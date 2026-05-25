from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _review(**overrides):
    data = {
        "id": 7,
        "session_id": "abc123",
        "collection": "HR-docs",
        "question": "How many annual leave days?",
        "answer_excerpt": "Employees receive 25 annual leave days.",
        "rating": "needs_review",
        "reason": "Verify policy version.",
        "language": "en",
        "citation_count": 1,
        "citations_json": [{"document": "HR-policy.pdf", "page": 2, "chunk_id": "hr-policy-p2"}],
        "source_confidence": 0.92,
        "confidence_label": "high",
        "answer_quality_json": {"outcome": "grounded"},
        "status": "open",
        "reviewer_note": "",
        "created_by": "viewer",
        "resolved_by": None,
        "promoted_eval_case_id": None,
        "created_at": "2026-05-25 12:00:00",
        "updated_at": "2026-05-25 12:00:00",
        "resolved_at": None,
        "promoted_to_eval_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _eval_case(**overrides):
    data = {
        "id": 11,
        "case_id": "review-7",
        "review_id": 7,
        "language": "en",
        "collection": "HR-docs",
        "question": "How many annual leave days?",
        "expectation": "answer",
        "required_citations_json": [{"document": "HR-policy.pdf", "page": 2, "chunk_id": "hr-policy-p2"}],
        "notes_json": {"source": "answer_review", "rating": "needs_review"},
        "status": "active",
        "created_by": "admin",
        "created_at": "2026-05-25 12:10:00",
        "updated_at": "2026-05-25 12:10:00",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _eval_report(passed=True):
    return {
        "passed": passed,
        "failures": [] if passed else ["case_pass_rate"],
        "thresholds": {
            "min_citation_recall": 0.85,
            "min_no_answer_accuracy": 0.95,
            "min_grounded_accuracy": 0.85,
            "min_case_pass_rate": 0.85,
        },
        "summary": {
            "total_cases": 1,
            "passed_cases": 1 if passed else 0,
            "missing_predictions": 0,
            "case_pass_rate": 1.0 if passed else 0.0,
            "answer_cases": 1,
            "no_answer_cases": 0,
            "grounded_accuracy": 1.0 if passed else 0.0,
            "no_answer_accuracy": 1.0,
            "citation_recall": 1.0 if passed else 0.0,
            "required_citations": 1,
            "matched_required_citations": 1 if passed else 0,
        },
        "by_language": [],
        "by_collection": [],
        "cases": [
            {
                "case_id": "review-7",
                "language": "en",
                "collection": "HR-docs",
                "expectation": "answer",
                "prediction_outcome": "grounded" if passed else "no_context",
                "required_citations": 1,
                "matched_required_citations": 1 if passed else 0,
                "retrieved_citations": 1 if passed else 0,
                "citation_recall": 1.0 if passed else 0.0,
                "citation_precision": 1.0 if passed else 0.0,
                "no_answer_correct": False,
                "grounded_correct": passed,
                "passed": passed,
                "missing_prediction": False,
            }
        ],
        "predictions": [
            {
                "case_id": "review-7",
                "outcome": "grounded" if passed else "no_context",
                "citations": [{"document": "HR-policy.pdf", "page": 2}] if passed else [],
                "retriever": "live_retrieval",
            }
        ],
    }


def _eval_run(**overrides):
    data = {
        "id": 21,
        "run_id": "eval-abc123",
        "collection": "HR-docs",
        "status": "completed",
        "total_cases": 1,
        "passed_cases": 1,
        "case_pass_rate": 1.0,
        "citation_recall": 1.0,
        "grounded_accuracy": 1.0,
        "no_answer_accuracy": 1.0,
        "passed": True,
        "report_json": _eval_report(True),
        "created_by": "admin",
        "started_at": "2026-05-25 12:15:00",
        "completed_at": "2026-05-25 12:15:01",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_review_summary_prioritizes_open_collection_counts():
    from app.main import _answer_review_summary

    summary = _answer_review_summary(
        [
            _review(collection="HR-docs", status="open"),
            _review(collection="HR-docs", status="resolved"),
            _review(collection="Legal-docs", status="open", rating="not_helpful"),
        ]
    )

    assert summary["total"] == 3
    assert summary["open"] == 2
    assert summary["resolved"] == 1
    assert summary["needs_review"] == 3
    assert summary["resolution_rate"] == 33
    assert summary["by_collection"][0]["open"] == 1


def test_admin_reviews_lists_open_reviews(client, mock_db_session):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.offset.return_value = query
    query.count.return_value = 1
    query.all.return_value = [_review()]
    mock_db_session.query.return_value = query

    resp = client.get("/admin/reviews?status=open")

    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["total"] == 1
    assert data["reviews"][0]["id"] == 7
    assert data["reviews"][0]["status"] == "open"
    assert data["summary"]["open"] == 1


def test_update_review_resolves_and_audits(client, mock_db_session):
    row = _review()
    mock_db_session.query.return_value.filter.return_value.first.return_value = row

    resp = client.patch(
        "/admin/reviews/7",
        json={"status": "resolved", "reviewer_note": "Confirmed with HR owner."},
    )

    assert resp.status_code == 200
    assert row.status == "resolved"
    assert row.reviewer_note == "Confirmed with HR owner."
    assert row.resolved_by == "admin"
    assert row.resolved_at is not None
    mock_db_session.commit.assert_called()


def test_build_eval_case_from_review_captures_required_citations():
    from app.main import _build_eval_case_from_review

    review = _review(
        citations_json=[
            {"document": "HR-policy.pdf", "page": 2, "chunk_id": "hr-policy-p2", "relevance": 0.91},
            {"document": "Benefits.pdf", "page": "", "chunk_id": "", "relevance": 0.44},
            {"page": 9},
        ]
    )

    eval_case = _build_eval_case_from_review(review, SimpleNamespace(username="admin"))

    assert eval_case.case_id == "review-7"
    assert eval_case.collection == "HR-docs"
    assert eval_case.required_citations_json == [
        {"document": "HR-policy.pdf", "page": 2, "chunk_id": "hr-policy-p2"},
        {"document": "Benefits.pdf"},
    ]
    assert eval_case.notes_json["source"] == "answer_review"
    assert eval_case.notes_json["answer_excerpt"] == "Employees receive 25 annual leave days."


def test_promote_review_to_eval_creates_case_and_marks_review(client, mock_db_session):
    from app.db import EvaluationCase

    row = _review()
    review_query = MagicMock()
    review_query.filter.return_value.first.return_value = row
    eval_query = MagicMock()
    eval_query.filter.return_value.first.return_value = None
    mock_db_session.query.side_effect = [review_query, eval_query]

    resp = client.post("/admin/reviews/7/promote-eval")

    assert resp.status_code == 200
    data = resp.json()
    assert data["eval_case"]["case_id"] == "review-7"
    assert data["eval_case"]["required_citations"] == [
        {"document": "HR-policy.pdf", "page": 2, "chunk_id": "hr-policy-p2"}
    ]
    assert data["review"]["promoted_eval_case_id"] == "review-7"
    assert row.promoted_eval_case_id == "review-7"
    assert row.promoted_to_eval_at is not None
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    assert any(isinstance(item, EvaluationCase) and item.case_id == "review-7" for item in added)
    mock_db_session.commit.assert_called()


def test_export_eval_cases_returns_golden_case_payload(client, mock_db_session):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [_eval_case()]
    mock_db_session.query.return_value = query

    resp = client.get("/admin/eval-cases/export?collection=HR-docs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == 1
    assert data["cases"] == [
        {
            "id": "review-7",
            "language": "en",
            "collection": "HR-docs",
            "question": "How many annual leave days?",
            "expectation": "answer",
            "required_citations": [{"document": "HR-policy.pdf", "page": 2, "chunk_id": "hr-policy-p2"}],
            "notes": {"source": "answer_review", "rating": "needs_review"},
        }
    ]


def test_run_promoted_eval_cases_scores_live_retrieval(monkeypatch, mock_db_session):
    from app.main import _run_promoted_eval_cases

    monkeypatch.setattr(
        "app.main._retrieve_context",
        lambda question, collection, language, current_user, db: [
            {
                "id": "hr-policy-p2",
                "document_name": "HR-policy.pdf",
                "page": 2,
                "content": "Employees receive 25 annual leave days.",
                "search_text": "annual leave 25 days",
                "score": 0.91,
            }
        ],
    )
    monkeypatch.setattr("app.main._source_freshness_by_document", lambda db, collection, rows: {})

    report = _run_promoted_eval_cases([_eval_case()], SimpleNamespace(username="admin", is_admin=True), mock_db_session)

    assert report["passed"] is True
    assert report["summary"]["case_pass_rate"] == 1.0
    assert report["predictions"][0]["retriever"] == "live_retrieval"
    assert report["predictions"][0]["citations"][0]["document"] == "HR-policy.pdf"


def test_run_eval_cases_persists_completed_run(client, mock_db_session, monkeypatch):
    from app.db import EvaluationRun

    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [_eval_case()]
    mock_db_session.query.return_value = query
    monkeypatch.setattr("app.main._run_promoted_eval_cases", lambda rows, current_user, db: _eval_report(True))

    resp = client.post("/admin/eval-runs?collection=HR-docs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run"]["collection"] == "HR-docs"
    assert data["run"]["passed"] is True
    assert data["run"]["case_pass_rate"] == 1.0
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    run = next(item for item in added if isinstance(item, EvaluationRun))
    assert run.total_cases == 1
    assert run.report_json["predictions"][0]["retriever"] == "live_retrieval"
    mock_db_session.commit.assert_called()


def test_run_eval_cases_rejects_empty_case_set(client, mock_db_session):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = []
    mock_db_session.query.return_value = query

    resp = client.post("/admin/eval-runs?collection=Missing")

    assert resp.status_code == 400
    assert "No active evaluation cases" in resp.json()["detail"]


def test_list_eval_runs_returns_latest_summary(client, mock_db_session):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [
        _eval_run(run_id="eval-new", case_pass_rate=1.0, passed=True),
        _eval_run(run_id="eval-old", case_pass_rate=0.0, citation_recall=0.0, passed=False, report_json=_eval_report(False)),
    ]
    mock_db_session.query.return_value = query

    resp = client.get("/admin/eval-runs?collection=HR-docs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"]["latest"]["run_id"] == "eval-new"
    assert data["summary"]["passing_runs"] == 1
    assert [item["run_id"] for item in data["summary"]["trend"]] == ["eval-old", "eval-new"]
