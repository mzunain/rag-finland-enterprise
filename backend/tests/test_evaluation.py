from __future__ import annotations

import json
from pathlib import Path

from app.evaluation import evaluate_retrieval, generate_predictions, main


def _cases():
    return [
        {
            "id": "answer-1",
            "language": "en",
            "collection": "HR-docs",
            "expectation": "answer",
            "required_citations": [{"document": "policy.pdf", "page": 2}],
        },
        {
            "id": "no-answer-1",
            "language": "fi",
            "collection": "HR-docs",
            "expectation": "no_answer",
            "required_citations": [],
        },
    ]


def _eval_fixture(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "evals" / name


def test_evaluate_retrieval_passes_grounded_and_no_answer_cases():
    report = evaluate_retrieval(
        _cases(),
        [
            {"case_id": "answer-1", "outcome": "grounded", "citations": [{"document": "policy.pdf", "page": 2}]},
            {"case_id": "no-answer-1", "outcome": "no_context", "citations": []},
        ],
        thresholds={
            "min_citation_recall": 1.0,
            "min_no_answer_accuracy": 1.0,
            "min_grounded_accuracy": 1.0,
            "min_case_pass_rate": 1.0,
        },
    )

    assert report["passed"] is True
    assert report["summary"]["citation_recall"] == 1.0
    assert report["summary"]["no_answer_accuracy"] == 1.0
    assert report["by_language"][0]["value"] == "en"


def test_evaluate_retrieval_fails_missing_required_citation():
    report = evaluate_retrieval(
        _cases(),
        [
            {"case_id": "answer-1", "outcome": "grounded", "citations": [{"document": "other.pdf", "page": 9}]},
            {"case_id": "no-answer-1", "outcome": "no_context", "citations": []},
        ],
        thresholds={
            "min_citation_recall": 1.0,
            "min_no_answer_accuracy": 1.0,
            "min_grounded_accuracy": 1.0,
            "min_case_pass_rate": 1.0,
        },
    )

    assert report["passed"] is False
    assert "citation_recall" in report["failures"]
    assert report["cases"][0]["matched_required_citations"] == 0


def test_evaluate_retrieval_fails_no_answer_with_citations():
    report = evaluate_retrieval(
        _cases(),
        [
            {"case_id": "answer-1", "outcome": "grounded", "citations": [{"document": "policy.pdf", "page": 2}]},
            {"case_id": "no-answer-1", "outcome": "grounded", "citations": [{"document": "policy.pdf", "page": 3}]},
        ],
        thresholds={
            "min_citation_recall": 1.0,
            "min_no_answer_accuracy": 1.0,
            "min_grounded_accuracy": 1.0,
            "min_case_pass_rate": 1.0,
        },
    )

    assert report["passed"] is False
    assert "no_answer_accuracy" in report["failures"]
    assert report["summary"]["no_answer_accuracy"] == 0.0


def test_evaluation_cli_exits_nonzero_on_threshold_failure(tmp_path):
    cases_path = tmp_path / "cases.json"
    predictions_path = tmp_path / "predictions.json"
    cases_path.write_text(json.dumps({"cases": _cases()}), encoding="utf-8")
    predictions_path.write_text(
        json.dumps(
            {
                "predictions": [
                    {"case_id": "answer-1", "outcome": "grounded", "citations": [{"document": "other.pdf", "page": 2}]},
                    {"case_id": "no-answer-1", "outcome": "no_context", "citations": []},
                ]
            }
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "--cases",
            str(cases_path),
            "--predictions",
            str(predictions_path),
            "--min-citation-recall",
            "1.0",
        ]
    )

    assert code == 1


def test_generate_predictions_from_seed_corpus_passes_golden_cases():
    cases = json.loads(_eval_fixture("retrieval_golden.json").read_text(encoding="utf-8"))["cases"]
    corpus = json.loads(_eval_fixture("seed_corpus.json").read_text(encoding="utf-8"))["chunks"]

    predictions = generate_predictions(cases, corpus)
    report = evaluate_retrieval(
        cases,
        predictions,
        thresholds={
            "min_citation_recall": 1.0,
            "min_no_answer_accuracy": 1.0,
            "min_grounded_accuracy": 1.0,
            "min_case_pass_rate": 1.0,
        },
    )

    assert report["passed"] is True
    assert report["summary"]["passed_cases"] == len(cases)
    assert next(item for item in predictions if item["case_id"] == "hr-en-cafeteria-menu")["citations"] == []


def test_generate_predictions_marks_no_answer_when_score_below_threshold():
    predictions = generate_predictions(
        [
            {
                "id": "missing-context",
                "collection": "HR-docs",
                "question": "What is tomorrow's cafeteria menu?",
                "expectation": "no_answer",
                "required_citations": [],
            }
        ],
        [
            {
                "collection": "HR-docs",
                "document": "policy.pdf",
                "page": 1,
                "content": "Annual leave, payroll, onboarding, and security training are covered in this policy.",
            }
        ],
    )

    assert predictions == [
        {
            "case_id": "missing-context",
            "outcome": "no_context",
            "citations": [],
            "retriever": "seeded_lexical",
        }
    ]


def test_evaluation_cli_scores_seeded_corpus_and_writes_predictions(tmp_path):
    predictions_path = tmp_path / "generated_predictions.json"

    code = main(
        [
            "--cases",
            str(_eval_fixture("retrieval_golden.json")),
            "--corpus",
            str(_eval_fixture("seed_corpus.json")),
            "--write-predictions",
            str(predictions_path),
            "--min-citation-recall",
            "1.0",
            "--min-no-answer-accuracy",
            "1.0",
            "--min-grounded-accuracy",
            "1.0",
            "--min-case-pass-rate",
            "1.0",
        ]
    )

    assert code == 0
    payload = json.loads(predictions_path.read_text(encoding="utf-8"))
    assert len(payload["predictions"]) == 5
    assert payload["predictions"][0]["retriever"] == "seeded_lexical"
