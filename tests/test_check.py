"""Check a Message: engine, four input modes, privacy and past results."""
from __future__ import annotations

import base64

import pytest

from tests.conftest import csrf_of

SCAM = (
    "Join our VIP Trading Club. Guaranteed 30% monthly returns with zero risk. "
    "SEBI approved strategy. Only 5 seats left - pay Rs 4,999 joining fee via UPI today. "
    "Details: http://bit.ly/vip-club"
)
PLAIN = "Hi, the society meeting is on Sunday at 6 pm in the community hall."

# 1x1 PNG
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def make_pdf(text: str | None) -> bytes:
    """A minimal one-page PDF, with a text layer only when ``text`` is given."""
    content = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET".encode() if text else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


def post(client, **fields):
    files = fields.pop("files", None)
    return client.post(
        "/api/check",
        data=fields,
        files=files,
        headers={"X-CSRF-Token": csrf_of(client), "Accept": "application/json"},
    )


@pytest.fixture
def user_client(auth_client, request):
    return auth_client(email=f"check-{request.node.name[:40]}@test.local")


# ---------------------------------------------------------------- engine


def test_engine_link_checks():
    from app.services import analysis as engine

    def types(url):
        return {f.signal_type for f in engine.inspect_link(url).findings}

    assert "SUSPICIOUS_LINK" in types("http://192.168.1.10/login")
    assert "SUSPICIOUS_LINK" in types("https://bit.ly/abc")
    assert "IMPERSONATION" in types("https://sebi-kyc-update.xyz/form")
    assert "IMPERSONATION" in types("https://zer0dha.com/login")
    assert "UNKNOWN_DOMAIN" in types("https://free-ipo.top")
    assert engine.inspect_link("https://www.sebi.gov.in/").findings == []
    assert engine.validate_url("not a link") is not None
    assert engine.validate_url("ftp://x.com") is not None
    assert engine.validate_url("example.com/offer") is None


def test_statuses_never_claim_safe():
    from app.models.enums import AnalysisStatus
    from app.services import analysis as engine

    assert engine.decide_status([])[0] == AnalysisStatus.NO_OBVIOUS_SIGNALS.value
    panes = engine.write_panes([], kind="TEXT", notes=[])
    assert all("safe" not in v.lower() for v in panes.values())


# ---------------------------------------------------------------- modes


def test_text_mode_detects_and_persists(user_client):
    r = post(user_client, mode="text", text=SCAM)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "MULTIPLE_SIGNALS_DETECTED"
    assert body["stored"] and body["id"]
    assert "Multiple Safety Signals Detected" in body["html"]
    assert "Checked a message" in body["row_html"]

    page = user_client.get("/check")
    assert page.status_code == 200
    assert body["id"] in page.text

    again = user_client.get(f"/api/check/{body['id']}")
    assert again.status_code == 200
    assert "Guaranteed" in again.json()["html"] or "guaranteed" in again.json()["html"]


def test_text_mode_plain_message(user_client):
    r = post(user_client, mode="text", text=PLAIN)
    assert r.status_code == 200
    assert r.json()["status"] == "NO_OBVIOUS_WARNING_SIGNALS_DETECTED"


def test_text_mode_validation(user_client):
    r = post(user_client, mode="text", text="   ")
    assert r.status_code == 422 and r.json()["code"] == "empty_text"


def test_credentials_are_redacted_before_storing(user_client, db):
    from app.models.analysis import MessageAnalysis

    r = post(user_client, mode="text", text="Bank KYC: share your OTP 482913 now to avoid account blocked")
    assert r.status_code == 200
    a = db.get(MessageAnalysis, __import__("uuid").UUID(r.json()["id"]))
    assert "482913" not in a.raw_text
    assert any(s.signal_type == "OTP_REQUEST" for s in a.signals)


def test_link_mode(user_client):
    r = post(user_client, mode="link", url="http://sebi-registration.xyz/verify")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "MULTIPLE_SIGNALS_DETECTED"
    assert "The page itself was not opened" in body["html"]
    assert "Checked a link" in body["row_html"]

    bad = post(user_client, mode="link", url="hello world")
    assert bad.status_code == 422 and bad.json()["code"] == "bad_url"


def test_image_mode_without_ocr_requires_typed_text(user_client, db):
    from app.models.analysis import MessageAnalysis, UploadedFile
    from app.services import analysis_inputs

    if analysis_inputs.ocr_available():
        pytest.skip("OCR installed; typed-text path not required")
    files = {"file": ("shot.png", PNG, "image/png")}
    r = post(user_client, mode="image", typed_text="", files=files)
    assert r.status_code == 422 and r.json()["code"] == "need_typed"

    r = post(user_client, mode="image", typed_text=SCAM, files={"file": ("shot.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    a = db.get(MessageAnalysis, __import__("uuid").UUID(r.json()["id"]))
    assert a.input_kind == "IMAGE" and a.ocr_used is False
    up = db.get(UploadedFile, a.uploaded_file_id)
    assert up is not None and up.stored_path is None  # bytes not retained by default

    bad = post(user_client, mode="image", typed_text="x", files={"file": ("a.png", b"not an image", "image/png")})
    assert bad.status_code == 422 and bad.json()["code"] == "bad_file"


def test_pdf_mode(user_client):
    r = post(user_client, mode="pdf", files={"file": ("offer.pdf", make_pdf("Guaranteed returns of 40% monthly. Act now."), "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("MULTIPLE_SIGNALS_DETECTED", "NEEDS_VERIFICATION")
    assert "Checked a PDF" in r.json()["row_html"]

    empty = post(user_client, mode="pdf", files={"file": ("scan.pdf", make_pdf(None), "application/pdf")})
    assert empty.status_code == 422 and empty.json()["code"] == "pdf_no_text"

    notpdf = post(user_client, mode="pdf", files={"file": ("x.pdf", b"hello", "application/pdf")})
    assert notpdf.status_code == 422


def test_history_off_is_not_persisted(user_client, db):
    from sqlalchemy import func, select

    from app.models.analysis import MessageAnalysis
    from app.models.user import User, UserPrivacySettings

    user = db.execute(select(User).where(User.email.like("check-test_history_off%"))).scalar_one()
    p = db.execute(select(UserPrivacySettings).where(UserPrivacySettings.user_id == user.id)).scalar_one_or_none()
    if p is None:
        p = UserPrivacySettings(user_id=user.id)
        db.add(p)
    p.store_analysis_history = False
    db.commit()

    r = post(user_client, mode="text", text=SCAM)
    assert r.status_code == 200
    assert r.json()["stored"] is False and r.json()["id"] is None and r.json()["row_html"] is None
    count = db.execute(select(func.count()).select_from(MessageAnalysis).where(MessageAnalysis.user_id == user.id)).scalar()
    assert count == 0


def test_other_users_results_are_private(auth_client, client, make_user):
    c = auth_client(email="check-owner@test.local")
    rid = post(c, mode="text", text=SCAM).json()["id"]
    client.cookies.clear()
    auth_client(email="check-other@test.local")
    assert client.get(f"/api/check/{rid}").status_code == 404


def test_save_to_journal(user_client, db):
    from sqlalchemy import select

    from app.models.reflection import JournalEntry

    rid = post(user_client, mode="text", text=SCAM).json()["id"]
    r = user_client.post(f"/api/check/{rid}/journal", headers={"X-CSRF-Token": csrf_of(user_client)})
    assert r.status_code == 200 and r.json()["saved"]
    import uuid

    assert db.get(JournalEntry, uuid.UUID(r.json()["journal_id"])) is not None


def test_csrf_required(user_client):
    r = user_client.post("/api/check", data={"mode": "text", "text": SCAM})
    assert r.status_code == 403
