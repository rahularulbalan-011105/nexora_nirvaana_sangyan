"""Check a Message: the signed-in user's own most recent analysis and scan count."""
from __future__ import annotations

from sqlalchemy import func, select

from app.config import settings
from app.models.analysis import MessageAnalysis
from app.models.enums import AnalysisStatus, SignalType

# Presentation for each analysis status. Wording is deliberately non-accusatory.
STATUS_META: dict[str, dict[str, str]] = {
    AnalysisStatus.MULTIPLE_SIGNALS.value: {
        "label": "Multiple Safety Signals Detected",
        "summary": "This message contains several warning signals commonly associated "
        "with financial scams or misleading promotions.",
        "tone": "error",
        "icon": "warning",
    },
    AnalysisStatus.NEEDS_VERIFICATION.value: {
        "label": "Needs Verification",
        "summary": "Some claims in this message could not be confirmed. Check them with "
        "an official source before you act.",
        "tone": "secondary",
        "icon": "help",
    },
    AnalysisStatus.NO_OBVIOUS_SIGNALS.value: {
        "label": "No Obvious Warning Signals Detected",
        "summary": "Nothing in this message matched a known warning pattern. This is not "
        "a guarantee that it is genuine.",
        "tone": "tertiary",
        "icon": "check_circle",
    },
}

SEVERITY_LABEL = {"HIGH": "High Risk", "MEDIUM": "Medium Risk", "LOW": "Low Risk"}
_SEVERITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

INPUT_KIND_LABEL = {
    "TEXT": "Text Snippet",
    "IMAGE": "Image (Screenshot)",
    "PDF": "File (PDF)",
    "URL": "Link (URL)",
}

LINK_SIGNALS = {SignalType.SUSPICIOUS_LINK.value, SignalType.UNKNOWN_DOMAIN.value}


def status_meta(status: str | None) -> dict[str, str]:
    return STATUS_META.get(status or "", STATUS_META[AnalysisStatus.NEEDS_VERIFICATION.value])


def confidence_label(value: float | None) -> str:
    value = value or 0.0
    if value >= 0.75:
        return "High"
    if value >= 0.4:
        return "Moderate"
    return "Low"


def humanise(code: str | None) -> str:
    return (code or "").replace("_", " ").strip().capitalize()


def analysis_view(analysis: MessageAnalysis) -> dict:
    """Flatten an analysis into the values the template shows."""
    signals = sorted(
        analysis.signals,
        key=lambda s: _SEVERITY_RANK.get(s.severity, 0),
        reverse=True,
    )
    top_severity = signals[0].severity if signals else None
    nlp = analysis.nlp_result if isinstance(analysis.nlp_result, dict) else {}
    claims = [str(c) for c in (nlp.get("claims") or []) if c][:5]
    links = [str(link) for link in (nlp.get("links") or []) if link]
    if analysis.source_url and analysis.source_url not in links:
        links.insert(0, analysis.source_url)
    return {
        "obj": analysis,
        "text": analysis.text_for_display,
        "meta": status_meta(analysis.status),
        "confidence_label": confidence_label(analysis.confidence),
        "severity_label": SEVERITY_LABEL.get(top_severity or "", ""),
        "signals": signals,
        "signal_label": {s.id: humanise(s.signal_type) for s in signals},
        "claims": claims,
        "links": links,
        "link_signals": [s for s in signals if s.signal_type in LINK_SIGNALS],
        "kind_label": INPUT_KIND_LABEL.get(analysis.input_kind, humanise(analysis.input_kind)),
        "simple": [str(x) for x in (nlp.get("simple") or []) if x],
        "verify_links": verify_links(signals),
        "ocr_percent": (
            round(analysis.ocr_confidence * 100, 1)
            if analysis.ocr_used and analysis.ocr_confidence is not None
            else None
        ),
    }


# Official places to verify, chosen by what was found. Real public sites only.
SEBI_LINK = ("SEBI website", "https://www.sebi.gov.in/")
RBI_SACHET_LINK = ("RBI Sachet", "https://sachet.rbi.org.in/")
CYBERCRIME_LINK = ("Cyber Crime Portal", "https://cybercrime.gov.in/")
_BANKING_SIGNALS = {
    SignalType.OTP_REQUEST.value,
    SignalType.CREDENTIAL_REQUEST.value,
    SignalType.PAYMENT_REQUEST.value,
    SignalType.IMPERSONATION.value,
    SignalType.REMOTE_ACCESS_REQUEST.value,
    SignalType.PERSONAL_INFORMATION_REQUEST.value,
}


def verify_links(signals) -> list[tuple[str, str]]:
    types = {s.signal_type for s in signals}
    if types & _BANKING_SIGNALS:
        return [RBI_SACHET_LINK, SEBI_LINK, CYBERCRIME_LINK]
    if types:
        return [SEBI_LINK, RBI_SACHET_LINK, CYBERCRIME_LINK]
    return [SEBI_LINK, RBI_SACHET_LINK]


KIND_TITLE = {
    "TEXT": "Checked a message",
    "URL": "Checked a link",
    "PDF": "Checked a PDF",
    "IMAGE": "Checked an image",
}
KIND_ICON = {"TEXT": "chat", "URL": "link", "PDF": "picture_as_pdf", "IMAGE": "image"}


def history_item(a: MessageAnalysis) -> dict:
    """One "Past checks" row, shaped like the dashboard's recent-activity rows."""
    from app.page_context import _activity as act

    flagged = a.status in act.WARNING_STATUSES
    return {
        "id": str(a.id),
        "title": KIND_TITLE.get(a.input_kind, "Checked a message"),
        "kind_icon": KIND_ICON.get(a.input_kind, "chat"),
        "quote": act.snippet(a.source_url or a.text_for_display, 80),
        "badge": act.STATUS_TEXT.get(a.status, "Checked"),
        "badge_class": (
            "bg-error-container text-on-error-container"
            if flagged
            else "bg-tertiary-container/15 text-tertiary"
        ),
        "icon": "warning" if flagged else "verified_user",
        "icon_class": (
            "bg-error-container text-on-error-container"
            if flagged
            else "bg-primary-fixed text-primary"
        ),
        "detail": " • ".join(
            act.snippet(humanise(s.signal_type), 40) for s in (a.signals or [])[:3]
        ),
        "ago": act.time_ago(a.created_at),
    }


def build(db, user) -> dict:
    scan_count = int(
        db.execute(
            select(func.count())
            .select_from(MessageAnalysis)
            .where(MessageAnalysis.user_id == user.id)
        ).scalar()
        or 0
    )
    # The page starts fresh; past results open from the "Past checks" list.
    from app.services.analysis_inputs import ocr_available

    past = db.execute(
        select(MessageAnalysis)
        .where(MessageAnalysis.user_id == user.id)
        .order_by(MessageAnalysis.created_at.desc())
        .limit(20)
    ).scalars()
    return {
        "scan_count": scan_count,
        "latest_analysis": None,
        "past_checks": [history_item(a) for a in past],
        "ocr_available": ocr_available(),
        "max_upload_mb": settings.max_upload_mb,
    }
