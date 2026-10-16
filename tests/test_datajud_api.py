from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.datajud_client import DataJudLookupResult
from app.datajud_enrichment import DataJudMetadata


@pytest.mark.parametrize(
    "path",
    (
        "/processes/0000000-00.2024.8.26.0100/datajud",
        "/processos/0000000-00.2024.8.26.0100/datajud",
        "/v1/processos/0000000-00.2024.8.26.0100/datajud",
    ),
)
def test_datajud_success_serializes_only_modeled_metadata(monkeypatch, path: str) -> None:
    # Synthetic API-contract regression: replace the transport; no CNJ request is sent.
    monkeypatch.setenv("DATAJUD_ENABLED", "true")
    monkeypatch.setenv("DATAJUD_AUTHORIZED_USE", "true")
    monkeypatch.setenv("DATAJUD_API_KEY", "test-key-never-sent-to-network")

    lookup = AsyncMock(
        return_value=DataJudLookupResult(
            status="ok",
            metadata=DataJudMetadata(
                class_name="Procedimento de teste",
                class_code="123",
                subjects=({"code": "456", "name": "Assunto de teste"},),
                adjudicating_body="Vara de teste",
                county="Comarca de teste",
            ),
        )
    )
    monkeypatch.setattr("app.api.lookup_datajud_metadata", lookup)
    monkeypatch.setattr("app.api_v1.lookup_datajud_metadata", lookup)
    monkeypatch.setattr(
        app.state,
        "bearer_tokens",
        {"datajud-test-token": uuid4()},
        raising=False,
    )

    response = TestClient(app).get(
        path,
        headers={"Authorization": "Bearer datajud-test-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "code": "0000000-00.2024.8.26.0100",
        "source": "datajud",
        "class_name": "Procedimento de teste",
        "court": "TJSP",
        "adjudicating_body": "Vara de teste",
        "county": "Comarca de teste",
        "subjects": [{"code": "456", "name": "Assunto de teste"}],
        "parties": [],
    }
    lookup.assert_awaited_once()
