import io
import re

from pypdf import PdfReader

MAX_PAGES = 10
MIN_TEXT_CHARS = 50


class PDFError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


def extract_text(data: bytes) -> str:
    # Check the real file signature; the Content-Type header can be faked.
    if not data.startswith(b"%PDF-"):
        raise PDFError("File is not a valid PDF", status_code=415)

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise PDFError("PDF is password protected")
        pages = [(page.extract_text() or "") for page in reader.pages[:MAX_PAGES]]
    except PDFError:
        raise
    except Exception as exc:
        raise PDFError("Could not read this PDF") from exc

    text = "\n".join(pages).replace("\x00", "")  # PostgreSQL rejects NUL characters
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if len(text) < MIN_TEXT_CHARS:
        raise PDFError(
            "No readable text found. Scanned/image PDFs need OCR, which is not supported yet."
        )
    return text