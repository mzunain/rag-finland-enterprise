from __future__ import annotations

import pytest
from app.ingestion import chunk_pages, extract_text


def test_extract_text_txt():
    pages = extract_text("hello.txt", b"Hello world")
    assert len(pages) == 1
    assert pages[0] == (1, "Hello world")


def test_extract_text_csv():
    pages = extract_text("data.csv", b"col1,col2\nval1,val2")
    assert len(pages) == 1
    assert "col1" in pages[0][1]


def test_extract_text_md():
    pages = extract_text("readme.md", b"# Title\nContent here")
    assert len(pages) == 1


def test_extract_text_unsupported():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("file.xyz", b"data")


def test_extract_text_utf8_with_errors():
    pages = extract_text("broken.txt", b"Hello \xff\xfe world")
    assert len(pages) == 1
    assert "Hello" in pages[0][1]


def test_chunk_pages_single_short_page():
    pages = [(1, "Short text.")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0]["page"] == 1
    assert chunks[0]["content"] == "Short text."


def test_chunk_pages_empty_page_skipped():
    pages = [(1, ""), (2, "   "), (3, "Actual content")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 1
    assert chunks[0]["page"] == 3


def test_chunk_pages_long_text_splits():
    long_text = "Word " * 1000
    pages = [(1, long_text)]
    chunks = chunk_pages(pages, chunk_size=500, chunk_overlap=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["page"] == 1
        assert len(chunk["content"]) <= 600


def test_chunk_pages_multiple_pages():
    pages = [(1, "Page one content."), (2, "Page two content.")]
    chunks = chunk_pages(pages)
    assert len(chunks) == 2
    pages_seen = {c["page"] for c in chunks}
    assert pages_seen == {1, 2}


def test_chunk_pages_preserves_chunk_index():
    long_text = "Sentence. " * 500
    pages = [(1, long_text)]
    chunks = chunk_pages(pages, chunk_size=200, chunk_overlap=20)
    indices = [c["chunk_index"] for c in chunks]
    assert indices == list(range(len(chunks)))
