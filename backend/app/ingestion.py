from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List, Tuple

from docx import Document as DocxDocument
from docx.opc.exceptions import PackageNotFoundError
from langchain_text_splitters import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError


def extract_text(filename: str, payload: bytes) -> List[Tuple[int, str]]:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(payload)
    if ext == ".docx":
        return _extract_docx(payload)
    if ext in {".txt", ".md", ".csv"}:
        text = payload.decode("utf-8", errors="ignore")
        return [(1, text)]
    raise ValueError(f"Unsupported file type: {ext}")


def _extract_pdf(payload: bytes) -> List[Tuple[int, str]]:
    pages: List[Tuple[int, str]] = []
    try:
        reader = PdfReader(BytesIO(payload))
    except (PdfReadError, ValueError, OSError) as exc:
        raise ValueError("Could not parse PDF file") from exc

    for idx, page in enumerate(reader.pages, start=1):
        pages.append((idx, page.extract_text() or ""))
    return pages


def _extract_docx(payload: bytes) -> List[Tuple[int, str]]:
    try:
        doc = DocxDocument(BytesIO(payload))
    except (PackageNotFoundError, ValueError, OSError) as exc:
        raise ValueError("Could not parse DOCX file") from exc
    text = "\n".join(p.text for p in doc.paragraphs)
    return [(1, text)]


def chunk_pages(pages: List[Tuple[int, str]], chunk_size: int = 2000, chunk_overlap: int = 250):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = []
    for page_num, text in pages:
        if not text.strip():
            continue
        page_chunks = splitter.split_text(text)
        for i, chunk in enumerate(page_chunks):
            chunks.append(
                {
                    "page": page_num,
                    "chunk_index": i,
                    "content": chunk,
                }
            )
    return chunks
