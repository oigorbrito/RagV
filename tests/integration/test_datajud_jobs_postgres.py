from __future__ import annotations

import os
from uuid import uuid4

import httpx
import pytest

from app.api import app
from app.datajud_client import DataJudLookupResult
from app.datajud_enrichment import DataJudMetadata
from app.db import create_pool
from app.migrations import migrate
from app.worker import Worker, WorkerSettings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must name a disposable PostgreSQL database")
CNJ = "0000000-00.2024.8.26.0100"


async def _setup(monkeypatch):
    assert TEST_DATABASE_URL  # nosec B101
    await migrate(TEST_DATABASE_URL)
    pool = await create_pool(TEST_DATABASE_URL, min_size=1, max_size=4)
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE jobs, tenants RESTART IDENTITY CASCADE")
    tenants = [uuid4(), uuid4()]
    tokens = [f"datajud-{uuid4()}", f"datajud-{uuid4()}"]
    async with pool.acquire() as conn:
        for index, tenant_id in enumerate(tenants):
            await conn.execute("INSERT INTO tenants(id,name) VALUES($1,$2)", tenant_id, "DataJud tenant")
    monkeypatch.setattr(app.state, "bearer_tokens", dict(zip(tokens, tenants)), raising=False)
    monkeypatch.setattr(app.state, "pool", pool, raising=False)
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("DATAJUD_ENABLED", "true")
    monkeypatch.setenv("DATAJUD_AUTHORIZED_USE", "true")
    monkeypatch.delenv("DATAJUD_API_KEY", raising=False)
    return pool, tenants, tokens


def _worker(pool):
    return Worker(
        pool,
        WorkerSettings(
            database_url=TEST_DATABASE_URL,
            concurrency=1,
            heartbeat_interval_seconds=60,
            stale_after_seconds=120,
            task_timeout_seconds=30,
            reclaim_interval_seconds=60,
        ),
    )


@pytest.mark.asyncio
async def test_versioned_aliases_use_the_same_durable_job_contract(monkeypatch):
    pool, tenants, tokens = await _setup(monkeypatch)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            for index, path in enumerate((f"/processos/{CNJ}/datajud", f"/v1/processos/{CNJ}/datajud")):
                headers = {"Authorization": f"Bearer {tokens[0]}", "Idempotency-Key": f"alias-{index}"}
                submitted = await client.post(path, headers=headers)
                assert submitted.status_code == 202  # nosec B101
                status_path = path.replace("/datajud", f"/datajud/jobs/{submitted.json()['job_id']}")
                status = await client.get(status_path, headers={"Authorization": f"Bearer {tokens[0]}"})
                assert status.status_code == 202  # nosec B101
                assert status.json()["job_id"] == submitted.json()["job_id"]  # nosec B101
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_datajud_job_persists_result_is_idempotent_and_isolated(monkeypatch):
    pool, tenants, tokens = await _setup(monkeypatch)
    calls = []

    async def fake_lookup(*, code, secrecy_level, config):
        calls.append((code, secrecy_level))
        assert config.api_key == "worker-only-test-key"  # nosec B101
        return DataJudLookupResult(
            status="ok",
            metadata=DataJudMetadata(
                class_name="Procedimento de teste",
                class_code="123",
                subjects=({"code": "456", "name": "Assunto de teste"},),
                adjudicating_body="Vara de teste",
                county="Comarca de teste",
            ),
        )

    monkeypatch.setattr("app.datajud_tasks.lookup_datajud_metadata", fake_lookup)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first_headers = {"Authorization": f"Bearer {tokens[0]}", "Idempotency-Key": "request-1"}
            first = await client.post(f"/processes/{CNJ}/datajud", headers=first_headers)
            replay = await client.post(f"/processes/{CNJ}/datajud", headers=first_headers)
            assert first.status_code == replay.status_code == 202  # nosec B101
            assert first.json()["created"] is True and replay.json()["created"] is False  # nosec B101
            assert first.json()["job_id"] == replay.json()["job_id"]  # nosec B101
            assert "DATAJUD_API_KEY" not in os.environ  # nosec B101

            conflict = await client.post(
                "/processes/0000000-00.2024.8.26.0101/datajud",
                headers=first_headers,
            )
            assert conflict.status_code == 409  # nosec B101

            other = await client.post(
                f"/processes/{CNJ}/datajud",
                headers={"Authorization": f"Bearer {tokens[1]}", "Idempotency-Key": "request-1"},
            )
            assert other.status_code == 202  # nosec B101
            assert other.json()["job_id"] != first.json()["job_id"]  # nosec B101

            unknown = await client.post(
                f"/processes/{CNJ}/datajud",
                headers={"Authorization": "Bearer invalid", "Idempotency-Key": "request-2"},
            )
            assert unknown.status_code == 401  # nosec B101
            cross_tenant = await client.get(
                f"/processes/{CNJ}/datajud/jobs/{first.json()['job_id']}",
                headers={"Authorization": f"Bearer {tokens[1]}"},
            )
            assert cross_tenant.status_code == 404  # nosec B101
            pending = await client.get(
                f"/processes/{CNJ}/datajud/jobs/{first.json()['job_id']}",
                headers={"Authorization": f"Bearer {tokens[0]}"},
            )
            assert pending.status_code == 202  # nosec B101

            monkeypatch.setenv("DATAJUD_API_KEY", "worker-only-test-key")
            assert await _worker(pool).process_one() is True  # nosec B101
            completed = await client.get(
                f"/processes/{CNJ}/datajud/jobs/{first.json()['job_id']}",
                headers={"Authorization": f"Bearer {tokens[0]}"},
            )
            assert completed.status_code == 200  # nosec B101
            assert completed.json() == {  # nosec B101
                "code": CNJ,
                "source": "datajud",
                "court": "TJSP",
                "class_name": "Procedimento de teste",
                "adjudicating_body": "Vara de teste",
                "county": "Comarca de teste",
                "subjects": [{"code": "456", "name": "Assunto de teste"}],
                "parties": [],
            }
            assert len(calls) == 1  # nosec B101
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT status::text AS status, result FROM jobs WHERE id=$1", first.json()["job_id"])
            assert row and row["status"] == "completed" and row["result"]["status"] == "ok"  # nosec B101
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_missing_worker_credential_fails_closed_without_provider_call(monkeypatch):
    pool, tenants, tokens = await _setup(monkeypatch)
    calls = 0

    async def forbidden_lookup(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("provider adapter must not run without worker credentials")

    monkeypatch.setattr("app.datajud_tasks.lookup_datajud_metadata", forbidden_lookup)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            accepted = await client.post(
                f"/processes/{CNJ}/datajud",
                headers={"Authorization": f"Bearer {tokens[0]}", "Idempotency-Key": "missing-key"},
            )
            assert accepted.status_code == 202  # nosec B101
            assert await _worker(pool).process_one() is True  # nosec B101
            response = await client.get(
                f"/processes/{CNJ}/datajud/jobs/{accepted.json()['job_id']}",
                headers={"Authorization": f"Bearer {tokens[0]}"},
            )
            assert response.status_code == 502  # nosec B101
        async with pool.acquire() as conn:
            status = await conn.fetchval("SELECT status::text FROM jobs WHERE id=$1", accepted.json()["job_id"])
        assert status == "dead" and calls == 0  # nosec B101
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_provider_no_hit_and_failure_are_sanitized(monkeypatch):
    pool, tenants, tokens = await _setup(monkeypatch)
    monkeypatch.setenv("DATAJUD_API_KEY", "worker-only-test-key")
    outcomes = iter((DataJudLookupResult(status="not_found"), DataJudLookupResult(status="unavailable", error_code="secret-detail")))

    async def fake_lookup(**kwargs):
        return next(outcomes)

    monkeypatch.setattr("app.datajud_tasks.lookup_datajud_metadata", fake_lookup)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {tokens[0]}", "Idempotency-Key": "no-hit"}
            no_hit = await client.post(f"/processes/{CNJ}/datajud", headers=headers)
            assert no_hit.status_code == 202  # nosec B101
            assert await _worker(pool).process_one() is True  # nosec B101
            not_found = await client.get(
                f"/processes/{CNJ}/datajud/jobs/{no_hit.json()['job_id']}",
                headers={"Authorization": f"Bearer {tokens[0]}"},
            )
            assert not_found.status_code == 404  # nosec B101

            failure = await client.post(
                f"/processes/{CNJ}/datajud",
                headers={"Authorization": f"Bearer {tokens[0]}", "Idempotency-Key": "provider-error"},
            )
            assert failure.status_code == 202  # nosec B101
            assert await _worker(pool).process_one() is True  # nosec B101
            unavailable = await client.get(
                f"/processes/{CNJ}/datajud/jobs/{failure.json()['job_id']}",
                headers={"Authorization": f"Bearer {tokens[0]}"},
            )
            assert unavailable.status_code == 502  # nosec B101
            assert "secret-detail" not in unavailable.text  # nosec B101
    finally:
        await pool.close()
