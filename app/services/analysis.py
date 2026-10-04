"""Check a Message: the deterministic analysis engine.

What it does, honestly:
- applies the admin-editable ``SafetyRule`` regex patterns to the message;
- adds built-in checks for links (shorteners, IP hosts, lookalike domains,
  plain http, unusual TLDs) and for a regulator claim with no registration
  number, plus fallbacks for core patterns when no rule covers them;
- derives one of the three ``AnalysisStatus`` values from what was found and
  writes the four explainability panes from those findings only.

It never opens a link, never judges intent, and never calls a model. Text is
redacted (OTP/PIN/card/etc.) before it is analysed, so every stored evidence
span refers to the redacted text.
"""
from __future__ import annotations

import ipaddress
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

from sqlalchemy import select

from app.models.analysis import AnalysisSignal, MessageAnalysis, SafetyRule
from app.models.enums import AnalysisStatus, GuardrailAction, InputKind, Severity, SignalType
from app.services import responsible_ai as rai

MAX_TEXT_CHARS = 10_000

_SEV_RANK = {Severity.LOW.value: 1, Severity.MEDIUM.value: 2, Severity.HIGH.value: 3}

# ---------------------------------------------------------------------------
# Built-in checks
# ---------------------------------------------------------------------------

# Fallbacks used only when no enabled SafetyRule exists for that signal type.
_FALLBACK_RULES: list[dict] = [
    {
        "signal_type": SignalType.GUARANTEED_RETURN.value,
        "pattern": r"\b(guarantee[ds]?|assured|risk[\s-]?free|no[\s-]?risk)\b.{0,40}"
        r"\b(returns?|profits?|income)\b",
        "severity": Severity.HIGH.value,
        "weight": 2.0,
        "explanation": "The message promises a guaranteed or risk-free return. "
        "Market-linked returns cannot be guaranteed.",
        "verify_hint": "Ask who is legally bound by the guarantee and get it in writing.",
    },
    {
        "signal_type": SignalType.URGENCY.value,
        "pattern": r"\b(urgent|immediately|right now|act now|hurry|last chance|today only)\b",
        "severity": Severity.MEDIUM.value,
        "weight": 1.0,
        "explanation": "The message pushes you to act quickly, which leaves less time to check.",
        "verify_hint": "Wait before acting. A genuine offer can wait a day.",
    },
    {
        "signal_type": SignalType.OTP_REQUEST.value,
        "pattern": r"\b(share|send|tell|give|provide)\b.{0,30}\b(otp|one[\s-]?time"
        r"\s*(?:password|code)|pin|cvv)\b",
        "severity": Severity.HIGH.value,
        "weight": 2.0,
        "explanation": "The message asks for a one-time password, PIN or card code. "
        "Banks and regulators do not ask for these.",
        "verify_hint": "Do not share it. Call your bank on the number printed on your card.",
    },
    {
        "signal_type": SignalType.PAYMENT_REQUEST.value,
        "pattern": r"\b(transfer|deposit|pay|upi|gpay|phonepe|paytm)\b.{0,40}"
        r"\b(now|today|fee|account)\b",
        "severity": Severity.HIGH.value,
        "weight": 1.7,
        "explanation": "The message asks for a payment, often an upfront fee.",
        "verify_hint": "Check whether the receiving account belongs to a registered entity.",
    },
]

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "rb.gy", "cutt.ly", "is.gd", "shorturl.at",
    "t.ly", "tiny.cc", "ow.ly", "buff.ly", "s.id", "rebrand.ly", "bitly.com", "v.gd",
    "shorte.st", "adf.ly", "tinyurl.in", "short.gy", "rb.gy",
}
UNUSUAL_TLDS = {
    "xyz", "top", "click", "live", "buzz", "icu", "online", "site", "club", "loan", "win",
    "work", "rest", "cfd", "sbs", "vip", "bond", "shop", "monster", "quest", "cyou", "tk",
    "ml", "ga", "cf", "gq",
}
# Official domains of commonly impersonated Indian financial bodies and firms.
OFFICIAL_DOMAINS = {
    "sebi": "sebi.gov.in",
    "rbi": "rbi.org.in",
    "irdai": "irdai.gov.in",
    "npci": "npci.org.in",
    "nseindia": "nseindia.com",
    "bseindia": "bseindia.com",
    "amfiindia": "amfiindia.com",
    "incometax": "incometax.gov.in",
    "sbi": "sbi.co.in",
    "onlinesbi": "onlinesbi.sbi",
    "hdfcbank": "hdfcbank.com",
    "icicibank": "icicibank.com",
    "axisbank": "axisbank.com",
    "kotak": "kotak.com",
    "zerodha": "zerodha.com",
    "groww": "groww.in",
    "upstox": "upstox.com",
    "paytm": "paytm.com",
    "phonepe": "phonepe.com",
    "lic": "licindia.in",
    "licindia": "licindia.in",
}
_LEET = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s"})

_URL_RE = re.compile(
    r"(?:(?:https?://)|(?:www\.))[^\s<>\"')\]]+"
    r"|\b(?:[a-z0-9-]+\.)+(?:com|in|org|net|io|co|info|biz|me|ly|gl|gy|at|cc|id|xyz|top|"
    r"click|live|buzz|icu|online|site|club|loan|win|work|rest|cfd|sbs|vip|bond|shop|tk|"
    r"ml|ga|cf|gq|app|link|ai|sbi)(?:/[^\s<>\"')\]]*)?",
    re.IGNORECASE,
)
_REGULATOR_RE = re.compile(r"\b(sebi|rbi|irdai|amfi|nse|bse)\b", re.IGNORECASE)
_REG_NUMBER_RE = re.compile(r"\b(IN[AHZ]\d{6,9}|ARN[-\s]?\d{3,7}|INP\d{6,9})\b", re.IGNORECASE)
_CLAIM_HINT_RE = re.compile(
    r"(\d+(?:\.\d+)?\s*%|₹|\brs\.?\s?\d|\binr\b|\breturns?\b|\bprofits?\b|\bguarantee|"
    r"\bapproved\b|\bregistered\b|\bsebi\b|\brbi\b|\bdouble\b|\bbonus\b|\bfee\b|\bearn)",
    re.IGNORECASE,
)

SIMPLE_WORDS = {
    SignalType.GUARANTEED_RETURN.value: "It promises you will surely make money. Nobody can promise that for market investments.",
    SignalType.UNREALISTIC_RETURN.value: "The profit it talks about is much higher than normal savings or investments give.",
    SignalType.URGENCY.value: "It tries to make you hurry. Hurrying leaves no time to check.",
    SignalType.LIMITED_TIME_PRESSURE.value: "It says the offer will end soon, so you act before thinking.",
    SignalType.FOMO.value: "It makes you feel you will miss out if you do not join.",
    SignalType.SOCIAL_PRESSURE.value: "It uses other people's stories to make you trust it.",
    SignalType.LOSS_RECOVERY_PROMPT.value: "It offers to get back money you lost. This often leads to losing more.",
    SignalType.IMPERSONATION.value: "The sender says they are from a bank or office. Anyone can claim that in a message.",
    SignalType.UNVERIFIED_REGULATORY_CLAIM.value: "It uses a regulator's name to look trustworthy, but gives no way to check it.",
    SignalType.FAKE_AUTHORITY.value: "It uses an official-sounding name to look trustworthy.",
    SignalType.SUSPICIOUS_LINK.value: "The link has features that are often used to hide where it really goes.",
    SignalType.UNKNOWN_DOMAIN.value: "The website name is unusual and not one we recognise.",
    SignalType.PAYMENT_REQUEST.value: "It asks you to send money.",
    SignalType.PERSONAL_INFORMATION_REQUEST.value: "It asks for your personal details.",
    SignalType.OTP_REQUEST.value: "It asks for your OTP or PIN. Never share these with anyone.",
    SignalType.CREDENTIAL_REQUEST.value: "It asks for your login or bank details.",
    SignalType.REMOTE_ACCESS_REQUEST.value: "It asks you to install an app that lets someone control your phone.",
    SignalType.MISLEADING_TESTIMONIAL.value: "It shows other people's profits as proof. Such screenshots are easy to fake.",
}


# ---------------------------------------------------------------------------
# Data holders
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    signal_type: str
    severity: str
    weight: float
    evidence: str
    start: int | None
    end: int | None
    explanation: str
    verify_hint: str
    detector: str = "rule"
    rule_id: uuid.UUID | None = None


@dataclass
class LinkReport:
    url: str
    host: str
    findings: list[Finding] = field(default_factory=list)
    official_match: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def detect_language(text: str) -> tuple[str, float]:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en", 0.0
    deva = sum(1 for c in letters if "ऀ" <= c <= "ॿ")
    tamil = sum(1 for c in letters if "஀" <= c <= "௿")
    n = len(letters)
    if deva / n > 0.3:
        return "hi", round(deva / n, 2)
    if tamil / n > 0.3:
        return "ta", round(tamil / n, 2)
    return "en", round(1 - (deva + tamil) / n, 2)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _registered_domain(host: str) -> str:
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "gov", "org", "net", "ac", "nic", "gen"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def normalise_url(raw: str) -> tuple[str, bool]:
    """Return ``(url_with_scheme, had_scheme)``."""
    raw = raw.strip().strip(".,;")
    if re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.IGNORECASE):
        return raw, True
    return "https://" + raw, False


def validate_url(raw: str) -> str | None:
    """Error message for an unusable link, or None if it can be analysed."""
    raw = (raw or "").strip()
    if not raw:
        return "Please paste a link to check."
    if len(raw) > 2048:
        return "That link is too long to check."
    if re.search(r"\s", raw):
        return "A link cannot contain spaces. Please paste just the link."
    url, _ = normalise_url(raw)
    try:
        parts = urlsplit(url)
    except ValueError:
        return "That does not look like a valid link."
    if parts.scheme.lower() not in ("http", "https"):
        return "Only web links starting with http:// or https:// can be checked."
    host = (parts.hostname or "").lower()
    if not host or ("." not in host and not _is_ip(host)):
        return "That does not look like a valid link."
    return None


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def inspect_link(raw: str, *, evidence_offset: int | None = None) -> LinkReport:
    """Inspect a link's structure. The page itself is never fetched."""
    url, had_scheme = normalise_url(raw)
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        scheme = parts.scheme.lower()
        userinfo = "@" in parts.netloc
    except ValueError:
        host, scheme, userinfo = "", "", False
    report = LinkReport(url=raw, host=host)
    start = evidence_offset
    end = evidence_offset + len(raw) if evidence_offset is not None else None

    def add(sig: str, sev: str, weight: float, why: str, hint: str) -> None:
        report.findings.append(
            Finding(sig, sev, weight, raw, start, end, why, hint, detector="rule")
        )

    if not host:
        return report

    if _is_ip(host):
        add(SignalType.SUSPICIOUS_LINK.value, Severity.HIGH.value, 1.8,
            f"The link points to a raw IP address ({host}) instead of a website name. "
            "Genuine financial services use named, registered domains.",
            "Do not open it. Visit the organisation's website by typing its name yourself.")
        return report

    reg = _registered_domain(host)
    if host in URL_SHORTENERS or reg in URL_SHORTENERS:
        add(SignalType.SUSPICIOUS_LINK.value, Severity.MEDIUM.value, 1.2,
            f"This is a shortened link ({reg}). It hides the real destination.",
            "Ask the sender for the full website address, or find the organisation's site yourself.")

    if host.startswith("xn--") or ".xn--" in host:
        add(SignalType.SUSPICIOUS_LINK.value, Severity.HIGH.value, 1.6,
            "The website name uses special characters that can imitate a familiar name.",
            "Type the organisation's official address yourself instead of using this link.")

    if userinfo:
        add(SignalType.SUSPICIOUS_LINK.value, Severity.HIGH.value, 1.6,
            "The link contains an '@' before the website name, a trick that hides the real destination.",
            "Do not open it. Look up the organisation's site yourself.")

    if had_scheme and scheme == "http":
        add(SignalType.SUSPICIOUS_LINK.value, Severity.LOW.value, 0.6,
            "The link uses http:// without encryption. Financial websites normally use https://.",
            "Do not enter any personal or banking details on a page opened from this link.")

    tld = host.rsplit(".", 1)[-1]
    if tld in UNUSUAL_TLDS:
        add(SignalType.UNKNOWN_DOMAIN.value, Severity.MEDIUM.value, 1.0,
            f"The website ends in '.{tld}', an ending rarely used by regulated financial firms in India.",
            "Check the firm's registered website on the regulator's site, such as sebi.gov.in.")

    # Lookalike / brand-in-subdomain checks.
    official_domains = set(OFFICIAL_DOMAINS.values())
    if reg in official_domains or host.endswith(".gov.in") or host.endswith(".nic.in"):
        report.official_match = reg
    else:
        labels = re.split(r"[.-]", host.translate(_LEET))
        first_label = reg.split(".")[0].translate(_LEET)
        hit = None
        for brand, official in OFFICIAL_DOMAINS.items():
            if len(brand) <= 3:
                # Short names (sbi, rbi, lic) only count as whole labels.
                if brand in labels:
                    hit = (brand, official)
                    break
                continue
            if brand in labels or brand in first_label:
                hit = (brand, official)
                break
            if len(first_label) >= 5 and _levenshtein(first_label, brand) <= (1 if len(brand) < 7 else 2):
                hit = (brand, official)
                break
        if hit:
            add(SignalType.IMPERSONATION.value, Severity.HIGH.value, 1.8,
                f"The website name looks like '{hit[1]}' but is a different address ({reg}).",
                f"Type {hit[1]} into your browser yourself instead of using this link.")

    if host.count("-") >= 3 or len(host) > 50 or host.count(".") >= 5:
        add(SignalType.SUSPICIOUS_LINK.value, Severity.LOW.value, 0.6,
            "The website name is unusually long or complex, a pattern often used to look official.",
            "Compare it carefully with the organisation's known website address.")
    return report


def extract_links(text: str) -> list[tuple[str, int]]:
    links: list[tuple[str, int]] = []
    seen: set[str] = set()
    for m in _URL_RE.finditer(text):
        link = m.group(0).rstrip(".,;:!?")
        # Skip bare words like "e.g." that matched the domain shape poorly.
        if "." not in link or link.lower() in seen:
            continue
        seen.add(link.lower())
        links.append((link, m.start()))
    return links[:10]


def extract_claims(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?\n])\s+|\n+", text)
    claims = []
    for s in sentences:
        s = s.strip(" -•*\t")
        if 8 <= len(s) <= 220 and _CLAIM_HINT_RE.search(s):
            claims.append(s)
    return claims[:5]


def _enabled_rules(db) -> list[SafetyRule]:
    return list(db.execute(select(SafetyRule).where(SafetyRule.enabled.is_(True))).scalars())


def find_signals(db, text: str, language: str = "en") -> list[Finding]:
    """Rule matches + built-in checks over (already redacted) ``text``."""
    findings: list[Finding] = []
    rules = _enabled_rules(db)
    covered = {r.signal_type for r in rules}

    for rule in sorted(rules, key=lambda r: -float(r.weight or 0)):
        try:
            m = re.search(rule.pattern, text, re.IGNORECASE)
        except re.error:
            continue
        if not m:
            continue
        findings.append(
            Finding(
                signal_type=rule.signal_type,
                severity=rule.severity,
                weight=float(rule.weight or 1.0),
                evidence=m.group(0).strip()[:300],
                start=m.start(),
                end=m.end(),
                explanation=rule.explanation_for(language),
                verify_hint=rule.verify_hint_en or "",
                rule_id=rule.id,
            )
        )

    for spec in _FALLBACK_RULES:
        if spec["signal_type"] in covered:
            continue
        m = re.search(spec["pattern"], text, re.IGNORECASE)
        if m:
            findings.append(
                Finding(spec["signal_type"], spec["severity"], spec["weight"],
                        m.group(0).strip()[:300], m.start(), m.end(),
                        spec["explanation"], spec["verify_hint"])
            )

    # A regulator named with no registration number to check.
    have_reg_claim = any(
        f.signal_type in (SignalType.UNVERIFIED_REGULATORY_CLAIM.value, SignalType.FAKE_AUTHORITY.value)
        for f in findings
    )
    reg = _REGULATOR_RE.search(text)
    if reg and not have_reg_claim and re.search(
        r"\b(approved|registered|certified|authori[sz]ed|licensed|recogni[sz]ed)\b", text, re.IGNORECASE
    ) and not _REG_NUMBER_RE.search(text):
        findings.append(
            Finding(SignalType.UNVERIFIED_REGULATORY_CLAIM.value, Severity.MEDIUM.value, 1.2,
                    reg.group(0), reg.start(), reg.end(),
                    "A regulator is mentioned as backing, but no registration number is given to check.",
                    "Ask for the registration number and look it up yourself on the regulator's website.")
        )

    for link, offset in extract_links(text):
        findings.extend(inspect_link(link, evidence_offset=offset).findings)

    return _dedupe(findings)


def _dedupe(findings: list[Finding]) -> list[Finding]:
    """One signal per (type, evidence); keep the strongest."""
    out: dict[tuple[str, str], Finding] = {}
    for f in findings:
        key = (f.signal_type, f.evidence.lower())
        if key not in out or f.weight > out[key].weight:
            out[key] = f
    # And at most two signals of the same type, so one pattern does not dominate.
    per_type: dict[str, int] = {}
    result = []
    for f in sorted(out.values(), key=lambda f: (-_SEV_RANK.get(f.severity, 0), -f.weight)):
        per_type[f.signal_type] = per_type.get(f.signal_type, 0) + 1
        if per_type[f.signal_type] <= 2:
            result.append(f)
    return result


def decide_status(findings: list[Finding]) -> tuple[str, float]:
    """Status and detection confidence from what was found - nothing else."""
    if not findings:
        return AnalysisStatus.NO_OBVIOUS_SIGNALS.value, 0.4
    types = {f.signal_type for f in findings}
    score = sum(f.weight for f in findings)
    high = any(f.severity == Severity.HIGH.value for f in findings)
    if len(types) >= 2 and (high or score >= 3.0):
        status = AnalysisStatus.MULTIPLE_SIGNALS.value
    else:
        status = AnalysisStatus.NEEDS_VERIFICATION.value
    confidence = min(0.95, 0.45 + 0.1 * score)
    return status, round(confidence, 2)


def _human(sig: str) -> str:
    return sig.replace("_", " ").capitalize()


def write_panes(findings: list[Finding], *, kind: str, notes: list[str]) -> dict[str, str]:
    if findings:
        names = []
        for f in findings:
            n = _human(f.signal_type).lower()
            if n not in names:
                names.append(n)
        detected = (
            f"We found {len(findings)} warning signal{'s' if len(findings) != 1 else ''}: "
            + ", ".join(names) + "."
        )
        why = (
            "These patterns are commonly seen in misleading financial messages. "
            "They describe the message, not the sender's intent."
        )
        hints = []
        for f in findings:
            if f.verify_hint and f.verify_hint not in hints:
                hints.append(f.verify_hint)
        verify = "\n".join(f"- {h}" for h in hints[:4]) or (
            "Check the sender and any registration number on the regulator's official website."
        )
    else:
        detected = "Nothing in this content matched our known warning patterns."
        why = (
            "Our checks look for specific patterns such as guaranteed returns, pressure to act, "
            "requests for OTPs or payments, and unusual links. None were found."
        )
        verify = (
            "If the message asks you to invest, pay or share details, confirm the sender "
            "independently through an official website or phone number you look up yourself."
        )
    uncertain_parts = [
        "This check is based on patterns in the content only. We cannot see who sent it, "
        "and a result without signals is not proof that something is genuine."
    ]
    uncertain_parts.extend(notes)
    return {
        "what_we_detected": detected,
        "why_it_matters": why,
        "what_to_verify": verify,
        "what_is_uncertain": "\n".join(uncertain_parts),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@dataclass
class CheckInput:
    kind: str  # InputKind value
    text: str = ""
    url: str | None = None
    ocr_used: bool = False
    ocr_confidence: float | None = None
    ocr_text: str | None = None
    notes: list[str] = field(default_factory=list)
    uploaded_file_id: uuid.UUID | None = None


def analyse(db, user, data: CheckInput, *, language: str = "en", persist: bool = True) -> MessageAnalysis:
    """Run the checks and build a ``MessageAnalysis`` (added to ``db`` only if ``persist``)."""
    started = time.perf_counter()
    notes = list(data.notes)

    source = data.text or ""
    if data.kind == InputKind.URL.value:
        source = (data.url or "").strip()
    source = source[:MAX_TEXT_CHARS]
    redacted, sensitive = rai.redact_sensitive(source)
    if sensitive:
        notes.append(
            "Some sensitive details (" + ", ".join(k.replace("_", " ") for k in sensitive)
            + ") were masked before checking and are not stored."
        )

    if data.kind == InputKind.URL.value:
        report = inspect_link(redacted, evidence_offset=0)
        findings = _dedupe(report.findings)
        notes.append(
            "Only the link address was checked. The page itself was not opened, so its "
            "content was not reviewed."
        )
        if report.official_match:
            notes.append(
                f"The address matches the known website {report.official_match}. Make sure "
                "you typed or bookmarked it yourself rather than following a forwarded link."
            )
        links = [redacted]
        claims: list[str] = []
    else:
        findings = find_signals(db, redacted, language)
        links = [link for link, _ in extract_links(redacted)]
        claims = extract_claims(redacted)
        if links:
            notes.append("Links in the message were checked by their address only; they were not opened.")

    status, confidence = decide_status(findings)
    panes = write_panes(findings, kind=data.kind, notes=notes)
    lang, lang_conf = detect_language(redacted)

    simple = []
    for f in findings:
        line = SIMPLE_WORDS.get(f.signal_type)
        if line and line not in simple:
            simple.append(line)

    now = datetime.now(timezone.utc)
    analysis = MessageAnalysis(
        id=uuid.uuid4(),
        user_id=user.id,
        uploaded_file_id=data.uploaded_file_id,
        input_kind=data.kind,
        source_url=redacted if data.kind == InputKind.URL.value else None,
        raw_text=redacted if data.kind != InputKind.IMAGE.value or not data.ocr_used
        else rai.redact_sensitive(data.ocr_text or "")[0],
        corrected_text=redacted if data.kind == InputKind.IMAGE.value and data.ocr_used else None,
        ocr_used=data.ocr_used,
        ocr_confidence=data.ocr_confidence,
        detected_language=lang,
        language_confidence=lang_conf,
        status=status,
        confidence=confidence,
        nlp_result={
            "claims": claims,
            "links": links,
            "simple": simple,
            "engine": "rules",
            "sensitive_masked": sensitive,
        },
        guardrail_action=GuardrailAction.TRANSFORM.value if sensitive else GuardrailAction.ALLOW.value,
        guardrail_notes={"sensitive_found": sensitive},
        ai_provider="rules",
        created_at=now,
        updated_at=now,
        **panes,
    )
    for f in findings:
        # rule_id only (not the relationship) so an unsaved result never cascades into the session.
        analysis.signals.append(
            AnalysisSignal(
                id=uuid.uuid4(),
                rule_id=f.rule_id,
                signal_type=f.signal_type,
                severity=f.severity,
                confidence=round(min(0.95, 0.5 + 0.15 * f.weight), 2),
                evidence=f.evidence,
                evidence_start=f.start,
                evidence_end=f.end,
                explanation=f.explanation,
                verify_hint=f.verify_hint,
                detector=f.detector,
            )
        )
    analysis.processing_ms = int((time.perf_counter() - started) * 1000)
    if persist:
        db.add(analysis)
    return analysis
