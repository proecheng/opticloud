from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_rule_module():
    spec = importlib.util.spec_from_file_location(
        "error_message_i18n_single_source",
        ROOT / "scripts" / "error_message_i18n_single_source.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_dictionary(root: Path, name: str, keys: list[str]) -> None:
    directory = root / "packages" / "i18n"
    directory.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# Test dictionary",
        "errors:",
    ]
    tree: dict[str, dict[str, str]] = {}
    for key in keys:
        _, status, code = key.split(".", 2)
        tree.setdefault(status, {})[code] = key
    for status, entries in tree.items():
        lines.append(f"  {status}:")
        for code, key in entries.items():
            lines.extend(
                [
                    f"    {code}:",
                    f'      title: "Title for {key}"',
                    f'      detail: "Detail for {key}"',
                    f'      remediation: "Remediation for {key}"',
                ]
            )
    (directory / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_committed_error_dictionaries_validate() -> None:
    module = load_rule_module()

    errors = module.validate_repository(ROOT)

    assert errors == []


def test_hardcoded_problem_title_and_detail_fail_with_actionable_output(tmp_path: Path) -> None:
    module = load_rule_module()
    write_dictionary(
        tmp_path,
        "errors.zh-CN.yaml",
        ["errors.422.invalid_prediction_data"],
    )
    write_dictionary(
        tmp_path,
        "errors.en-US.yaml",
        ["errors.422.invalid_prediction_data"],
    )
    source = tmp_path / "apps" / "web" / "src" / "lib" / "bad.ts"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        """
export const bad = {
  status: 422,
  title: "Invalid Prediction Data",
  detail: "horizon must be between 1 and 90",
  errors: [
    {
      field_path: "body.horizon",
      value: 120,
      constraint: "too high",
      remediation_hint_key: "errors.422.invalid_prediction_data",
    },
  ],
};
""",
        encoding="utf-8",
    )

    errors = module.validate_repository(tmp_path)

    assert any("error-message-i18n-single-source" in error for error in errors)
    assert any("apps/web/src/lib/bad.ts" in error for error in errors)
    assert any("title" in error for error in errors)
    assert any("detail" in error for error in errors)
    assert any("packages/i18n/errors.zh-CN.yaml" in error for error in errors)


def test_nested_problem_object_and_single_quoted_strings_are_rejected(tmp_path: Path) -> None:
    module = load_rule_module()
    write_dictionary(
        tmp_path,
        "errors.zh-CN.yaml",
        ["errors.422.invalid_prediction_data"],
    )
    write_dictionary(
        tmp_path,
        "errors.en-US.yaml",
        ["errors.422.invalid_prediction_data"],
    )
    source = tmp_path / "apps" / "web" / "src" / "lib" / "nested.ts"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        """
export const bad = {
  meta: { source: "client" },
  title: 'Invalid Prediction Data',
  status: 422,
  detail: 'horizon must be between 1 and 90',
  errors: [{ field_path: "body.horizon", constraint: "too high", remediation_hint_key: "errors.422.invalid_prediction_data" }],
};
""",
        encoding="utf-8",
    )

    errors = module.validate_repository(tmp_path)

    assert sum("hard-coded RFC 7807 title" in error for error in errors) == 1
    assert sum("hard-coded RFC 7807 detail" in error for error in errors) == 1


def test_valid_remediation_key_passes_when_dictionary_contains_key(tmp_path: Path) -> None:
    module = load_rule_module()
    write_dictionary(
        tmp_path,
        "errors.zh-CN.yaml",
        ["errors.429.rate_limit_exceeded"],
    )
    write_dictionary(
        tmp_path,
        "errors.en-US.yaml",
        ["errors.429.rate_limit_exceeded"],
    )
    source = tmp_path / "packages" / "ui" / "src" / "problem.ts"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        """
export const detail = {
  field_path: "rate_limit",
  value: "starter",
  constraint: getConstraint(),
  remediation_hint_key: "errors.429.rate_limit_exceeded",
};
""",
        encoding="utf-8",
    )

    errors = module.validate_repository(tmp_path)

    assert errors == []


def test_title_and_detail_i18n_keys_are_allowed_when_dictionary_contains_key(
    tmp_path: Path,
) -> None:
    module = load_rule_module()
    write_dictionary(
        tmp_path,
        "errors.zh-CN.yaml",
        ["errors.fallback.request_failed"],
    )
    write_dictionary(
        tmp_path,
        "errors.en-US.yaml",
        ["errors.fallback.request_failed"],
    )
    source = tmp_path / "apps" / "web" / "src" / "lib" / "fallback.ts"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        """
export const fallback = {
  status: 500,
  title: "errors.fallback.request_failed",
  detail: "errors.fallback.request_failed",
  errors: [{ field_path: "response.body", constraint: getConstraint(), remediation_hint_key: "errors.fallback.request_failed" }],
};
""",
        encoding="utf-8",
    )

    errors = module.validate_repository(tmp_path)

    assert errors == []


def test_missing_or_invalid_remediation_key_fails(tmp_path: Path) -> None:
    module = load_rule_module()
    write_dictionary(tmp_path, "errors.zh-CN.yaml", ["errors.402.topup"])
    write_dictionary(tmp_path, "errors.en-US.yaml", ["errors.402.topup"])
    source = tmp_path / "apps" / "web" / "src" / "bad-key.tsx"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(
        """
export const invalid = {
  field_path: "body.amount",
  value: 0,
  constraint: getConstraint(),
  remediation_hint_key: "billing.topup",
};

export const missing = {
  field_path: "rate_limit",
  value: "starter",
  constraint: getConstraint(),
  remediation_hint_key: "errors.429.rate_limit_exceeded",
};
""",
        encoding="utf-8",
    )

    errors = module.validate_repository(tmp_path)

    assert any("must start with errors." in error for error in errors)
    assert any("not found in packages/i18n/errors.zh-CN.yaml" in error for error in errors)


def test_dictionary_schema_and_key_parity_failures_are_reported(tmp_path: Path) -> None:
    module = load_rule_module()
    dictionary_dir = tmp_path / "packages" / "i18n"
    dictionary_dir.mkdir(parents=True)
    (dictionary_dir / "errors.zh-CN.yaml").write_text(
        """
errors:
  402:
    topup:
      title: "Insufficient Credits"
      detail: ""
      remediation: "Top up credits"
""",
        encoding="utf-8",
    )
    write_dictionary(tmp_path, "errors.en-US.yaml", ["errors.429.rate_limit_exceeded"])

    errors = module.validate_repository(tmp_path)

    assert any("errors.402.topup.detail must be non-empty" in error for error in errors)
    assert any("dictionary key parity drift" in error for error in errors)


def test_ignored_files_do_not_trigger_problem_string_failures(tmp_path: Path) -> None:
    module = load_rule_module()
    write_dictionary(tmp_path, "errors.zh-CN.yaml", ["errors.422.invalid_prediction_data"])
    write_dictionary(tmp_path, "errors.en-US.yaml", ["errors.422.invalid_prediction_data"])
    ignored_paths = [
        "apps/web/src/lib/problem.test.ts",
        "packages/ui/src/components/Error/index.stories.tsx",
        "packages/ui/src/components/Error/index.a11y.test.tsx",
        "apps/web/src/i18n/messages/zh-CN.json",
        "packages/shared-ts/openapi/solver.json",
        "_bmad-output/stories/example.md",
        "packages/i18n/fixture.ts",
    ]
    for path_value in ignored_paths:
        path = tmp_path / path_value
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            'export const bad = { status: 422, title: "Bad", detail: "Bad", errors: [] };\n',
            encoding="utf-8",
        )

    errors = module.validate_repository(tmp_path)

    assert errors == []


def test_ci_path_filter_covers_error_i18n_gate() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "error_i18n:" in ci
    for expected in (
        "packages/i18n/**",
        "scripts/error_message_i18n_single_source.py",
        "tests/test_error_i18n_single_source.py",
        ".pre-commit-config.yaml",
        "package.json",
    ):
        assert expected in ci
    assert "error-i18n-validation" in ci
    assert "uv run pytest tests/test_error_i18n_single_source.py -v" in ci
