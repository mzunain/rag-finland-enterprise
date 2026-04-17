from __future__ import annotations

import re

import snowballstemmer

_STEMMER = snowballstemmer.stemmer("finnish")
_TOKEN_RE = re.compile(r"[A-Za-zÅÄÖåäö]+", re.UNICODE)
_CHAR_MAP = str.maketrans({"ä": "a", "ö": "o", "å": "a", "Ä": "A", "Ö": "O", "Å": "A"})
_VOWELS = set("aeiouy")
_COMMON_PARTS = {
    "tieto",
    "turva",
    "loma",
    "vuosiloma",
    "henkilo",
    "johtaja",
    "kaytanto",
    "opas",
    "hallinto",
    "tyo",
    "sopimus",
    "yritys",
    "palvelu",
    "prosessi",
    "dokumentti",
    "ohje",
    "jarjestelma",
}


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def normalize_finnish_chars(text: str) -> str:
    return text.translate(_CHAR_MAP)


def decompose_finnish_compound(token: str) -> list[str]:
    word = normalize_finnish_chars(token.lower()).strip()
    if len(word) < 10:
        return [word] if word else []
    if not any(ch in _VOWELS for ch in word):
        return [word]

    best_parts: tuple[str, str] | None = None
    best_score = 0
    for idx in range(4, len(word) - 3):
        left = word[:idx]
        right = word[idx:]
        if len(left) < 3 or len(right) < 3:
            continue
        if not any(ch in _VOWELS for ch in left) or not any(ch in _VOWELS for ch in right):
            continue

        score = 0
        if left in _COMMON_PARTS:
            score += 2
        if right in _COMMON_PARTS:
            score += 2
        if left.endswith("n"):
            score += 1
        if right.startswith(("tieto", "turva", "loma", "opas", "ohje", "jarjestelma")):
            score += 1
        if abs(len(left) - len(right)) <= 4:
            score += 1

        if score > best_score:
            best_score = score
            best_parts = (left, right)

    if best_parts and best_score >= 3:
        return [best_parts[0], best_parts[1]]
    return [word]


def finnish_stems(text: str) -> list[str]:
    normalized = normalize_finnish_chars(normalize_whitespace(text))
    tokens = [t.lower() for t in _TOKEN_RE.findall(normalized)]
    if not tokens:
        return []
    expanded_tokens: list[str] = []
    for token in tokens:
        expanded_tokens.append(token)
        expanded_tokens.extend(decompose_finnish_compound(token))
    return _STEMMER.stemWords(expanded_tokens)


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
