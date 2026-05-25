from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from app.finnish import finnish_search_text, normalize_finnish_chars, stem_overlap_ratio

NO_ANSWER_OUTCOMES = {"no_answer", "no_context", "unanswerable"}
ANSWER_OUTCOMES = {"answer", "answered", "grounded"}
DEFAULT_GENERATION_TOP_K = 3
DEFAULT_GENERATION_MIN_SCORE = 0.34

_TOKEN_RE = re.compile(r"[A-Za-zÅÄÖåäö0-9]+", re.UNICODE)
_STOP_WORDS = {
    "a",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "do",
    "does",
    "for",
    "from",
    "how",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "which",
    "who",
    "with",
    "kuinka",
    "mita",
    "mikä",
    "mika",
    "mitka",
    "monta",
    "on",
    "ovat",
    "ja",
    "tai",
    "vilka",
    "vad",
    "vem",
    "for",
    "för",
}

DEFAULT_THRESHOLDS = {
    "min_citation_recall": 0.85,
    "min_no_answer_accuracy": 0.95,
    "min_grounded_accuracy": 0.85,
    "min_case_pass_rate": 0.85,
}


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_doc(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_page(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _generic_tokens(text: Any) -> set[str]:
    normalized = normalize_finnish_chars(str(text or "").lower())
    return {
        token
        for token in _TOKEN_RE.findall(normalized)
        if len(token) > 1 and token not in _STOP_WORDS
    }


def _chunk_text(chunk: dict) -> str:
    fields = (
        "title",
        "heading",
        "document",
        "document_title",
        "content",
        "text",
        "body",
        "search_text",
    )
    return " ".join(str(chunk.get(field) or "") for field in fields)


def _chunk_search_text(chunk: dict) -> str:
    search_text = str(chunk.get("search_text") or "").strip()
    if search_text:
        return search_text
    return finnish_search_text(_chunk_text(chunk))


def _case_collection(case: dict) -> str:
    return str(case.get("collection") or "").strip().lower()


def _chunk_collection(chunk: dict) -> str:
    return str(chunk.get("collection") or "").strip().lower()


def score_seeded_chunk(case: dict, chunk: dict) -> float:
    question = str(case.get("question") or "")
    q_tokens = _generic_tokens(question)
    c_tokens = _generic_tokens(_chunk_text(chunk))
    generic_score = len(q_tokens.intersection(c_tokens)) / len(q_tokens) if q_tokens else 0.0
    language = str(case.get("language") or "").strip().lower()
    stem_score = stem_overlap_ratio(question, _chunk_search_text(chunk)) if language in {"fi", "fin", "finnish"} else 0.0
    return round(max(generic_score, stem_score), 6)


def _citation_from_chunk(chunk: dict, relevance: float) -> dict:
    citation: dict[str, Any] = {
        "document": chunk.get("document") or chunk.get("source") or chunk.get("path") or "unknown",
        "relevance": round(relevance, 4),
    }
    page = _normalize_page(chunk.get("page"))
    if page is not None:
        citation["page"] = page
    chunk_id = chunk.get("chunk_id") or chunk.get("id")
    if chunk_id:
        citation["chunk_id"] = chunk_id
    return citation


def _case_matches_chunk_collection(case: dict, chunk: dict) -> bool:
    collection = _case_collection(case)
    if not collection:
        return True
    return collection == _chunk_collection(chunk)


def generate_predictions(
    cases: list[dict],
    corpus: list[dict],
    *,
    top_k: int = DEFAULT_GENERATION_TOP_K,
    min_score: float = DEFAULT_GENERATION_MIN_SCORE,
) -> list[dict]:
    predictions: list[dict] = []
    bounded_top_k = max(1, int(top_k))

    for case in cases:
        scored = []
        for chunk in corpus:
            if not isinstance(chunk, dict) or not _case_matches_chunk_collection(case, chunk):
                continue
            score = score_seeded_chunk(case, chunk)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("document") or ""),
                _normalize_page(item[1].get("page")) or 0,
                str(item[1].get("chunk_id") or item[1].get("id") or ""),
            )
        )
        selected = [(score, chunk) for score, chunk in scored if score >= min_score][:bounded_top_k]
        citations = [_citation_from_chunk(chunk, score) for score, chunk in selected]

        predictions.append(
            {
                "case_id": case.get("id"),
                "outcome": "grounded" if citations else "no_context",
                "citations": citations,
                "retriever": "seeded_lexical",
            }
        )

    return predictions


def _expected_matches_citation(expected: dict, citation: dict) -> bool:
    if _normalize_doc(expected.get("document")) != _normalize_doc(citation.get("document")):
        return False
    expected_page = _normalize_page(expected.get("page"))
    if expected_page is None:
        return True
    return expected_page == _normalize_page(citation.get("page"))


def _prediction_outcome(prediction: dict) -> str:
    outcome = str(prediction.get("outcome") or "").strip().lower()
    if outcome:
        return outcome
    if "answerable" in prediction:
        return "grounded" if bool(prediction.get("answerable")) else "no_context"
    return "grounded" if prediction.get("citations") else "no_context"


def evaluate_case(case: dict, prediction: dict | None) -> dict:
    prediction = prediction or {}
    citations = prediction.get("citations") or []
    if not isinstance(citations, list):
        citations = []

    expected = case.get("required_citations") or []
    if not isinstance(expected, list):
        expected = []

    expectation = str(case.get("expectation") or "answer").strip().lower()
    outcome = _prediction_outcome(prediction)
    matched_required = [
        item
        for item in expected
        if isinstance(item, dict) and any(_expected_matches_citation(item, citation) for citation in citations if isinstance(citation, dict))
    ]
    matched_retrieved = [
        citation
        for citation in citations
        if isinstance(citation, dict) and any(_expected_matches_citation(item, citation) for item in expected if isinstance(item, dict))
    ]

    required_count = len(expected)
    citation_recall = len(matched_required) / required_count if required_count else 1.0
    citation_precision = len(matched_retrieved) / len(citations) if citations else (1.0 if not required_count else 0.0)
    no_answer_expected = expectation in NO_ANSWER_OUTCOMES
    no_answer_correct = no_answer_expected and outcome in NO_ANSWER_OUTCOMES and not citations
    grounded_correct = not no_answer_expected and outcome in ANSWER_OUTCOMES and bool(citations)
    case_passed = no_answer_correct or (grounded_correct and citation_recall >= 1.0)

    return {
        "case_id": case.get("id"),
        "language": case.get("language") or "unknown",
        "collection": case.get("collection") or "unknown",
        "expectation": "no_answer" if no_answer_expected else "answer",
        "prediction_outcome": outcome,
        "required_citations": required_count,
        "matched_required_citations": len(matched_required),
        "retrieved_citations": len(citations),
        "citation_recall": round(citation_recall, 4),
        "citation_precision": round(citation_precision, 4),
        "no_answer_correct": no_answer_correct,
        "grounded_correct": grounded_correct,
        "passed": case_passed,
        "missing_prediction": not bool(prediction),
    }


def _aggregate(case_results: list[dict]) -> dict:
    total = len(case_results)
    answer_cases = [row for row in case_results if row["expectation"] == "answer"]
    no_answer_cases = [row for row in case_results if row["expectation"] == "no_answer"]
    required = sum(row["required_citations"] for row in case_results)
    matched = sum(row["matched_required_citations"] for row in case_results)

    return {
        "total_cases": total,
        "passed_cases": sum(1 for row in case_results if row["passed"]),
        "missing_predictions": sum(1 for row in case_results if row["missing_prediction"]),
        "case_pass_rate": round(sum(1 for row in case_results if row["passed"]) / total, 4) if total else 0.0,
        "answer_cases": len(answer_cases),
        "no_answer_cases": len(no_answer_cases),
        "grounded_accuracy": round(sum(1 for row in answer_cases if row["grounded_correct"]) / len(answer_cases), 4) if answer_cases else 1.0,
        "no_answer_accuracy": round(sum(1 for row in no_answer_cases if row["no_answer_correct"]) / len(no_answer_cases), 4) if no_answer_cases else 1.0,
        "citation_recall": round(matched / required, 4) if required else 1.0,
        "required_citations": required,
        "matched_required_citations": matched,
    }


def _by_dimension(case_results: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for row in case_results:
        buckets.setdefault(str(row.get(key) or "unknown"), []).append(row)
    return [{"value": value, **_aggregate(rows)} for value, rows in sorted(buckets.items())]


def evaluate_retrieval(cases: list[dict], predictions: list[dict], thresholds: dict | None = None) -> dict:
    prediction_by_id = {item.get("case_id"): item for item in predictions if isinstance(item, dict)}
    case_results = [evaluate_case(case, prediction_by_id.get(case.get("id"))) for case in cases if isinstance(case, dict)]
    summary = _aggregate(case_results)
    active_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    failures = []
    if summary["citation_recall"] < active_thresholds["min_citation_recall"]:
        failures.append("citation_recall")
    if summary["no_answer_accuracy"] < active_thresholds["min_no_answer_accuracy"]:
        failures.append("no_answer_accuracy")
    if summary["grounded_accuracy"] < active_thresholds["min_grounded_accuracy"]:
        failures.append("grounded_accuracy")
    if summary["case_pass_rate"] < active_thresholds["min_case_pass_rate"]:
        failures.append("case_pass_rate")
    if summary["missing_predictions"]:
        failures.append("missing_predictions")

    return {
        "passed": not failures,
        "failures": failures,
        "thresholds": active_thresholds,
        "summary": summary,
        "by_language": _by_dimension(case_results, "language"),
        "by_collection": _by_dimension(case_results, "collection"),
        "cases": case_results,
    }


def _load_cases(path: str | Path) -> list[dict]:
    payload = load_json(path)
    if isinstance(payload, dict):
        payload = payload.get("cases", [])
    if not isinstance(payload, list):
        raise ValueError("Evaluation cases must be a JSON array or an object with a 'cases' array")
    return payload


def _load_predictions(path: str | Path) -> list[dict]:
    payload = load_json(path)
    if isinstance(payload, dict):
        payload = payload.get("predictions", [])
    if not isinstance(payload, list):
        raise ValueError("Predictions must be a JSON array or an object with a 'predictions' array")
    return payload


def _load_corpus(path: str | Path) -> list[dict]:
    payload = load_json(path)
    if isinstance(payload, dict):
        payload = payload.get("chunks", [])
    if not isinstance(payload, list):
        raise ValueError("Seed corpus must be a JSON array or an object with a 'chunks' array")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score RAG retrieval predictions against golden cases.")
    parser.add_argument("--cases", required=True, help="Path to retrieval golden cases JSON")
    prediction_source = parser.add_mutually_exclusive_group(required=True)
    prediction_source.add_argument("--predictions", help="Path to retrieval predictions JSON")
    prediction_source.add_argument("--corpus", help="Path to seeded corpus JSON used to generate predictions")
    parser.add_argument("--write-predictions", help="Write generated predictions to this JSON path")
    parser.add_argument("--top-k", type=int, default=DEFAULT_GENERATION_TOP_K, help="Maximum generated citations per case")
    parser.add_argument(
        "--min-relevance",
        type=float,
        default=DEFAULT_GENERATION_MIN_SCORE,
        help="Minimum seeded retriever relevance required to cite a chunk",
    )
    parser.add_argument("--min-citation-recall", type=float, default=DEFAULT_THRESHOLDS["min_citation_recall"])
    parser.add_argument("--min-no-answer-accuracy", type=float, default=DEFAULT_THRESHOLDS["min_no_answer_accuracy"])
    parser.add_argument("--min-grounded-accuracy", type=float, default=DEFAULT_THRESHOLDS["min_grounded_accuracy"])
    parser.add_argument("--min-case-pass-rate", type=float, default=DEFAULT_THRESHOLDS["min_case_pass_rate"])
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases)
    if args.predictions:
        if args.write_predictions:
            parser.error("--write-predictions can only be used with --corpus")
        predictions = _load_predictions(args.predictions)
    else:
        predictions = generate_predictions(cases, _load_corpus(args.corpus), top_k=args.top_k, min_score=args.min_relevance)
        if args.write_predictions:
            output_path = Path(args.write_predictions)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps({"version": 1, "predictions": predictions}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    report = evaluate_retrieval(
        cases,
        predictions,
        thresholds={
            "min_citation_recall": args.min_citation_recall,
            "min_no_answer_accuracy": args.min_no_answer_accuracy,
            "min_grounded_accuracy": args.min_grounded_accuracy,
            "min_case_pass_rate": args.min_case_pass_rate,
        },
    )
    json.dump(report, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
