from __future__ import annotations


def test_create_collection_writes_audit_log(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    resp = client.post("/admin/collections", json={"name": "Finance-docs", "description": "Financial docs"})
    assert resp.status_code == 200

    entries = [call.args[0] for call in mock_db_session.add.call_args_list if call.args[0].__class__.__name__ == "AuditLog"]
    assert len(entries) == 1
    assert entries[0].action == "collection.create"
    assert entries[0].resource_type == "collection"
    assert entries[0].resource_id == "Finance-docs"


def test_delete_document_writes_audit_log(client, mock_db_session):
    mock_db_session.query.return_value.filter.return_value.delete.return_value = 3
    resp = client.delete("/admin/documents/payroll.pdf?collection=HR-docs")
    assert resp.status_code == 200

    entries = [call.args[0] for call in mock_db_session.add.call_args_list if call.args[0].__class__.__name__ == "AuditLog"]
    assert len(entries) == 1
    assert entries[0].action == "document.delete"
    assert entries[0].resource_type == "document"
    assert entries[0].resource_id == "payroll.pdf"
