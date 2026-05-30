"""Story 5.C.3 — PIPL JSON data export lifecycle tests."""

from __future__ import annotations

import asyncio
import csv
import io
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from auth_service import data_export
from auth_service.models import AuditLog, DataExportRequest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def _phone() -> str:
    return f"+8613{uuid.uuid4().int % 10**10:010d}"


def _email() -> str:
    return f"export-{uuid.uuid4().hex[:10]}@example.com"


@pytest_asyncio.fixture(autouse=True)
async def _ensure_data_export_schema(engine: AsyncEngine) -> None:
    """Local DBs may predate Story 5.C.3; CI applies updated schema after merge."""
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS data_export_requests (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id_snapshot UUID NOT NULL,
                    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
                    format VARCHAR(16) NOT NULL DEFAULT 'json',
                    status VARCHAR(32) NOT NULL DEFAULT 'queued',
                    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sla_deadline_at TIMESTAMPTZ NOT NULL,
                    processing_started_at TIMESTAMPTZ NULL,
                    completed_at TIMESTAMPTZ NULL,
                    expires_at TIMESTAMPTZ NULL,
                    package_json JSONB NULL,
                    package_sha256 CHAR(64) NULL,
                    package_bytes INTEGER NULL,
                    download_url TEXT NULL,
                    last_error TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.table_constraints
                        WHERE table_name = 'data_export_requests'
                          AND constraint_name = 'ck_data_export_requests_format'
                    ) THEN
                        ALTER TABLE data_export_requests
                            DROP CONSTRAINT ck_data_export_requests_format;
                    END IF;
                END $$;
                """
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_data_export_requests_user_requested "
                "ON data_export_requests(user_id_snapshot, requested_at DESC)"
            )
        )
        await s.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_data_export_requests_queued "
                "ON data_export_requests(requested_at) WHERE status = 'queued'"
            )
        )
        await s.execute(
            text(
                "ALTER TABLE data_export_requests "
                "ADD CONSTRAINT ck_data_export_requests_format "
                "CHECK (format IN ('json', 'csv'))"
            )
        )
        await s.execute(text("DROP INDEX IF EXISTS uq_data_export_requests_inflight_json"))
        await s.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_data_export_requests_inflight_format "
                "ON data_export_requests(user_id_snapshot, format) "
                "WHERE format IN ('json', 'csv') AND status IN ('queued', 'processing')"
            )
        )
        await s.execute(text("DELETE FROM data_export_requests"))
        await s.execute(text("DELETE FROM outbox WHERE event_type LIKE 'data_export.%'"))
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS optimizations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    api_key_id UUID NOT NULL,
                    task_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'queued',
                    input_payload JSONB NOT NULL,
                    solution JSONB NULL,
                    objective NUMERIC NULL,
                    model_version JSONB NULL,
                    error JSONB NULL,
                    solve_seconds NUMERIC NULL,
                    idempotency_key VARCHAR(255) NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    api_key_id UUID NOT NULL,
                    family VARCHAR(64) NOT NULL,
                    status VARCHAR(50) NOT NULL DEFAULT 'queued',
                    input_payload JSONB NOT NULL,
                    prediction JSONB NULL,
                    drift_score NUMERIC NULL,
                    model_version JSONB NULL,
                    error JSONB NULL,
                    predict_seconds NUMERIC NULL,
                    idempotency_key VARCHAR(255) NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS saga_instances (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    saga_type VARCHAR(64) NOT NULL,
                    current_state VARCHAR(32) NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    idempotency_key VARCHAR(255) NULL,
                    amount NUMERIC(12, 4) NULL,
                    retries INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NULL,
                    payload_ref JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS credit_transactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    saga_id UUID NULL REFERENCES saga_instances(id) ON DELETE SET NULL,
                    amount NUMERIC(12, 4) NOT NULL,
                    kind VARCHAR(32) NOT NULL,
                    bucket VARCHAR(32) NOT NULL DEFAULT 'monthly',
                    currency VARCHAR(3) NOT NULL DEFAULT 'CNY',
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS billing_subscriptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    plan_code VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'active',
                    current_period_start TIMESTAMPTZ NOT NULL,
                    current_period_end TIMESTAMPTZ NOT NULL,
                    last_refilled_period_start TIMESTAMPTZ NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await s.commit()


async def _signup(http_client: AsyncClient) -> tuple[uuid.UUID, str]:
    r = await http_client.post(
        "/v1/auth/signup",
        json={"phone": _phone(), "email": _email(), "age_years": 18},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return uuid.UUID(body["user_id"]), body["jwt_access"]


async def _create_api_key(http_client: AsyncClient, jwt: str) -> tuple[uuid.UUID, str]:
    r = await http_client.post(
        "/v1/auth/api_keys",
        json={"label": "export-key", "scope": ["optimize:write", "billing:read"]},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return uuid.UUID(body["id"]), body["api_key"]


async def _insert_cross_domain_rows(
    engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        saga_id = uuid.uuid4()
        await s.execute(
            text(
                """
                INSERT INTO optimizations
                    (id, user_id, api_key_id, task_type, status, input_payload, solution, error,
                     idempotency_key)
                VALUES
                    (:id, :uid, :kid, 'lp', 'completed',
                     CAST(:input_payload AS jsonb), CAST(:solution AS jsonb), NULL,
                     '=SUM(1,1)')
                """
            ),
            {
                "id": uuid.uuid4(),
                "uid": user_id,
                "kid": api_key_id,
                "input_payload": '{"objective":"min","authorization":"Bearer secret-token"}',
                "solution": '{"x":1,"nested":{"api_key":"sk-secret-value"}}',
            },
        )
        await s.execute(
            text(
                """
                INSERT INTO predictions
                    (id, user_id, api_key_id, family, status, input_payload, prediction)
                VALUES
                    (:id, :uid, :kid, 'chronos', 'completed',
                     CAST(:input_payload AS jsonb), CAST(:prediction AS jsonb))
                """
            ),
            {
                "id": uuid.uuid4(),
                "uid": user_id,
                "kid": api_key_id,
                "input_payload": '{"series":[1,2,3],"jwt_access":"jwt-secret"}',
                "prediction": '{"p50":[2,3,4]}',
            },
        )
        await s.execute(
            text(
                """
                INSERT INTO saga_instances
                    (id, saga_type, current_state, user_id, amount, payload_ref)
                VALUES
                    (:sid, 'solve_charge', 'charged', :uid, 10.00,
                     CAST(:payload_ref AS jsonb))
                """
            ),
            {
                "sid": saga_id,
                "uid": user_id,
                "payload_ref": '{"optimization_id":"opt-1","request_body_hash":"hash-secret"}',
            },
        )
        await s.execute(
            text(
                """
                INSERT INTO credit_transactions
                    (id, user_id, saga_id, amount, kind, metadata)
                VALUES
                    (:id, :uid, :sid, -10.00, 'charge', CAST(:metadata AS jsonb))
                """
            ),
            {
                "id": uuid.uuid4(),
                "uid": user_id,
                "sid": saga_id,
                "metadata": '{"visible":"ok","key_hash":"hash-secret"}',
            },
        )
        await s.commit()


async def _insert_csv_edge_rows(
    engine: AsyncEngine,
    *,
    user_id: uuid.UUID,
    api_key_id: uuid.UUID,
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                INSERT INTO optimizations
                    (id, user_id, api_key_id, task_type, status, input_payload, solution, error)
                VALUES
                    (:id, :uid, :kid, 'lp', 'completed',
                     CAST(:input_payload AS jsonb), CAST(:solution AS jsonb), NULL)
                """
            ),
            {
                "id": uuid.uuid4(),
                "uid": user_id,
                "kid": api_key_id,
                "input_payload": '{"note":"=SUM(1,1)","safe":"visible"}',
                "solution": '{"nested":{"authorization":"Bearer secret-token","value":"@cmd"}}',
            },
        )
        await s.commit()


def _zip_text_entries(content: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name).decode("utf-8") for name in sorted(archive.namelist())}


async def test_data_export_request_is_idempotent(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)

    first = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    second = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "queued"
    assert first.json()["format"] == "json"
    assert first.json()["sla_deadline_at"] is not None

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        audit_count = (
            await s.execute(
                text(
                    "SELECT count(*) FROM audit_logs "
                    "WHERE user_id = :uid AND action = 'data_export.requested'"
                ),
                {"uid": user_id},
            )
        ).scalar_one()
        outbox_count = (
            await s.execute(
                text("SELECT count(*) FROM outbox WHERE event_type = 'data_export.requested'")
            )
        ).scalar_one()
    assert audit_count == 1
    assert outbox_count == 1


async def test_csv_data_export_request_is_format_scoped_and_idempotent(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)

    default_json = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    csv_first = await http_client.post(
        "/v1/auth/data-exports",
        json={"format": "csv"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    csv_second = await http_client.post(
        "/v1/auth/data-exports",
        json={"format": "csv"},
        headers={"Authorization": f"Bearer {jwt}"},
    )

    assert default_json.status_code == 200, default_json.text
    assert csv_first.status_code == 200, csv_first.text
    assert csv_second.status_code == 200, csv_second.text
    assert default_json.json()["format"] == "json"
    assert csv_first.json()["format"] == "csv"
    assert default_json.json()["id"] != csv_first.json()["id"]
    assert csv_first.json()["id"] == csv_second.json()["id"]

    unsupported = await http_client.post(
        "/v1/auth/data-exports",
        json={"format": "xlsx"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert unsupported.status_code == 422

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        row_count = (
            await s.execute(
                text("SELECT count(*) FROM data_export_requests WHERE user_id_snapshot = :uid"),
                {"uid": user_id},
            )
        ).scalar_one()
        outbox_count = (
            await s.execute(
                text("SELECT count(*) FROM outbox WHERE event_type = 'data_export.requested'")
            )
        ).scalar_one()
    assert row_count == 2
    assert outbox_count == 2


async def test_data_export_direct_concurrent_requests_share_one_row(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, _ = await _signup(http_client)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_one() -> uuid.UUID:
        async with maker() as s:
            row = await data_export.request_data_export(s, user_id=user_id)
            await s.commit()
            return row.id

    first_id, second_id = await asyncio.gather(create_one(), create_one())

    assert first_id == second_id
    async with maker() as s:
        row_count = (
            await s.execute(
                text("SELECT count(*) FROM data_export_requests WHERE user_id_snapshot = :uid"),
                {"uid": user_id},
            )
        ).scalar_one()
        outbox_count = (
            await s.execute(
                text("SELECT count(*) FROM outbox WHERE event_type = 'data_export.requested'")
            )
        ).scalar_one()
    assert row_count == 1
    assert outbox_count == 1


async def test_data_export_direct_concurrent_csv_requests_share_one_row(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, _ = await _signup(http_client)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_one() -> uuid.UUID:
        async with maker() as s:
            row = await data_export.request_data_export(
                s,
                user_id=user_id,
                export_format="csv",
            )
            await s.commit()
            return row.id

    first_id, second_id = await asyncio.gather(create_one(), create_one())

    assert first_id == second_id
    async with maker() as s:
        row_count = (
            await s.execute(
                text(
                    "SELECT count(*) FROM data_export_requests "
                    "WHERE user_id_snapshot = :uid AND format = 'csv'"
                ),
                {"uid": user_id},
            )
        ).scalar_one()
        outbox_count = (
            await s.execute(
                text(
                    "SELECT count(*) FROM outbox "
                    "WHERE event_type = 'data_export.requested' "
                    "AND payload->>'format' = 'csv'"
                )
            )
        ).scalar_one()
    assert row_count == 1
    assert outbox_count == 1


async def test_data_export_status_and_download_are_owner_scoped(
    http_client: AsyncClient,
) -> None:
    _, jwt_a = await _signup(http_client)
    _, jwt_b = await _signup(http_client)

    created = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt_a}"},
    )
    export_id = created.json()["id"]

    own = await http_client.get(
        f"/v1/auth/data-exports/{export_id}",
        headers={"Authorization": f"Bearer {jwt_a}"},
    )
    other_status = await http_client.get(
        f"/v1/auth/data-exports/{export_id}",
        headers={"Authorization": f"Bearer {jwt_b}"},
    )
    other_download = await http_client.get(
        f"/v1/auth/data-exports/{export_id}/download",
        headers={"Authorization": f"Bearer {jwt_b}"},
    )

    assert own.status_code == 200
    assert other_status.status_code == 404
    assert other_download.status_code == 404


async def test_worker_generates_sanitized_json_package(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    api_key_id, full_api_key = await _create_api_key(http_client, jwt)
    await _insert_cross_domain_rows(engine, user_id=user_id, api_key_id=api_key_id)
    created = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    export_id = uuid.UUID(created.json()["id"])

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        completed = await data_export.complete_pending_data_export_requests(
            s,
            now=datetime.now(UTC),
        )
        await s.commit()
    assert completed == [export_id]

    downloaded = await http_client.get(
        f"/v1/auth/data-exports/{export_id}/download",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert downloaded.status_code == 200, downloaded.text
    package = downloaded.json()
    assert package["schema_version"] == "pipl_export_json_v1"
    assert package["subject"]["user_id"] == str(user_id)
    assert package["manifest"]["sections"]["auth.profile"]["count"] == 1
    assert package["manifest"]["sections"]["solver.optimizations"]["count"] == 1
    assert package["manifest"]["sections"]["solver.predictions"]["count"] == 1
    assert package["manifest"]["sections"]["billing.credit_transactions"]["count"] == 1
    assert package["manifest"]["sections"]["chat.messages"]["status"] == "unavailable"

    rendered = downloaded.text
    assert full_api_key not in rendered
    assert "secret-token" not in rendered
    assert "sk-secret-value" not in rendered
    assert "jwt-secret" not in rendered
    assert "hash-secret" not in rendered
    assert '"visible":"ok"' in rendered

    async with maker() as s:
        row = (
            await s.execute(select(DataExportRequest).where(DataExportRequest.id == export_id))
        ).scalar_one()
        assert row.status == "completed"
        assert row.package_sha256 is not None
        assert row.package_bytes is not None and row.package_bytes > 0
        completion_events = (
            await s.execute(
                text(
                    "SELECT count(*) FROM outbox "
                    "WHERE event_type = 'data_export.completed' "
                    "AND payload->>'data_export_id' = :eid"
                ),
                {"eid": str(export_id)},
            )
        ).scalar_one()
    assert completion_events == 1


async def test_worker_generates_sanitized_csv_zip_package(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    user_id, jwt = await _signup(http_client)
    api_key_id, full_api_key = await _create_api_key(http_client, jwt)
    await _insert_cross_domain_rows(engine, user_id=user_id, api_key_id=api_key_id)
    await _insert_csv_edge_rows(engine, user_id=user_id, api_key_id=api_key_id)
    created = await http_client.post(
        "/v1/auth/data-exports",
        json={"format": "csv"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    export_id = uuid.UUID(created.json()["id"])

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        completed = await data_export.complete_pending_data_export_requests(
            s,
            now=datetime.now(UTC),
        )
        await s.commit()
    assert completed == [export_id]

    downloaded = await http_client.get(
        f"/v1/auth/data-exports/{export_id}/download",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith("application/zip")
    assert "attachment" in downloaded.headers["content-disposition"]
    entries = _zip_text_entries(downloaded.content)
    assert {
        "auth/api_keys.csv",
        "auth/audit_logs.csv",
        "auth/profile.csv",
        "billing/credit_transactions.csv",
        "billing/saga_instances.csv",
        "manifest.csv",
        "solver/optimizations.csv",
        "solver/predictions.csv",
    }.issubset(entries)
    manifest_rows = list(csv.DictReader(io.StringIO(entries["manifest.csv"])))
    manifest_by_section = {row["section"]: row for row in manifest_rows}
    assert manifest_by_section["auth.profile"]["status"] == "available"
    assert manifest_by_section["solver.optimizations"]["count"] == "2"
    assert manifest_by_section["chat.messages"]["status"] == "unavailable"
    assert manifest_by_section["chat.messages"]["path"] == ""

    rendered = "\n".join(entries.values())
    assert full_api_key not in rendered
    assert "secret-token" not in rendered
    assert "sk-secret-value" not in rendered
    assert "jwt-secret" not in rendered
    assert "hash-secret" not in rendered
    assert "'=SUM(1,1)" in rendered
    assert "'-10.0000" not in rendered
    assert "-10.0000" in rendered
    assert '""nested"":{""authorization"":""[REDACTED]"",""value"":""@cmd""}' in rendered

    async with maker() as s:
        row = (
            await s.execute(select(DataExportRequest).where(DataExportRequest.id == export_id))
        ).scalar_one()
        assert row.status == "completed"
        assert row.package_json is not None
        assert row.package_json["format"] == "csv"
        assert row.package_json["archive"]["content_base64"] not in rendered
        assert row.package_sha256 is not None
        assert row.package_bytes == len(downloaded.content)
        completion_events = (
            await s.execute(
                text(
                    "SELECT count(*) FROM outbox "
                    "WHERE event_type = 'data_export.completed' "
                    "AND payload->>'data_export_id' = :eid "
                    "AND payload->>'format' = 'csv' "
                    "AND payload ? 'content_base64' = false"
                ),
                {"eid": str(export_id)},
            )
        ).scalar_one()
    assert completion_events == 1


async def test_completed_csv_export_is_immutable_on_worker_replay(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    _, jwt = await _signup(http_client)
    created = await http_client.post(
        "/v1/auth/data-exports",
        json={"format": "csv"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    export_id = uuid.UUID(created.json()["id"])
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with maker() as s:
        first_completed = await data_export.complete_pending_data_export_requests(
            s,
            now=datetime.now(UTC),
        )
        await s.commit()
    assert first_completed == [export_id]

    async with maker() as s:
        before = (
            await s.execute(select(DataExportRequest).where(DataExportRequest.id == export_id))
        ).scalar_one()
        before_hash = before.package_sha256
        before_completed_at = before.completed_at
        second_completed = await data_export.complete_pending_data_export_requests(
            s,
            now=datetime.now(UTC) + timedelta(minutes=5),
        )
        await s.commit()
    assert second_completed == []

    async with maker() as s:
        after = (
            await s.execute(select(DataExportRequest).where(DataExportRequest.id == export_id))
        ).scalar_one()
        completion_events = (
            await s.execute(
                text(
                    "SELECT count(*) FROM outbox "
                    "WHERE event_type = 'data_export.completed' "
                    "AND payload->>'data_export_id' = :eid"
                ),
                {"eid": str(export_id)},
            )
        ).scalar_one()
    assert after.package_sha256 == before_hash
    assert after.completed_at == before_completed_at
    assert completion_events == 1


async def test_download_rejects_queued_and_expired_packages(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    _, jwt = await _signup(http_client)
    created = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    export_id = uuid.UUID(created.json()["id"])

    queued = await http_client.get(
        f"/v1/auth/data-exports/{export_id}/download",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert queued.status_code == 409

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                UPDATE data_export_requests
                SET status = 'completed',
                    completed_at = :completed_at,
                    expires_at = :expires_at,
                    package_json = CAST(:package AS jsonb),
                    package_sha256 = :sha,
                    package_bytes = 2,
                    download_url = :url
                WHERE id = :id
                """
            ),
            {
                "id": export_id,
                "completed_at": datetime.now(UTC) - timedelta(days=8),
                "expires_at": datetime.now(UTC) - timedelta(seconds=1),
                "package": "{}",
                "sha": "0" * 64,
                "url": f"/v1/auth/data-exports/{export_id}/download",
            },
        )
        await s.commit()

    expired = await http_client.get(
        f"/v1/auth/data-exports/{export_id}/download",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert expired.status_code == 410


async def test_csv_download_rejects_missing_archive_envelope(
    http_client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    _, jwt = await _signup(http_client)
    created = await http_client.post(
        "/v1/auth/data-exports",
        json={"format": "csv"},
        headers={"Authorization": f"Bearer {jwt}"},
    )
    export_id = uuid.UUID(created.json()["id"])

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        await s.execute(
            text(
                """
                UPDATE data_export_requests
                SET status = 'completed',
                    completed_at = :completed_at,
                    expires_at = :expires_at,
                    package_json = CAST(:package AS jsonb),
                    package_sha256 = :sha,
                    package_bytes = 2,
                    download_url = :url
                WHERE id = :id
                """
            ),
            {
                "id": export_id,
                "completed_at": datetime.now(UTC),
                "expires_at": datetime.now(UTC) + timedelta(days=1),
                "package": '{"schema_version":"pipl_export_csv_v1","format":"csv"}',
                "sha": "0" * 64,
                "url": f"/v1/auth/data-exports/{export_id}/download",
            },
        )
        await s.commit()

    downloaded = await http_client.get(
        f"/v1/auth/data-exports/{export_id}/download",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    assert downloaded.status_code == 409


async def test_worker_failure_records_bounded_error_without_completion_event(
    http_client: AsyncClient,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, jwt = await _signup(http_client)
    created = await http_client.post(
        "/v1/auth/data-exports",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    export_id = uuid.UUID(created.json()["id"])

    async def boom(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("database password=secret-token should not leak")

    monkeypatch.setattr(data_export, "_build_data_export_package", boom)

    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        completed = await data_export.complete_pending_data_export_requests(
            s,
            now=datetime.now(UTC),
        )
        await s.commit()

    assert completed == []
    async with maker() as s:
        row = (
            await s.execute(select(DataExportRequest).where(DataExportRequest.id == export_id))
        ).scalar_one()
        assert row.status == "failed"
        assert row.package_json is None
        assert row.last_error is not None
        assert "secret-token" not in row.last_error
        completed_outbox = (
            await s.execute(
                text(
                    "SELECT count(*) FROM outbox "
                    "WHERE event_type = 'data_export.completed' "
                    "AND payload->>'data_export_id' = :eid"
                ),
                {"eid": str(export_id)},
            )
        ).scalar_one()
        audit_actions = {
            row.action
            for row in (
                await s.execute(
                    select(AuditLog.action).where(AuditLog.action == "data_export.failed")
                )
            ).all()
        }
    assert completed_outbox == 0
    assert "data_export.failed" in audit_actions
