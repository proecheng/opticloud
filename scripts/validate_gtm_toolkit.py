from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_CATEGORIES = {
    "customer_story",
    "pricing_optimization",
    "customer_faq",
    "procurement_template",
    "sales_collateral",
    "customer_success",
    "lighthouse_slo",
}
ALLOWED_STATUSES = {
    "draft",
    "internal_ready",
    "legal_review_required",
    "evidence_required",
    "published",
}
ALLOWED_CLAIM_STATUSES = {
    "hypothesis",
    "source_supported",
    "operator_evidence_required",
    "consent_required",
    "verified",
}
ALLOWED_EVIDENCE_STATUSES = {
    "hypothesis",
    "source_supported",
    "operator_evidence_required",
    "consent_required",
    "verified",
}
ALLOWED_PREFIXES = (
    "docs/gtm/",
    "docs/customer-faqs/",
    "docs/enterprise-gtm-toolkit.md",
    "apps/web/src/app/pricing/page.tsx",
    "apps/web/src/i18n/messages/zh-CN.json",
    "apps/web/src/i18n/messages/en-US.json",
)
PLAN_KEYS = {"free", "starter", "pro", "team", "enterprise"}
PLAN_LABELS = {"Free", "Starter", "Pro", "Team", "Enterprise"}
FORBIDDEN_ANALYTICS = ("gtag(", "googletagmanager", "segment.com", "mixpanel", "amplitude")
M45B_TERMS = ("m4.5b", "30 lp", "benchmark results", "beats gurobi", "outperform gurobi")
ALLOWED_M45B_BOUNDARY_PHRASES = (
    "the 30 lp benchmark whitepaper is story `m4-5b-gurobi-benchmark-whitepaper` and remains out of scope",
    "benchmark claims belong to the separate m4.5b story",
    "keep benchmark or comparison claims for the separate m4.5b story",
)
PII_PATTERNS = (
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
)


def _repo_path(path: Path) -> str:
    return path.as_posix()


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"')
    return fields


def _has_real_pii(text: str) -> bool:
    return any(pattern.search(text) for pattern in PII_PATTERNS)


def _has_unsupported_claim(text: str) -> bool:
    lowered = text.lower()
    suspicious = (
        "soc 2 type ii certified",
        "iso 27001 certification",
        "iso 27001 certified",
        "aigc filing approved",
        "99.9% sla",
        "signed customer logo",
        "published production case study",
    )
    return any(term in lowered for term in suspicious)


def _has_m45b_scope_drift(text: str) -> bool:
    lowered = text.lower()
    cleaned = lowered
    for phrase in ALLOWED_M45B_BOUNDARY_PHRASES:
        cleaned = cleaned.replace(phrase, "")
    return any(term in cleaned for term in M45B_TERMS)


def _has_external_analytics(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in FORBIDDEN_ANALYTICS)


def _has_future_live_url(text: str) -> bool:
    return "https://opticloud.cn/migrate" in text or "https://opticloud.cn/gtm" in text


def validate_markdown_asset(
    root: Path,
    path: Path,
    category: str,
    required_fields: list[str],
) -> list[str]:
    errors: list[str] = []
    asset_path = root / path
    display_path = _repo_path(path)
    if not asset_path.exists():
        return [f"{display_path}: missing asset"]
    text = asset_path.read_text(encoding="utf-8")
    fields = _parse_frontmatter(text)

    for field in required_fields:
        if field not in fields:
            errors.append(f"{display_path}: missing frontmatter field {field}")

    status = fields.get("status")
    if status is not None and status not in ALLOWED_STATUSES:
        errors.append(f"{display_path}: invalid status {status}")
    claim_status = fields.get("claim_status")
    if claim_status is not None and claim_status not in ALLOWED_CLAIM_STATUSES:
        errors.append(f"{display_path}: invalid claim_status {claim_status}")
    evidence_status = fields.get("evidence_status")
    if evidence_status is not None and evidence_status not in ALLOWED_EVIDENCE_STATUSES:
        errors.append(f"{display_path}: invalid evidence_status {evidence_status}")

    if category == "customer_story":
        for heading in ("## Assumptions", "## Source-Supported Facts", "## Observed Evidence"):
            if heading not in text:
                errors.append(f"{display_path}: missing customer story section {heading}")
        if fields.get("status") == "published" and fields.get("evidence_status") != "verified":
            errors.append(f"{display_path}: published story requires verified evidence")
        if fields.get("status") == "published" and fields.get("consent_status") != "signed":
            errors.append(f"{display_path}: published story requires signed consent")

    if _has_unsupported_claim(text):
        errors.append(f"{display_path}: unsupported certification/SLA/logo claim")
    if _has_real_pii(text):
        errors.append(f"{display_path}: real-looking PII")
    if _has_external_analytics(text):
        errors.append(f"{display_path}: external analytics snippet")
    if _has_future_live_url(text):
        errors.append(f"{display_path}: future live marketing URL")
    if _has_m45b_scope_drift(text):
        errors.append(f"{display_path}: M4.5b benchmark scope drift")

    return errors


def _validate_manifest(root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = root / "tools/gtm_toolkit/gtm_toolkit_manifest.json"
    schema_path = root / "tools/gtm_toolkit/gtm_toolkit_manifest.schema.json"
    if not manifest_path.exists():
        return ["tools/gtm_toolkit/gtm_toolkit_manifest.json: missing manifest"]
    if not schema_path.exists():
        errors.append(
            "tools/gtm_toolkit/gtm_toolkit_manifest.schema.json: missing schema reference"
        )
    else:
        schema = _load_json(schema_path)
        required = set(schema.get("required", []))
        for field in ("story_key", "stage", "source_gap", "assets", "out_of_scope"):
            if field not in required:
                errors.append(f"manifest schema: missing required field {field}")

    manifest = _load_json(manifest_path)
    if manifest.get("story_key") != "m4-5-gtm-toolkit":
        errors.append("manifest: story_key must be m4-5-gtm-toolkit")
    if manifest.get("stage") != "M4.5":
        errors.append("manifest: stage must be M4.5")
    if manifest.get("out_of_scope") != ["m4-5b-gurobi-benchmark-whitepaper"]:
        errors.append("manifest: out_of_scope must pin m4-5b-gurobi-benchmark-whitepaper")

    assets = manifest.get("assets", [])
    if not isinstance(assets, list) or not assets:
        return errors + ["manifest: assets must be a non-empty list"]

    categories = {asset.get("category") for asset in assets}
    if categories != REQUIRED_CATEGORIES:
        errors.append(f"manifest: categories drifted {sorted(categories)}")

    customer_story_count = 0
    for asset in assets:
        path_value = asset.get("path")
        category = asset.get("category")
        if not isinstance(path_value, str) or not isinstance(category, str):
            errors.append("manifest: every asset needs string path and category")
            continue
        if not path_value.startswith(ALLOWED_PREFIXES):
            errors.append(f"{path_value}: path outside allowed GTM locations")
        if asset.get("status") not in ALLOWED_STATUSES:
            errors.append(f"{path_value}: invalid manifest status")
        if asset.get("claim_status") not in ALLOWED_CLAIM_STATUSES:
            errors.append(f"{path_value}: invalid manifest claim_status")
        if asset.get("evidence_status") not in ALLOWED_EVIDENCE_STATUSES:
            errors.append(f"{path_value}: invalid manifest evidence_status")
        if not asset.get("source_refs"):
            errors.append(f"{path_value}: missing source_refs")
        if not asset.get("required_fields"):
            errors.append(f"{path_value}: missing required_fields")
        if category == "customer_story":
            customer_story_count += 1
        if path_value.endswith(".md"):
            errors.extend(
                validate_markdown_asset(
                    root=root,
                    path=Path(path_value),
                    category=category,
                    required_fields=list(asset.get("required_fields", [])),
                )
            )
        elif not (root / path_value).exists():
            errors.append(f"{path_value}: missing asset")

    if customer_story_count < 2:
        errors.append("manifest: at least two customer_story assets required")
    return errors


def _validate_pricing(root: Path) -> list[str]:
    errors: list[str] = []
    zh = _load_json(root / "apps/web/src/i18n/messages/zh-CN.json")
    en = _load_json(root / "apps/web/src/i18n/messages/en-US.json")
    page_path = root / "apps/web/src/app/pricing/page.tsx"
    page = page_path.read_text(encoding="utf-8")

    for locale, messages in (("zh-CN", zh), ("en-US", en)):
        pricing = messages.get("pricing", {})
        plans = pricing.get("plans", {})
        if set(plans) != PLAN_KEYS:
            errors.append(f"{locale}: pricing plan keys must be {sorted(PLAN_KEYS)}")
        if "buyerSafeCaveat" not in pricing:
            errors.append(f"{locale}: pricing buyerSafeCaveat missing")
        if "docsCta" not in pricing:
            errors.append(f"{locale}: pricing docsCta missing")
        for key, plan in plans.items():
            if "name" not in plan or "summary" not in plan:
                errors.append(f"{locale}: pricing plan {key} missing name/summary")

    if 'const PLAN_KEYS = ["free", "starter", "pro", "team", "enterprise"] as const' not in page:
        errors.append("pricing page: missing canonical PLAN_KEYS")
    if 't("buyerSafeCaveat")' not in page:
        errors.append("pricing page: missing buyer-safe caveat")
    if 'href="/docs/quickstart"' not in page:
        errors.append("pricing page: missing docs quickstart link")
    if _has_external_analytics(page):
        errors.append("pricing page: external analytics snippet")

    pricing_doc = (root / "docs/gtm/pricing-page-optimization.md").read_text(encoding="utf-8")
    for label in PLAN_LABELS:
        if label not in pricing_doc:
            errors.append(f"pricing doc: missing canonical plan label {label}")
    if "commercial_hypothesis" not in pricing_doc or "current_runtime" not in pricing_doc:
        errors.append("pricing doc: missing claim-source status markers")
    return errors


def _validate_faq_coverage(root: Path) -> list[str]:
    errors: list[str] = []
    combined = "\n".join(
        [
            (root / "docs/customer-faqs/commercial-buyer-faq.md").read_text(encoding="utf-8"),
            (root / "docs/customer-faqs/technical-evaluator-faq.md").read_text(encoding="utf-8"),
        ]
    ).lower()
    for term in (
        "security",
        "data retention",
        "credits",
        "refund",
        "reproducibility",
        "academic",
        "enterprise",
        "gurobi",
        "support",
    ):
        if term not in combined:
            errors.append(f"customer FAQ: missing coverage for {term}")
    return errors


def _validate_ci(root: Path) -> list[str]:
    errors: list[str] = []
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    expected = (
        "gtm_toolkit:",
        "docs/gtm/**",
        "docs/customer-faqs/**",
        "docs/enterprise-gtm-toolkit.md",
        "tools/gtm_toolkit/**",
        "scripts/validate_gtm_toolkit.py",
        "tests/test_gtm_toolkit.py",
        "apps/web/src/app/pricing/page.tsx",
        "apps/web/src/i18n/messages/zh-CN.json",
        "apps/web/src/i18n/messages/en-US.json",
        "gtm-toolkit-validation",
        "uv run python scripts/validate_gtm_toolkit.py",
        "uv run pytest tests/test_gtm_toolkit.py",
    )
    for item in expected:
        if item not in ci:
            errors.append(f"ci: missing {item}")
    return errors


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve()
    if (root / "reports/gtm-toolkit").exists():
        errors.append("reports/gtm-toolkit: committed evidence not supported by M4.5")
    errors.extend(_validate_manifest(root))
    errors.extend(_validate_pricing(root))
    errors.extend(_validate_faq_coverage(root))
    errors.extend(_validate_ci(root))
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    errors = validate_repository(root)
    if errors:
        for error in errors:
            sys.stderr.write(f"ERROR: {error}\n")
        return 1
    sys.stdout.write("gtm toolkit OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
