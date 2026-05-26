from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_gtm_toolkit",
        ROOT / "scripts" / "validate_gtm_toolkit.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_gtm_toolkit_contract_validates() -> None:
    module = load_validator_module()

    errors = module.validate_repository(ROOT)

    assert errors == []


def test_manifest_required_categories_and_paths() -> None:
    manifest = json.loads((ROOT / "tools/gtm_toolkit/gtm_toolkit_manifest.json").read_text())

    categories = {asset["category"] for asset in manifest["assets"]}
    assert categories == {
        "customer_story",
        "pricing_optimization",
        "customer_faq",
        "procurement_template",
        "sales_collateral",
        "customer_success",
        "lighthouse_slo",
    }
    assert manifest["out_of_scope"] == ["m4-5b-gurobi-benchmark-whitepaper"]

    paths = {asset["path"] for asset in manifest["assets"]}
    assert "docs/enterprise-gtm-toolkit.md" in paths
    assert "docs/gtm/customer-stories/logistics-dispatch-spotlight.md" in paths
    assert "docs/gtm/customer-stories/energy-forecasting-spotlight.md" in paths
    assert "docs/gtm/pricing-page-optimization.md" in paths
    assert "docs/customer-faqs/commercial-buyer-faq.md" in paths
    assert "docs/customer-faqs/technical-evaluator-faq.md" in paths


def test_pricing_page_i18n_wiring_and_plan_labels() -> None:
    zh = json.loads((ROOT / "apps/web/src/i18n/messages/zh-CN.json").read_text(encoding="utf-8"))
    en = json.loads((ROOT / "apps/web/src/i18n/messages/en-US.json").read_text(encoding="utf-8"))
    page = (ROOT / "apps/web/src/app/pricing/page.tsx").read_text(encoding="utf-8")

    for messages in (zh, en):
        pricing = messages["pricing"]
        assert set(pricing["plans"]) == {"free", "starter", "pro", "team", "enterprise"}
        assert "buyerSafeCaveat" in pricing
        assert "docsCta" in pricing

    assert 'const PLAN_KEYS = ["free", "starter", "pro", "team", "enterprise"] as const' in page
    assert 't("buyerSafeCaveat")' in page
    assert 'href="/docs/quickstart"' in page


def test_ci_path_filter_covers_gtm_assets() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "gtm_toolkit:" in ci
    for expected in (
        "docs/gtm/**",
        "docs/customer-faqs/**",
        "docs/enterprise-gtm-toolkit.md",
        "tools/gtm_toolkit/**",
        "scripts/validate_gtm_toolkit.py",
        "tests/test_gtm_toolkit.py",
        "apps/web/src/app/pricing/page.tsx",
        "apps/web/src/i18n/messages/zh-CN.json",
        "apps/web/src/i18n/messages/en-US.json",
    ):
        assert expected in ci
    assert "gtm-toolkit-validation" in ci
    assert "uv run python scripts/validate_gtm_toolkit.py" in ci


def test_validator_rejects_fabricated_claims_and_pii(tmp_path: Path) -> None:
    module = load_validator_module()
    bad_story = tmp_path / "bad-story.md"
    bad_story.write_text(
        "\n".join(
            [
                "---",
                "status: published",
                "claim_status: verified",
                "evidence_status: verified",
                "consent_status: signed",
                "---",
                "# Bad Story",
                "OptiCloud is SOC 2 Type II certified with ISO 27001 certification.",
                "Call 张伟 at 13812345678 or zhang@example.com for the signed customer logo.",
            ]
        ),
        encoding="utf-8",
    )

    errors = module.validate_markdown_asset(
        root=tmp_path,
        path=Path("bad-story.md"),
        category="customer_story",
        required_fields=["status", "claim_status", "evidence_status", "consent_status"],
    )

    assert any("unsupported certification/SLA/logo claim" in error for error in errors)
    assert any("real-looking PII" in error for error in errors)


def test_validator_rejects_m45b_scope_drift(tmp_path: Path) -> None:
    module = load_validator_module()
    bad_doc = tmp_path / "benchmark.md"
    bad_doc.write_text(
        "M4.5b 30 LP Gurobi benchmark results show OptiCloud beats Gurobi.",
        encoding="utf-8",
    )

    errors = module.validate_markdown_asset(
        root=tmp_path,
        path=Path("benchmark.md"),
        category="sales_collateral",
        required_fields=[],
    )

    assert any("M4.5b benchmark scope" in error for error in errors)


def test_validator_allows_only_narrow_m45b_boundary_phrase(tmp_path: Path) -> None:
    module = load_validator_module()
    boundary_doc = tmp_path / "boundary.md"
    boundary_doc.write_text(
        "Benchmark claims belong to the separate M4.5b story.",
        encoding="utf-8",
    )
    bad_doc = tmp_path / "bad-boundary.md"
    bad_doc.write_text(
        "Benchmark claims belong to the separate M4.5b story, and OptiCloud beats Gurobi.",
        encoding="utf-8",
    )

    allowed_errors = module.validate_markdown_asset(
        root=tmp_path,
        path=Path("boundary.md"),
        category="customer_faq",
        required_fields=[],
    )
    rejected_errors = module.validate_markdown_asset(
        root=tmp_path,
        path=Path("bad-boundary.md"),
        category="customer_faq",
        required_fields=[],
    )

    assert not any("M4.5b benchmark scope" in error for error in allowed_errors)
    assert any("M4.5b benchmark scope" in error for error in rejected_errors)
