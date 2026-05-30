"""Story 5.C.3 — PIPL JSON data export helpers.

The long-term architecture owner is api-gateway. v1 keeps the actor shape inside
auth-service because api-gateway is not yet online, while reading non-auth
tables through raw SQL so service ORM boundaries remain intact.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
import re
import uuid
import zipfile
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from auth_service.models import APIKey, AuditLog, DataExportRequest, User

EXPORT_SLA_DAYS = 7
EXPORT_EXPIRES_DAYS = 7
SNAPSHOT_SCHEMA_VERSION = "pipl_export_snapshot_v1"
JSON_SCHEMA_VERSION = "pipl_export_json_v1"
CSV_SCHEMA_VERSION = "pipl_export_csv_v1"
JSON_FORMAT = "json"
CSV_FORMAT = "csv"
SUPPORTED_FORMATS = {JSON_FORMAT, CSV_FORMAT}
CSV_ARCHIVE_FILENAME = "opticloud-pipl-data-export-csv.zip"
CSV_MEDIA_TYPE = "application/zip"
CSV_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
CSV_SECTION_PATHS = {
    "auth.profile": "auth/profile.csv",
    "auth.api_keys": "auth/api_keys.csv",
    "auth.account_deletion_requests": "auth/account_deletion_requests.csv",
    "auth.account_merge_proposals": "auth/account_merge_proposals.csv",
    "auth.account_freeze_appeals": "auth/account_freeze_appeals.csv",
    "auth.risk_flags": "auth/risk_flags.csv",
    "auth.audit_logs": "auth/audit_logs.csv",
    "solver.optimizations": "solver/optimizations.csv",
    "solver.optimization_batches": "solver/optimization_batches.csv",
    "solver.predictions": "solver/predictions.csv",
    "billing.saga_instances": "billing/saga_instances.csv",
    "billing.credit_transactions": "billing/credit_transactions.csv",
    "billing.subscriptions": "billing/subscriptions.csv",
}

_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|key[_-]?hash|token[_-]?hash|request[_-]?body[_-]?hash|"
    r"authorization|jwt|password|pepper|otp|secret|tracking[_-]?token|"
    r"guardian[_-]?consent[_-]?token)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(Bearer\s+[A-Za-z0-9._~+/=-]+|sk-[A-Za-z0-9._~+/=-]+|"
    r"jwt-[A-Za-z0-9._~+/=-]+|secret-[A-Za-z0-9._~+/=-]+)",
    re.IGNORECASE,
)
_SAFE_TABLE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_SAFE_SQL_FRAGMENT_RE = re.compile(r"^[a-zA-Z0-9_ (),.:=<>']+$")
_NUMERIC_LITERAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$")


def _now() -> datetime:
    return datetime.now(UTC)


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(v) for v in value]
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _sanitize_key(key: str) -> bool:
    return bool(_SECRET_KEY_RE.search(key))


def sanitize_export_value(value: Any) -> Any:
    """Recursively redact obvious secrets from arbitrary JSON-like values."""
    if isinstance(value, Mapping):
        clean: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if _sanitize_key(key):
                clean[key] = "[REDACTED]"
            else:
                clean[key] = sanitize_export_value(raw_value)
        return clean
    if isinstance(value, list | tuple):
        return [sanitize_export_value(v) for v in value]
    if isinstance(value, str):
        return _SECRET_VALUE_RE.sub("[REDACTED]", value)
    return _to_jsonable(value)


def _validate_export_format(export_format: str) -> str:
    if export_format not in SUPPORTED_FORMATS:
        raise ValueError("unsupported data export format")
    return export_format


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: data export failed"


def _row_dict(row: Any, keys: Iterable[str]) -> dict[str, Any]:
    return {key: sanitize_export_value(getattr(row, key)) for key in keys}


def _section(status: str, count: int = 0, reason: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"status": status, "count": count}
    if reason is not None:
        payload["reason"] = reason
    return payload


def _status_response(row: DataExportRequest) -> dict[str, Any]:
    return {
        "id": row.id,
        "status": row.status,
        "format": row.format,
        "requested_at": row.requested_at,
        "sla_deadline_at": row.sla_deadline_at,
        "completed_at": row.completed_at,
        "expires_at": row.expires_at,
        "download_url": row.download_url,
        "package_sha256": row.package_sha256,
        "package_bytes": row.package_bytes,
        "last_error": row.last_error,
    }


async def get_export_request_for_user(
    session: AsyncSession,
    *,
    export_id: uuid.UUID,
    user_id: uuid.UUID,
) -> DataExportRequest | None:
    result = await session.execute(
        select(DataExportRequest).where(
            DataExportRequest.id == export_id,
            DataExportRequest.user_id_snapshot == user_id,
        )
    )
    return result.scalar_one_or_none()


async def request_data_export(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    export_format: str = JSON_FORMAT,
    now: datetime | None = None,
) -> DataExportRequest:
    export_format = _validate_export_format(export_format)
    current_time = now or _now()
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"data-export:{user_id}:{export_format}"},
    )
    existing = await _get_active_export_request(
        session,
        user_id=user_id,
        export_format=export_format,
        now=current_time,
    )
    if existing is not None:
        return existing

    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    request = DataExportRequest(
        user_id_snapshot=user_id,
        user_id=user.id if user is not None and user.deleted_at is None else None,
        format=export_format,
        status="queued",
        requested_at=current_time,
        sla_deadline_at=current_time + timedelta(days=EXPORT_SLA_DAYS),
        created_at=current_time,
        updated_at=current_time,
    )
    session.add(request)
    await session.flush()

    session.add(
        AuditLog(
            user_id=user_id if user is not None and user.deleted_at is None else None,
            actor="user",
            action="data_export.requested",
            resource_type="data_export",
            resource_id=request.id,
            audit_metadata={
                "data_export_id": str(request.id),
                "user_id_snapshot": str(user_id),
                "format": export_format,
                "sla_deadline_at": request.sla_deadline_at.isoformat(),
            },
        )
    )
    await _insert_outbox_event(
        session,
        aggregate_id=request.id,
        event_type="data_export.requested",
        payload={
            "data_export_id": str(request.id),
            "user_id_snapshot": str(user_id),
            "format": export_format,
            "sla_deadline_at": request.sla_deadline_at.isoformat(),
        },
        occurred_at=current_time,
    )
    await session.flush()
    return request


async def _get_active_export_request(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    export_format: str,
    now: datetime,
) -> DataExportRequest | None:
    result = await session.execute(
        select(DataExportRequest)
        .where(
            DataExportRequest.user_id_snapshot == user_id,
            DataExportRequest.format == export_format,
            DataExportRequest.status.in_(("queued", "processing", "completed")),
            ((DataExportRequest.expires_at.is_(None)) | (DataExportRequest.expires_at > now)),
        )
        .order_by(DataExportRequest.requested_at.desc(), DataExportRequest.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def complete_pending_data_export_requests(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 10,
) -> list[uuid.UUID]:
    current_time = now or _now()
    result = await session.execute(
        select(DataExportRequest)
        .where(DataExportRequest.status == "queued")
        .order_by(DataExportRequest.requested_at, DataExportRequest.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    requests = result.scalars().all()
    completed: list[uuid.UUID] = []

    for request in requests:
        request.status = "processing"
        request.processing_started_at = current_time
        request.updated_at = current_time
        await session.flush()
        try:
            package, downloadable_bytes = await _build_data_export_package(
                session,
                user_id=request.user_id_snapshot,
                export_format=request.format,
                generated_at=current_time,
            )
            request.status = "completed"
            request.completed_at = current_time
            request.expires_at = current_time + timedelta(days=EXPORT_EXPIRES_DAYS)
            request.package_json = package
            request.package_sha256 = hashlib.sha256(downloadable_bytes).hexdigest()
            request.package_bytes = len(downloadable_bytes)
            request.download_url = f"/v1/auth/data-exports/{request.id}/download"
            request.last_error = None
            request.updated_at = current_time
            session.add(
                AuditLog(
                    user_id=request.user_id,
                    actor="system",
                    action="data_export.completed",
                    resource_type="data_export",
                    resource_id=request.id,
                    audit_metadata={
                        "data_export_id": str(request.id),
                        "user_id_snapshot": str(request.user_id_snapshot),
                        "format": request.format,
                        "package_sha256": request.package_sha256,
                        "package_bytes": request.package_bytes,
                    },
                )
            )
            await _insert_outbox_event(
                session,
                aggregate_id=request.id,
                event_type="data_export.completed",
                payload={
                    "data_export_id": str(request.id),
                    "user_id_snapshot": str(request.user_id_snapshot),
                    "format": request.format,
                    "package_sha256": request.package_sha256,
                    "package_bytes": request.package_bytes,
                    "section_counts": _section_counts(package),
                    "download_url": request.download_url,
                },
                occurred_at=current_time,
            )
            completed.append(request.id)
        except Exception as exc:  # noqa: BLE001 - worker records bounded failure state.
            request.status = "failed"
            request.last_error = _safe_error(exc)
            request.package_json = None
            request.package_sha256 = None
            request.package_bytes = None
            request.download_url = None
            request.updated_at = current_time
            session.add(
                AuditLog(
                    user_id=request.user_id,
                    actor="system",
                    action="data_export.failed",
                    resource_type="data_export",
                    resource_id=request.id,
                    audit_metadata={
                        "data_export_id": str(request.id),
                        "user_id_snapshot": str(request.user_id_snapshot),
                        "format": request.format,
                        "error_type": type(exc).__name__,
                    },
                )
            )
    await session.flush()
    return completed


def _section_counts(package: Mapping[str, Any]) -> dict[str, int]:
    manifest = package.get("manifest")
    if not isinstance(manifest, Mapping):
        return {}
    sections = manifest.get("sections")
    if not isinstance(sections, Mapping):
        return {}
    counts: dict[str, int] = {}
    for key, value in sections.items():
        if isinstance(value, Mapping):
            count = value.get("count")
            counts[str(key)] = int(count) if isinstance(count, int) else 0
    return counts


async def _build_data_export_package(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    export_format: str,
    generated_at: datetime,
) -> tuple[dict[str, Any], bytes]:
    export_format = _validate_export_format(export_format)
    snapshot = await _build_data_export_snapshot(
        session,
        user_id=user_id,
        generated_at=generated_at,
    )
    if export_format == CSV_FORMAT:
        package = _render_csv_export_package(snapshot)
    else:
        package = _render_json_export_package(snapshot)
    return package, _downloadable_bytes(package)


async def _build_data_export_snapshot(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    generated_at: datetime,
) -> dict[str, Any]:
    manifest: dict[str, dict[str, Any]] = {}
    data: dict[str, Any] = {}

    profile = await _auth_profile(session, user_id)
    data["auth.profile"] = profile
    manifest["auth.profile"] = _section("available", 1 if profile is not None else 0)

    auth_sections = {
        "auth.api_keys": await _auth_api_keys(session, user_id),
        "auth.account_deletion_requests": await _table_rows(
            session,
            "account_deletion_requests",
            "user_id_snapshot = :uid",
            {"uid": user_id},
            order_by="requested_at, id",
        ),
        "auth.account_merge_proposals": await _auth_account_merge_rows(session, user_id),
        "auth.account_freeze_appeals": await _table_rows(
            session,
            "account_freeze_appeals",
            "user_id = :uid",
            {"uid": user_id},
            order_by="created_at, id",
        ),
        "auth.risk_flags": await _table_rows(
            session,
            "risk_flags",
            "user_id = :uid",
            {"uid": user_id},
            order_by="created_at, id",
        ),
        "auth.audit_logs": await _table_rows(
            session,
            "audit_logs",
            "(user_id = :uid OR resource_id = :uid)",
            {"uid": user_id},
            order_by="created_at, id",
        ),
    }
    for name, rows in auth_sections.items():
        data[name] = rows
        manifest[name] = _section("available", len(rows))

    table_sections = {
        "solver.optimizations": ("optimizations", "user_id = :uid", "created_at, id"),
        "solver.optimization_batches": (
            "optimization_batches",
            "user_id = :uid",
            "created_at, id",
        ),
        "solver.predictions": ("predictions", "user_id = :uid", "created_at, id"),
        "billing.saga_instances": ("saga_instances", "user_id = :uid", "created_at, id"),
        "billing.credit_transactions": (
            "credit_transactions",
            "user_id = :uid",
            "created_at, id",
        ),
        "billing.subscriptions": (
            "billing_subscriptions",
            "user_id = :uid",
            "created_at, id",
        ),
    }
    for section_name, (table, where, order_by) in table_sections.items():
        if await _table_exists(session, table):
            rows = await _table_rows(
                session,
                table,
                where,
                {"uid": user_id},
                order_by=order_by,
            )
            data[section_name] = rows
            manifest[section_name] = _section("available", len(rows))
        else:
            data[section_name] = []
            manifest[section_name] = _section("unavailable", reason="table_absent")

    data["chat.messages"] = []
    manifest["chat.messages"] = _section("unavailable", reason="not_persisted_v1")

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": _to_jsonable(generated_at),
        "subject": {"user_id": str(user_id)},
        "manifest": {"sections": {k: manifest[k] for k in sorted(manifest)}},
        "data": {k: data[k] for k in sorted(data)},
    }


def _render_json_export_package(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "format": JSON_FORMAT,
        "generated_at": snapshot["generated_at"],
        "subject": snapshot["subject"],
        "manifest": snapshot["manifest"],
        "data": snapshot["data"],
    }


def _render_csv_export_package(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    files: dict[str, bytes] = {}
    file_manifest: list[dict[str, Any]] = []
    section_manifest = _csv_section_manifest(snapshot)
    manifest_rows = _csv_manifest_rows(section_manifest)
    manifest_bytes = _csv_bytes(
        manifest_rows,
        ("section", "status", "count", "reason", "path"),
    )
    files["manifest.csv"] = manifest_bytes

    data = snapshot.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("data export snapshot is malformed")

    for section_name in sorted(section_manifest):
        section = section_manifest[section_name]
        path = section.get("path")
        row_mappings = _section_rows(data.get(section_name, []))
        if not path or not row_mappings:
            continue
        headers = sorted({key for row in row_mappings for key in row})
        files[str(path)] = _csv_bytes(row_mappings, tuple(headers))

    for path in sorted(files):
        content = files[path]
        file_manifest.append(
            {
                "path": path,
                "rows": _csv_data_row_count(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    archive_bytes = _zip_bytes(files)
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    return {
        "schema_version": CSV_SCHEMA_VERSION,
        "format": CSV_FORMAT,
        "generated_at": snapshot["generated_at"],
        "subject": snapshot["subject"],
        "manifest": {
            "sections": section_manifest,
            "files": file_manifest,
        },
        "archive": {
            "media_type": CSV_MEDIA_TYPE,
            "filename": CSV_ARCHIVE_FILENAME,
            "encoding": "base64",
            "sha256": archive_sha256,
            "bytes": len(archive_bytes),
            "content_base64": base64.b64encode(archive_bytes).decode("ascii"),
        },
    }


def _downloadable_bytes(package: Mapping[str, Any]) -> bytes:
    if package.get("format") == CSV_FORMAT:
        archive = package.get("archive")
        if not isinstance(archive, Mapping):
            raise ValueError("CSV archive envelope missing")
        if archive.get("encoding") != "base64":
            raise ValueError("CSV archive envelope encoding invalid")
        content_base64 = archive.get("content_base64")
        if not isinstance(content_base64, str):
            raise ValueError("CSV archive content missing")
        try:
            return base64.b64decode(content_base64.encode("ascii"), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("CSV archive content invalid") from exc
    return json.dumps(
        package,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def csv_download_bytes(package: Mapping[str, Any]) -> bytes | None:
    try:
        if package.get("format") != CSV_FORMAT:
            return None
        archive = package.get("archive")
        if not isinstance(archive, Mapping):
            return None
        if archive.get("media_type") != CSV_MEDIA_TYPE:
            return None
        return _downloadable_bytes(package)
    except ValueError:
        return None


def _csv_section_manifest(snapshot: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    manifest = snapshot.get("manifest")
    data = snapshot.get("data")
    if not isinstance(manifest, Mapping) or not isinstance(data, Mapping):
        raise ValueError("data export snapshot is malformed")
    raw_sections = manifest.get("sections")
    if not isinstance(raw_sections, Mapping):
        raise ValueError("data export manifest is malformed")

    sections: dict[str, dict[str, Any]] = {}
    for section_name in sorted(raw_sections):
        raw_section = raw_sections[section_name]
        if not isinstance(raw_section, Mapping):
            raise ValueError("data export section manifest is malformed")
        section = {
            "status": str(raw_section.get("status", "unavailable")),
            "count": int(raw_section.get("count", 0)),
        }
        reason = raw_section.get("reason")
        if reason is not None:
            section["reason"] = str(reason)
        rows = _section_rows(data.get(section_name, []))
        if section["status"] == "available" and rows:
            path = CSV_SECTION_PATHS.get(str(section_name))
            if path is None:
                raise ValueError("unknown CSV section path")
            section["path"] = path
        sections[str(section_name)] = section
    return sections


def _csv_manifest_rows(
    sections: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for section_name in sorted(sections):
        section = sections[section_name]
        rows.append(
            {
                "section": section_name,
                "status": section.get("status", ""),
                "count": section.get("count", 0),
                "reason": section.get("reason", ""),
                "path": section.get("path", ""),
            }
        )
    return rows


def _ensure_mapping_row(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return {str(key): value for key, value in row.items()}
    raise ValueError("CSV section rows must be objects")


def _section_rows(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [_ensure_mapping_row(value)]
    if isinstance(value, list):
        return [_ensure_mapping_row(row) for row in value]
    raise ValueError("CSV section data must be an object or list")


def _csv_bytes(rows: list[dict[str, Any]], headers: tuple[str, ...]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(headers), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({header: _csv_cell(row.get(header)) for header in headers})
    return output.getvalue().encode("utf-8")


def _csv_cell(value: Any) -> str:
    jsonable = sanitize_export_value(value)
    formula_escape = isinstance(value, str)
    if isinstance(jsonable, Mapping | list):
        rendered = json.dumps(
            jsonable,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    elif jsonable is None:
        rendered = ""
    else:
        rendered = str(jsonable)
    if formula_escape and _needs_csv_formula_escape(rendered):
        return "'" + rendered
    return rendered


def _needs_csv_formula_escape(value: str) -> bool:
    if value.startswith(("=", "@", "\t", "\r", "\n")):
        return True
    if value.startswith(("+", "-")):
        return not bool(_NUMERIC_LITERAL_RE.match(value))
    return False


def _csv_data_row_count(content: bytes) -> int:
    text_content = content.decode("utf-8")
    if not text_content:
        return 0
    return max(len(text_content.splitlines()) - 1, 0)


def _zip_bytes(files: Mapping[str, bytes]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            info = zipfile.ZipInfo(path, date_time=CSV_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[path])
    return output.getvalue()


async def _auth_profile(session: AsyncSession, user_id: uuid.UUID) -> dict[str, Any] | None:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return None
    return _row_dict(
        user,
        (
            "id",
            "phone",
            "email",
            "edu_tier",
            "age_verified",
            "risk_score",
            "is_frozen",
            "merged_into_user_id",
            "merged_at",
            "created_at",
            "updated_at",
            "deleted_at",
        ),
    )


async def _auth_api_keys(session: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await session.execute(
        select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at, APIKey.id)
    )
    keys = result.scalars().all()
    return [
        _row_dict(
            key,
            (
                "id",
                "user_id",
                "key_prefix",
                "label",
                "description",
                "scope",
                "expires_at",
                "last_used_at",
                "last_used_ip",
                "last_used_geo_bucket",
                "geo_risk_score",
                "geo_anomaly_at",
                "geo_anomaly_metadata",
                "revoked_at",
                "created_at",
            ),
        )
        for key in keys
    ]


async def _auth_account_merge_rows(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    if not await _table_exists(session, "account_merge_proposals"):
        return []
    rows = await session.execute(
        text(
            """
            SELECT *
            FROM account_merge_proposals
            WHERE requester_user_id = :uid
               OR primary_user_id = :uid
               OR :uid = ANY(duplicate_user_ids)
            ORDER BY created_at, id
            """
        ),
        {"uid": user_id},
    )
    return [_sanitize_row_mapping(row._mapping) for row in rows]


async def _table_rows(
    session: AsyncSession,
    table: str,
    where: str,
    params: Mapping[str, Any],
    *,
    order_by: str,
) -> list[dict[str, Any]]:
    if not await _table_exists(session, table):
        return []
    if not _SAFE_TABLE_RE.match(table) or not _SAFE_SQL_FRAGMENT_RE.match(where):
        raise ValueError("unsafe export table query")
    if not _SAFE_SQL_FRAGMENT_RE.match(order_by):
        raise ValueError("unsafe export table ordering")
    # The SQL fragments are internal constants validated above; parameters remain bound.
    query = text(f"SELECT * FROM {table} WHERE {where} ORDER BY {order_by}")  # noqa: S608  # nosec B608
    result = await session.execute(query, dict(params))
    return [_sanitize_row_mapping(row._mapping) for row in result]


async def _table_exists(session: AsyncSession, table: str) -> bool:
    result = await session.execute(
        text("SELECT to_regclass(:table_name) IS NOT NULL"),
        {"table_name": table},
    )
    return bool(result.scalar_one())


def _sanitize_row_mapping(row: Mapping[str, Any] | RowMapping) -> dict[str, Any]:
    return {str(key): sanitize_export_value(value) for key, value in row.items()}


async def _insert_outbox_event(
    session: AsyncSession,
    *,
    aggregate_id: uuid.UUID,
    event_type: str,
    payload: Mapping[str, Any],
    occurred_at: datetime,
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO outbox
                (aggregate_type, aggregate_id, event_type, event_version,
                 payload, headers, occurred_at)
            VALUES
                ('data_export', :aggregate_id, :event_type, 1,
                 CAST(:payload AS jsonb), '{}'::jsonb, :occurred_at)
            """
        ),
        {
            "aggregate_id": aggregate_id,
            "event_type": event_type,
            "payload": json.dumps(sanitize_export_value(payload), sort_keys=True),
            "occurred_at": occurred_at,
        },
    )


def status_response(row: DataExportRequest) -> dict[str, Any]:
    return _status_response(row)
