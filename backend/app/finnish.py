from __future__ import annotations

import re

import snowballstemmer

_STEMMER = snowballstemmer.stemmer("finnish")
_TOKEN_RE = re.compile(r"[A-Za-zÅÄÖåäö]+", re.UNICODE)
_CHAR_MAP = str.maketrans({"ä": "a", "ö": "o", "å": "a", "Ä": "A", "Ö": "O", "Å": "A"})


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def normalize_finnish_chars(text: str) -> str:
    return text.translate(_CHAR_MAP)


def finnish_stems(text: str) -> list[str]:
    normalized = normalize_finnish_chars(normalize_whitespace(text))
    tokens = [t.lower() for t in _TOKEN_RE.findall(normalized)]
    if not tokens:
        return []
    return _STEMMER.stemWords(tokens)


def finnish_search_text(text: str) -> str:
    stems = finnish_stems(text)
    return " ".join(stems)


def stem_overlap_ratio(question: str, chunk_search_text: str) -> float:
    q_stems = set(finnish_stems(question))
    if not q_stems:
        return 0.0
    c_stems = set(chunk_search_text.split())
    if not c_stems:
        return 0.0
    overlap = q_stems.intersection(c_stems)
    return len(overlap) / len(q_stems)
