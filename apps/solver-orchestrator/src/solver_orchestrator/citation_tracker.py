"""Citation tracking utilities — Story 6.A.3.

The module stays side-effect-light so a future scheduler can wrap the CLI
without changing tracking logic.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from solver_orchestrator.catalog import CATALOG, Algorithm

SEMANTIC_SCHOLAR_BASE_URL = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_CITATION_FIELDS = (
    "citingPaper.paperId,citingPaper.title,citingPaper.url,citingPaper.year,"
    "citingPaper.authors,citingPaper.externalIds"
)
LINEAR_GRAPHQL_URL = "https://api.linear.app/graphql"


@dataclass(frozen=True)
class CitationTarget:
    k_algo: str
    citation_key: str
    title: str
    doi: str | None
    url: str | None
    source: Literal["catalog"]


@dataclass(frozen=True)
class CitationHit:
    source: Literal["semantic_scholar", "google_scholar_import"]
    k_algo: str
    citation_key: str
    external_id: str
    title: str
    url: str | None
    year: int | None
    authors: list[str]
    observed_at: datetime


@dataclass(frozen=True)
class CitationTrackingReport:
    generated_at: datetime
    targets_scanned: int
    hits_total: int
    hits_new: int
    scan_notes: list[dict[str, str]]
    source_failures: list[dict[str, str]]
    unmatched_imports: list[dict[str, str]]
    malformed_imports: list[dict[str, str]]
    new_hits: list[CitationHit]
    all_hits: list[CitationHit]
    linear_issue_payloads: list[dict[str, object]]


@dataclass(frozen=True)
class ImportParseResult:
    hits: list[CitationHit]
    unmatched_imports: list[dict[str, str]]
    malformed_rows: list[dict[str, str]]


@dataclass(frozen=True)
class SemanticScholarFetchResult:
    hits: list[CitationHit] = field(default_factory=list)
    scan_notes: list[dict[str, str]] = field(default_factory=list)
    source_failures: list[dict[str, str]] = field(default_factory=list)


def extract_citation_targets(catalog: Sequence[Algorithm] = CATALOG) -> list[CitationTarget]:
    targets: list[CitationTarget] = []
    for algo in catalog:
        citation = algo["citation"]
        if citation is None:
            continue

        bibtex = citation["bibtex"]
        citation_key = _parse_bibtex_key(bibtex)
        if citation_key is None:
            continue

        targets.append(
            CitationTarget(
                k_algo=algo["k_algo"],
                citation_key=citation_key,
                title=_parse_bibtex_title(bibtex) or algo["description_en"],
                doi=citation["doi"],
                url=citation["url"],
                source="catalog",
            )
        )
    return targets


def _parse_bibtex_key(bibtex: str) -> str | None:
    match = re.search(r"@\w+\s*\{\s*([^,\s]+)\s*,", bibtex)
    if match is None:
        return None
    return match.group(1).strip()


def _parse_bibtex_title(bibtex: str) -> str | None:
    match = re.search(r"\btitle\s*=\s*\{(?P<title>(?:[^{}]|\{[^{}]*\})*)\}", bibtex, re.I)
    if match is None:
        return None
    return re.sub(r"\s+", " ", match.group("title").replace("{", "").replace("}", "")).strip()


async def fetch_semantic_scholar_citations(
    targets: Sequence[CitationTarget],
    *,
    client: httpx.AsyncClient | None = None,
    observed_at: datetime,
    api_key: str = "",
    min_interval_seconds: float = 1.0,
    timeout_seconds: float = 10.0,
    limit: int = 100,
) -> SemanticScholarFetchResult:
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(base_url=SEMANTIC_SCHOLAR_BASE_URL, timeout=timeout_seconds)

    hits: list[CitationHit] = []
    scan_notes: list[dict[str, str]] = []
    source_failures: list[dict[str, str]] = []
    headers = {"x-api-key": api_key} if api_key else None
    made_request = False

    try:
        for target in targets:
            if target.doi is None:
                scan_notes.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": "skipped_no_doi",
                    }
                )
                continue

            if made_request and min_interval_seconds > 0:
                await asyncio.sleep(min_interval_seconds)
            made_request = True

            try:
                response = await client.get(
                    f"{SEMANTIC_SCHOLAR_BASE_URL}/paper/DOI:{target.doi}/citations",
                    params={
                        "fields": SEMANTIC_SCHOLAR_CITATION_FIELDS,
                        "offset": 0,
                        "limit": limit,
                    },
                    headers=headers,
                    timeout=timeout_seconds,
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                source_failures.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": "request_error",
                        "message": type(exc).__name__,
                    }
                )
                continue

            if response.status_code == 404:
                scan_notes.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": "not_indexed",
                    }
                )
                continue

            if response.status_code == 429 or response.status_code >= 500:
                source_failures.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": f"http_{response.status_code}",
                        "message": f"Semantic Scholar returned HTTP {response.status_code}",
                    }
                )
                continue

            if response.status_code < 200 or response.status_code >= 300:
                source_failures.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": f"http_{response.status_code}",
                        "message": f"Semantic Scholar returned HTTP {response.status_code}",
                    }
                )
                continue

            try:
                body = response.json()
            except ValueError:
                source_failures.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": "invalid_json",
                        "message": "Semantic Scholar returned invalid JSON",
                    }
                )
                continue

            if not isinstance(body, Mapping):
                source_failures.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": "invalid_shape",
                        "message": "Semantic Scholar returned a non-object response",
                    }
                )
                continue

            hits.extend(_semantic_scholar_hits_from_body(body, target, observed_at, scan_notes))
            data = body.get("data", [])
            next_offset = body.get("next")
            if isinstance(next_offset, int) or (isinstance(data, list) and len(data) >= limit):
                scan_notes.append(
                    {
                        "source": "semantic_scholar",
                        "k_algo": target.k_algo,
                        "status": "truncated",
                    }
                )
    finally:
        if owns_client:
            await client.aclose()

    return SemanticScholarFetchResult(
        hits=hits,
        scan_notes=scan_notes,
        source_failures=source_failures,
    )


def _semantic_scholar_hits_from_body(
    body: Mapping[str, Any],
    target: CitationTarget,
    observed_at: datetime,
    scan_notes: list[dict[str, str]],
) -> list[CitationHit]:
    hits: list[CitationHit] = []
    data = body.get("data", [])
    if not isinstance(data, list):
        return hits

    for item in data:
        if not isinstance(item, Mapping):
            _append_malformed_s2_note(scan_notes, target)
            continue
        citing_paper = item.get("citingPaper")
        if not isinstance(citing_paper, Mapping):
            _append_malformed_s2_note(scan_notes, target)
            continue
        title = _string_or_none(citing_paper.get("title"))
        if title is None:
            _append_malformed_s2_note(scan_notes, target)
            continue
        paper_id = _string_or_none(citing_paper.get("paperId"))
        url = _string_or_none(citing_paper.get("url"))
        external_id = (
            paper_id or _normalized_url(url) or _fallback_external_id(title, target.citation_key)
        )
        hits.append(
            CitationHit(
                source="semantic_scholar",
                k_algo=target.k_algo,
                citation_key=target.citation_key,
                external_id=external_id,
                title=title,
                url=url,
                year=_int_or_none(citing_paper.get("year")),
                authors=_authors_from_s2(citing_paper.get("authors")),
                observed_at=observed_at,
            )
        )
    return hits


def _append_malformed_s2_note(scan_notes: list[dict[str, str]], target: CitationTarget) -> None:
    scan_notes.append(
        {
            "source": "semantic_scholar",
            "k_algo": target.k_algo,
            "status": "skipped_malformed_citation",
        }
    )


def load_google_scholar_import(
    path: Path,
    targets: Sequence[CitationTarget],
    *,
    observed_at: datetime,
) -> ImportParseResult:
    rows = _load_import_rows(path)
    by_key = _targets_by_key(targets)

    hits: list[CitationHit] = []
    unmatched_imports: list[dict[str, str]] = []
    malformed_rows: list[dict[str, str]] = []

    for row_number, row in rows:
        citation_key = _string_or_none(row.get("citation_key"))
        title = _string_or_none(row.get("title"))
        if citation_key is None:
            malformed_rows.append({"row_number": str(row_number), "reason": "missing_citation_key"})
            continue
        if title is None:
            malformed_rows.append({"row_number": str(row_number), "reason": "missing_title"})
            continue

        matching_targets = by_key.get(citation_key, [])
        if not matching_targets:
            unmatched_imports.append(
                {
                    "row_number": str(row_number),
                    "citation_key": citation_key,
                    "reason": "unknown_citation_key",
                }
            )
            continue

        url = _string_or_none(row.get("url"))
        external_id = _normalized_url(url) or _fallback_external_id(title, citation_key)
        source = _string_or_none(row.get("source")) or "google_scholar_import"
        if source != "google_scholar_import":
            source = "google_scholar_import"

        for target in matching_targets:
            hits.append(
                CitationHit(
                    source="google_scholar_import",
                    k_algo=target.k_algo,
                    citation_key=citation_key,
                    external_id=external_id,
                    title=title,
                    url=url,
                    year=_int_or_none(row.get("year")),
                    authors=_authors_from_import(row.get("authors")),
                    observed_at=observed_at,
                )
            )

    return ImportParseResult(
        hits=hits,
        unmatched_imports=unmatched_imports,
        malformed_rows=malformed_rows,
    )


def _load_import_rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return [(1, {"citation_key": None, "title": None})]
        rows: list[tuple[int, dict[str, Any]]] = []
        for index, item in enumerate(data, start=1):
            if isinstance(item, dict):
                rows.append((index, item))
            else:
                rows.append((index, {"citation_key": None, "title": None}))
        return rows

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [(index, dict(row)) for index, row in enumerate(reader, start=2)]


def _targets_by_key(targets: Sequence[CitationTarget]) -> dict[str, list[CitationTarget]]:
    by_key: dict[str, list[CitationTarget]] = {}
    for target in targets:
        by_key.setdefault(target.citation_key, []).append(target)
    return by_key


def hit_identity(hit: CitationHit) -> str:
    return f"{hit.source}:{hit.k_algo}:{hit.external_id}"


def deduplicate_hits(hits: Sequence[CitationHit]) -> list[CitationHit]:
    by_identity: dict[str, CitationHit] = {}
    by_url: dict[tuple[str, str], CitationHit] = {}

    for hit in hits:
        identity = hit_identity(hit)
        normalized_url = _normalized_url(hit.url)
        url_key = (hit.k_algo, normalized_url) if normalized_url is not None else None

        existing = by_identity.get(identity)
        if existing is not None:
            if _hit_preference(hit) > _hit_preference(existing):
                by_identity[identity] = hit
            continue

        if url_key is not None and url_key in by_url:
            existing_by_url = by_url[url_key]
            preferred = (
                hit if _hit_preference(hit) > _hit_preference(existing_by_url) else existing_by_url
            )
            by_identity.pop(hit_identity(existing_by_url), None)
            by_identity[hit_identity(preferred)] = preferred
            by_url[url_key] = preferred
            continue

        by_identity[identity] = hit
        if url_key is not None:
            by_url[url_key] = hit

    return list(by_identity.values())


def _hit_preference(hit: CitationHit) -> int:
    if hit.source == "semantic_scholar":
        return 2
    return 1


def build_tracking_report(
    *,
    targets: Sequence[CitationTarget],
    hits: Sequence[CitationHit],
    previous_seen_hit_ids: set[str],
    previous_hits: Sequence[CitationHit] = (),
    generated_at: datetime,
    scan_notes: list[dict[str, str]] | None = None,
    source_failures: list[dict[str, str]] | None = None,
    unmatched_imports: list[dict[str, str]] | None = None,
    malformed_imports: list[dict[str, str]] | None = None,
) -> CitationTrackingReport:
    deduped_hits = deduplicate_hits(hits)
    previous_signatures = _seen_signatures(previous_hits)
    new_hits = [
        hit
        for hit in deduped_hits
        if hit_identity(hit) not in previous_seen_hit_ids
        and _dedup_signature(hit) not in previous_signatures
    ]
    targets_by_algo = {target.k_algo: target for target in targets}
    payloads = [
        build_linear_issue_payload(hit, targets_by_algo[hit.k_algo])
        for hit in new_hits
        if hit.k_algo in targets_by_algo
    ]
    return CitationTrackingReport(
        generated_at=generated_at,
        targets_scanned=len(targets),
        hits_total=len(deduped_hits),
        hits_new=len(new_hits),
        scan_notes=scan_notes or [],
        source_failures=source_failures or [],
        unmatched_imports=unmatched_imports or [],
        malformed_imports=malformed_imports or [],
        new_hits=new_hits,
        all_hits=deduped_hits,
        linear_issue_payloads=payloads,
    )


def _seen_signatures(hits: Sequence[CitationHit]) -> set[tuple[str, str]]:
    return {_dedup_signature(hit) for hit in hits}


def _dedup_signature(hit: CitationHit) -> tuple[str, str]:
    normalized_url = _normalized_url(hit.url)
    if normalized_url is not None:
        return (hit.k_algo, f"url:{normalized_url}")
    return (hit.k_algo, f"id:{hit.external_id}")


def build_linear_issue_payload(hit: CitationHit, target: CitationTarget) -> dict[str, object]:
    title = f"[Citation] {hit.k_algo}: {_truncate(hit.title, 80)}"
    authors = ", ".join(hit.authors) if hit.authors else "unknown"
    description = "\n".join(
        [
            f"Detected a citation candidate for `{target.citation_key}`.",
            "",
            f"- Algorithm: `{hit.k_algo}`",
            f"- Citation key: `{hit.citation_key}`",
            f"- Source: `{hit.source}`",
            f"- Paper: {hit.title}",
            f"- URL: {hit.url or 'n/a'}",
            f"- Year: {hit.year if hit.year is not None else 'n/a'}",
            f"- Authors: {authors}",
            f"- Observed at: {hit.observed_at.isoformat()}",
            f"- External ID: `{hit.external_id}`",
            "",
            "Follow-up checklist:",
            "- [ ] verify paper actually cites OptiCloud/BibTeX entry",
            "- [ ] reply/thank author if appropriate",
            "- [ ] consider adding to monthly academic report",
            "- [ ] if false positive, mark duplicate/invalid",
        ]
    )
    return {
        "title": title,
        "description": description,
        "labels": ["academic", "citation-tracking", "story-6-a-3"],
        "metadata": {
            "k_algo": hit.k_algo,
            "citation_key": hit.citation_key,
            "source": hit.source,
            "external_id": hit.external_id,
        },
    }


async def create_linear_issues(
    payloads: Sequence[dict[str, object]],
    *,
    api_key: str,
    team_key: str,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, object]]:
    if not api_key or not team_key:
        raise ValueError("LINEAR_API_KEY and LINEAR_TEAM_KEY are required for --create-linear")

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)

    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier url }
      }
    }
    """
    results: list[dict[str, object]] = []
    try:
        for payload in payloads:
            try:
                response = await client.post(
                    LINEAR_GRAPHQL_URL,
                    headers={
                        "Authorization": api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "query": mutation,
                        "variables": {
                            "input": {
                                "teamId": team_key,
                                "title": payload["title"],
                                "description": payload["description"],
                                "labelIds": [],
                            }
                        },
                    },
                )
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                raise RuntimeError(f"Linear request failed: {type(exc).__name__}") from exc
            if response.status_code < 200 or response.status_code >= 300:
                raise RuntimeError(f"Linear returned HTTP {response.status_code}")
            try:
                body = response.json()
            except ValueError as exc:
                raise RuntimeError("Linear returned invalid JSON") from exc
            if body.get("errors"):
                raise RuntimeError("Linear GraphQL returned errors")
            issue_create = _issue_create_body(body)
            if issue_create is None or issue_create.get("success") is not True:
                raise RuntimeError("Linear issueCreate was not successful")
            results.append(body)
    finally:
        if owns_client:
            await client.aclose()
    return results


def _issue_create_body(body: Mapping[str, object]) -> Mapping[str, object] | None:
    data = body.get("data")
    if not isinstance(data, Mapping):
        return None
    issue_create = data.get("issueCreate")
    if not isinstance(issue_create, Mapping):
        return None
    return issue_create


def render_markdown_report(report: CitationTrackingReport) -> str:
    payload_json = json.dumps(
        report.linear_issue_payloads,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    lines = [
        "# Citation Tracking Dashboard",
        "",
        f"Generated: {report.generated_at.isoformat()}",
        f"Targets scanned: {report.targets_scanned}",
        f"Known hits: {report.hits_total}",
        f"New hits: {report.hits_new}",
        "",
        "## New Hits",
        "",
        "| k_algo | citation key | paper title | year | source | URL |",
        "|---|---|---|---|---|---|",
    ]
    if report.new_hits:
        for hit in report.new_hits:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(hit.k_algo),
                        _md_cell(hit.citation_key),
                        _md_cell(hit.title),
                        str(hit.year) if hit.year is not None else "",
                        hit.source,
                        _md_cell(hit.url or ""),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| _none_ |  |  |  |  |  |")

    lines.extend(
        [
            "",
            "## Known Total Hits",
            "",
            f"Total known hits in this run: {report.hits_total}",
            "",
            "## Source Failures",
            "",
            _details_or_none(report.source_failures),
            "",
            "## Scan Notes",
            "",
            _details_or_none(report.scan_notes),
            "",
            "## Unmatched Google Scholar Imports",
            "",
            _details_or_none(report.unmatched_imports),
            "",
            "## Malformed Google Scholar Imports",
            "",
            _details_or_none(report.malformed_imports),
            "",
            "## Linear Issue Payloads",
            "",
            "```json",
            payload_json,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def report_to_dict(report: CitationTrackingReport) -> dict[str, object]:
    return {
        "generated_at": report.generated_at.isoformat(),
        "targets_scanned": report.targets_scanned,
        "hits_total": report.hits_total,
        "hits_new": report.hits_new,
        "scan_notes": report.scan_notes,
        "source_failures": report.source_failures,
        "unmatched_imports": report.unmatched_imports,
        "malformed_imports": report.malformed_imports,
        "new_hits": [hit_to_dict(hit) for hit in report.new_hits],
        "all_hits": [hit_to_dict(hit) for hit in report.all_hits],
        "linear_issue_payloads": report.linear_issue_payloads,
    }


def hit_to_dict(hit: CitationHit) -> dict[str, object]:
    return {
        "source": hit.source,
        "k_algo": hit.k_algo,
        "citation_key": hit.citation_key,
        "external_id": hit.external_id,
        "title": hit.title,
        "url": hit.url,
        "year": hit.year,
        "authors": hit.authors,
        "observed_at": hit.observed_at.isoformat(),
    }


def hit_from_dict(data: Mapping[str, object]) -> CitationHit:
    observed_at = data.get("observed_at")
    if not isinstance(observed_at, str):
        observed_at = datetime.now(UTC).isoformat()
    authors_value = data.get("authors", [])
    authors = [str(author) for author in authors_value] if isinstance(authors_value, list) else []
    url_value = data.get("url")
    return CitationHit(
        source=cast(Literal["semantic_scholar", "google_scholar_import"], data["source"]),
        k_algo=str(data["k_algo"]),
        citation_key=str(data["citation_key"]),
        external_id=str(data["external_id"]),
        title=str(data["title"]),
        url=url_value if isinstance(url_value, str) else None,
        year=_int_or_none(data.get("year")),
        authors=authors,
        observed_at=datetime.fromisoformat(observed_at),
    )


def load_previous_state(path: Path) -> tuple[set[str], list[CitationHit]]:
    if not path.exists():
        return set(), []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping) or data.get("version") != 1:
        return set(), []
    seen_hit_ids = data.get("seen_hit_ids", [])
    hits = data.get("hits", [])
    return (
        {str(item) for item in seen_hit_ids if isinstance(item, str)},
        [hit_from_dict(item) for item in hits if isinstance(item, Mapping)],
    )


def write_state(path: Path, report: CitationTrackingReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": report.generated_at.isoformat(),
        "seen_hit_ids": sorted(hit_identity(hit) for hit in report.all_hits),
        "hits": [hit_to_dict(hit) for hit in report.all_hits],
    }
    tmp_path = path.with_suffix(".tmp") if path.suffix else path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)


def write_report(path: Path, report: CitationTrackingReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_markdown_report(path: Path, report: CitationTrackingReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(report), encoding="utf-8")


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _int_or_none(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _authors_from_s2(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    authors: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            name = _string_or_none(item.get("name"))
            if name is not None:
                authors.append(name)
        elif isinstance(item, str) and item.strip():
            authors.append(item.strip())
    return authors


def _authors_from_import(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str) or not value.strip():
        return []
    separator = ";" if ";" in value else None
    if separator is None:
        return [value.strip()]
    return [part.strip() for part in value.split(separator) if part.strip()]


def _fallback_external_id(title: str, citation_key: str) -> str:
    digest = hashlib.sha256(f"{title.lower()}:{citation_key}".encode()).hexdigest()
    return f"sha256:{digest}"


def _normalized_url(url: str | None) -> str | None:
    if url is None:
        return None
    parsed = urlsplit(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip().lower().rstrip("/") or None
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _md_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _details_or_none(items: Iterable[dict[str, str]]) -> str:
    item_list = list(items)
    if not item_list:
        return "_none_"
    return "\n".join(
        f"- `{json.dumps(item, ensure_ascii=False, sort_keys=True)}`" for item in item_list
    )


__all__ = [
    "CitationHit",
    "CitationTarget",
    "CitationTrackingReport",
    "ImportParseResult",
    "SemanticScholarFetchResult",
    "build_linear_issue_payload",
    "build_tracking_report",
    "create_linear_issues",
    "deduplicate_hits",
    "extract_citation_targets",
    "fetch_semantic_scholar_citations",
    "hit_identity",
    "hit_to_dict",
    "load_google_scholar_import",
    "load_previous_state",
    "render_markdown_report",
    "report_to_dict",
    "write_markdown_report",
    "write_report",
    "write_state",
]
