import hashlib
import io
import re
import zipfile
from pathlib import Path

from docx import Document
from fastapi import HTTPException
from pypdf import PdfReader

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 100000
COMPETENCY_TERMS = {
    "Python": ("python", "python程式"),
    "Software design": ("software", "api", "system design", "軟件", "軟體", "系統設計"),
    "Testing": ("test", "quality assurance", "測試", "品質"),
    "Data analysis": ("data", "analytics", "數據", "資料分析"),
    "Databases": ("sql", "database", "資料庫", "數據庫"),
    "Machine learning": (
        "machine learning",
        "artificial intelligence",
        "模型",
        "機器學習",
        "人工智能",
    ),
    "Teamwork": ("team", "collaborat", "團隊", "合作"),
    "Communication": ("communicat", "present", "stakeholder", "溝通", "匯報"),
    "Problem solving": ("problem", "debug", "solve", "解決", "除錯"),
}


def validate_text(text: str) -> str:
    text = text.replace("\x00", "").strip()
    if len(text) < 20:
        raise HTTPException(
            422,
            "The document has too little extractable text. Paste the job description; scanned PDFs require OCR, which is not supported.",
        )
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(
            413, "The extracted text exceeds 100,000 characters. Upload a shorter job description."
        )
    return text


def extract_file(filename: str, content: bytes) -> str:
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(413, "Files must be 5 MB or smaller.")
    extension = Path(filename).suffix.lower()
    if extension not in {".txt", ".pdf", ".docx"}:
        raise HTTPException(415, "Upload a TXT, text-based PDF, or DOCX file.")
    try:
        if extension == ".txt":
            if b"\x00" in content:
                raise ValueError("binary text")
            text = content.decode("utf-8-sig")
        elif extension == ".pdf":
            if not content.startswith(b"%PDF-"):
                raise ValueError("invalid PDF")
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted or len(reader.pages) > 50:
                raise ValueError("encrypted or too many pages")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            if not content.startswith(b"PK"):
                raise ValueError("invalid DOCX")
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                if len(entries) > 1000 or sum(x.file_size for x in entries) > 20 * 1024 * 1024:
                    raise ValueError("expanded file too large")
                if "word/document.xml" not in archive.namelist():
                    raise ValueError("not a DOCX")
            document = Document(io.BytesIO(content))
            text = "\n".join(
                [p.text for p in document.paragraphs]
                + [
                    cell.text
                    for table in document.tables
                    for row in table.rows
                    for cell in row.cells
                ]
            )
    except Exception as exc:
        raise HTTPException(
            422,
            "The file is corrupt, encrypted, unsupported, or not UTF-8 text. Paste the job description instead.",
        ) from exc
    return validate_text(text)


def profile_metadata(text: str, title: str | None) -> tuple[str, list[str], list[str]]:
    lower = text.lower()
    competencies = [
        name for name, terms in COMPETENCY_TERMS.items() if any(term in lower for term in terms)
    ]
    warnings = []
    if re.search(
        r"ignore (?:all |previous |the )*instructions|system prompt|system:|<\|im_start\|>|忽略.*指[令示]",
        lower,
    ):
        warnings.append(
            "Instruction-like text was detected. Uploaded content is treated only as quoted job data."
        )
    if not competencies:
        competencies = ["Role requirements"]
        warnings.append(
            "No supported technology competency was identified; check the extracted job text."
        )
    resolved_title = (title or re.split(r"[\n.!?。]", text)[0]).strip()[
        :160
    ] or "Interview practice"
    return resolved_title, competencies[:8], warnings


def chunk_text(text: str, prefix: str, source: str) -> list[dict]:
    # Approximate token boundaries: words/punctuation and individual CJK characters.
    units = list(re.finditer(r"[\u3400-\u9fff]|[A-Za-z0-9_]+|[^\w\s]", text))
    chunks = []
    for start in range(0, len(units), 370):
        end = min(start + 450, len(units))
        passage = text[units[start].start() : units[end - 1].end()].strip()
        digest = hashlib.sha256(passage.encode()).hexdigest()[:12]
        chunks.append({"id": f"{prefix}-{len(chunks)}-{digest}", "source": source, "text": passage})
        if end == len(units):
            break
    return chunks
