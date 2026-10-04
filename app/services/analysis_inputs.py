"""Turning uploads into text for Check a Message, honestly.

- PDFs: text is extracted with pypdf. A scanned PDF with no text layer is
  reported as such - we never guess its contents.
- Images: OCR runs only if an OCR engine is actually installed (pytesseract
  with a tesseract binary, or easyocr). Otherwise the caller must supply the
  text the user typed from the image, and ``ocr_used`` stays False.
"""
from __future__ import annotations

import hashlib
import io
import logging
from datetime import datetime, timezone
from functools import lru_cache

from app.config import settings
from app.models.analysis import UploadedFile

log = logging.getLogger("nirvaan.analysis_inputs")

IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
MAX_PDF_PAGES = 30
MAX_EXTRACT_CHARS = 10_000


class InputError(ValueError):
    """A user-facing reason the upload cannot be checked."""


def max_bytes() -> int:
    return int(settings.max_upload_mb) * 1024 * 1024


def sniff_image(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_size(data: bytes) -> None:
    if not data:
        raise InputError("The file is empty.")
    if len(data) > max_bytes():
        raise InputError(f"The file is larger than {settings.max_upload_mb} MB.")


def validate_image(data: bytes) -> str:
    validate_size(data)
    kind = sniff_image(data)
    if kind is None:
        raise InputError("Please choose a JPG, PNG or WebP image.")
    return kind


def extract_pdf_text(data: bytes) -> tuple[str, int]:
    """Return ``(text, page_count)``. Raises InputError for unusable PDFs."""
    validate_size(data)
    if not data.lstrip()[:5] == b"%PDF-":
        raise InputError("This file is not a PDF.")
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency is installed
        raise InputError("PDF reading is not available on this server.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                if not reader.decrypt(""):
                    raise InputError("This PDF is password-protected, so its text cannot be read.")
            except InputError:
                raise
            except Exception as exc:
                raise InputError("This PDF is password-protected, so its text cannot be read.") from exc
        pages = reader.pages
        parts: list[str] = []
        total = 0
        for page in list(pages)[:MAX_PDF_PAGES]:
            chunk = page.extract_text() or ""
            parts.append(chunk)
            total += len(chunk)
            if total >= MAX_EXTRACT_CHARS:
                break
        text = "\n".join(p.strip() for p in parts if p.strip())
        return text[:MAX_EXTRACT_CHARS], len(pages)
    except InputError:
        raise
    except Exception as exc:
        log.info("pdf extraction failed: %s", exc)
        raise InputError("This PDF could not be read. It may be damaged.") from exc


@lru_cache(maxsize=1)
def ocr_engine() -> str | None:
    """Name of a working OCR engine, or None. Checked once per process."""
    try:
        import pytesseract  # type: ignore

        pytesseract.get_tesseract_version()
        from PIL import Image  # noqa: F401

        return "tesseract"
    except Exception:
        pass
    try:
        import easyocr  # type: ignore  # noqa: F401

        return "easyocr"
    except Exception:
        return None


def ocr_available() -> bool:
    return ocr_engine() is not None


def run_ocr(data: bytes) -> tuple[str, float | None]:
    """OCR an image. Only call when ``ocr_available()``."""
    engine = ocr_engine()
    if engine == "tesseract":
        import pytesseract  # type: ignore
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        d = pytesseract.image_to_data(
            img, lang="eng", output_type=pytesseract.Output.DICT
        )
        confs = [
            float(c) for c, w in zip(d.get("conf", []), d.get("text", []))
            if w and w.strip() and float(c) >= 0
        ]
        text = pytesseract.image_to_string(img)
        return text.strip(), (sum(confs) / len(confs) / 100) if confs else None
    if engine == "easyocr":
        import easyocr  # type: ignore

        reader = _easyocr_reader()
        results = reader.readtext(data)
        text = "\n".join(r[1] for r in results)
        conf = sum(r[2] for r in results) / len(results) if results else None
        return text.strip(), conf
    raise InputError("Text recognition is not available on this server.")


@lru_cache(maxsize=1)
def _easyocr_reader():  # pragma: no cover - heavy optional dependency
    import easyocr  # type: ignore

    return easyocr.Reader(["en", "hi"], gpu=False)


def record_upload(db, user, *, data: bytes, filename: str, content_type: str, kind: str,
                  keep_bytes: bool) -> UploadedFile:
    """Metadata row for an upload; bytes are written only when ``keep_bytes``."""
    digest = hashlib.sha256(data).hexdigest()
    safe_name = (filename or "upload").replace("\\", "/").rsplit("/", 1)[-1][:200] or "upload"
    row = UploadedFile(
        user_id=user.id,
        original_filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        sha256=digest,
        kind=kind,
    )
    if keep_bytes:
        ext = IMAGE_TYPES.get(content_type, "pdf" if kind == "PDF" else "bin")
        folder = settings.upload_path / str(user.id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{digest}.{ext}"
        if not path.exists():
            path.write_bytes(data)
        row.stored_path = str(path)
    else:
        row.stored_path = None
        row.purged_at = datetime.now(timezone.utc)
    db.add(row)
    db.flush()
    return row
