from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _schedule(**overrides):
    data = {
        "enabled": False,
        "interval_hours": 24,
        "collection": "",
        "alert_email": "",
        "next_run_at": None,
        "last_due_run_at": None,
        "last_status": "not_configured",
        "last_error": "",
    }
    data.update(overrides)
    return data


def _eval_run(**overrides):
    data = {
        "id": 1,
        "run_id": "eval-launch",
        "collection": "HR-docs",
        "status": "completed",
        "total_cases": 2,
        "passed_cases": 2,
        "case_pass_rate": 1.0,
        "citation_recall": 1.0,
        "grounded_accuracy": 1.0,
        "no_answer_accuracy": 1.0,
        "passed": True,
        "report_json": {"passed": True, "summary": {"total_cases": 2}},
        "created_by": "admin",
        "started_at": "2026-05-26 08:00:00",
        "completed_at": "2026-05-26 08:00:01",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_launch_score_weights_statuses():
    from app.main import _launch_score

    score = _launch_score(
        [
            {"status": "ok"},
            {"status": "warning"},
            {"status": "error"},
            {"status": "ok"},
        ]
    )

    assert score == 63


def test_connector_catalog_marks_available_and_planned():
    from app.main import _connector_catalog_payload

    payload = _connector_catalog_payload()

    assert payload["available"] >= 3
    assert payload["planned"] >= 1
    assert {item["id"] for item in payload["connectors"]} >= {"confluence", "sharepoint", "generic-url"}


def test_launch_readiness_endpoint_returns_payload(client, monkeypatch):
    monkeypatch.setattr(
        "app.main._launch_readiness_payload",
        lambda db: {"score": 83, "checks": [], "metrics": {"active_eval_cases": 4}, "source_freshness": {}, "generated_at": "now"},
    )

    resp = client.get("/admin/launch/readiness")

    assert resp.status_code == 200
    assert resp.json()["score"] == 83
    assert resp.json()["metrics"]["active_eval_cases"] == 4


def test_demo_seed_endpoint_commits_seeded_workspace(client, mock_db_session, monkeypatch):
    monkeypatch.setattr("app.main._seed_demo_workspace", lambda db, current_user: {"created": {"chunks": 3}, "total_created": 3})
    monkeypatch.setattr("app.main._launch_readiness_payload", lambda db: {"score": 90, "checks": [], "metrics": {}})

    resp = client.post("/admin/launch/demo-seed")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_created"] == 3
    assert data["readiness"]["score"] == 90
    mock_db_session.commit.assert_called()


def test_update_eval_schedule_persists_setting(client, mock_db_session):
    from app.db import LaunchSetting

    query = MagicMock()
    query.filter.return_value.first.return_value = None
    mock_db_session.query.return_value = query

    resp = client.patch(
        "/admin/launch/eval-schedule",
        json={"enabled": True, "interval_hours": 12, "collection": "HR-docs", "alert_email": "ops@example.com"},
    )

    assert resp.status_code == 200
    schedule = resp.json()["schedule"]
    assert schedule["enabled"] is True
    assert schedule["interval_hours"] == 12
    assert schedule["collection"] == "HR-docs"
    assert schedule["next_run_at"]
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    setting = next(item for item in added if isinstance(item, LaunchSetting))
    assert setting.key == "eval_schedule"
    assert setting.value_json["alert_email"] == "ops@example.com"
    mock_db_session.commit.assert_called()


def test_run_due_eval_schedule_skips_when_disabled(client, monkeypatch):
    monkeypatch.setattr("app.main._eval_schedule_payload", lambda db: _schedule(enabled=False))

    resp = client.post("/admin/launch/eval-schedule/run-due")

    assert resp.status_code == 200
    assert resp.json()["skipped"] is True
    assert resp.json()["reason"] == "disabled"


def test_run_due_eval_schedule_persists_run_and_next_time(client, mock_db_session, monkeypatch):
    from app.db import LaunchSetting

    monkeypatch.setattr(
        "app.main._eval_schedule_payload",
        lambda db: _schedule(enabled=True, collection="HR-docs", next_run_at="2026-05-25 08:00:00"),
    )
    monkeypatch.setattr("app.main._create_evaluation_run", lambda **kwargs: _eval_run())
    query = MagicMock()
    query.filter.return_value.first.return_value = None
    mock_db_session.query.return_value = query

    resp = client.post("/admin/launch/eval-schedule/run-due?force=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["skipped"] is False
    assert data["run"]["run_id"] == "eval-launch"
    assert data["schedule"]["last_status"] == "passed"
    assert data["schedule"]["next_run_at"]
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    assert any(isinstance(item, LaunchSetting) and item.key == "eval_schedule" for item in added)
    mock_db_session.commit.assert_called()


def test_run_due_eval_schedule_skips_when_not_due(client, monkeypatch):
    monkeypatch.setattr(
        "app.main._eval_schedule_payload",
        lambda db: _schedule(enabled=True, next_run_at="2999-01-01 08:00:00"),
    )

    resp = client.post("/admin/launch/eval-schedule/run-due")

    assert resp.status_code == 200
    assert resp.json()["skipped"] is True
    assert resp.json()["reason"] == "not_due"


def test_run_due_eval_schedule_records_failure(client, mock_db_session, monkeypatch):
    from fastapi import HTTPException
    from app.db import LaunchSetting

    monkeypatch.setattr(
        "app.main._eval_schedule_payload",
        lambda db: _schedule(enabled=True, collection="HR-docs", next_run_at="2026-05-25 08:00:00"),
    )
    monkeypatch.setattr(
        "app.main._create_evaluation_run",
        lambda **kwargs: (_ for _ in ()).throw(HTTPException(status_code=400, detail="No active evaluation cases found")),
    )
    query = MagicMock()
    query.filter.return_value.first.return_value = None
    mock_db_session.query.return_value = query

    resp = client.post("/admin/launch/eval-schedule/run-due?force=true")

    assert resp.status_code == 200
    data = resp.json()
    assert data["skipped"] is False
    assert data["error"] == "No active evaluation cases found"
    assert data["schedule"]["last_status"] == "failed"
    assert data["schedule"]["last_error"] == "No active evaluation cases found"
    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    setting = next(item for item in added if isinstance(item, LaunchSetting))
    assert setting.value_json["last_status"] == "failed"
    assert setting.value_json["last_error"] == "No active evaluation cases found"
    assert "scheduler_poll_seconds" not in setting.value_json
    mock_db_session.commit.assert_called()


def test_eval_scheduler_tick_commits_due_run(monkeypatch):
    from app.main import _run_eval_scheduler_tick

    db = MagicMock()
    monkeypatch.setattr(
        "app.main._run_due_eval_schedule_job",
        lambda **kwargs: {"skipped": False, "run": {"run_id": "eval-auto"}, "schedule": {"last_status": "passed"}},
    )

    result = _run_eval_scheduler_tick(db_factory=lambda: db)

    assert result["run"]["run_id"] == "eval-auto"
    db.commit.assert_called_once()
    db.close.assert_called_once()


def test_eval_scheduler_tick_does_not_commit_skipped_run(monkeypatch):
    from app.main import _run_eval_scheduler_tick

    db = MagicMock()
    monkeypatch.setattr(
        "app.main._run_due_eval_schedule_job",
        lambda **kwargs: {"skipped": True, "reason": "not_due"},
    )

    result = _run_eval_scheduler_tick(db_factory=lambda: db)

    assert result["reason"] == "not_due"
    db.commit.assert_not_called()
    db.close.assert_called_once()
