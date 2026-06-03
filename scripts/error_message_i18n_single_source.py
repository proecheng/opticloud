from __future__ import annotations

import re
import sys
from pathlib import Path

RULE_ID = "error-message-i18n-single-source"
ZH_DICTIONARY = Path("packages/i18n/errors.zh-CN.yaml")
EN_DICTIONARY = Path("packages/i18n/errors.en-US.yaml")
REQUIRED_FIELDS = ("title", "detail", "remediation")
REQUIRED_ZH_KEYS = {
    "errors.402.topup",
    "errors.422.invalid_prediction_data",
    "errors.422.invalid_job_template",
    "errors.422.source_task_not_completed",
    "errors.429.rate_limit_exceeded",
    "errors.503.rate_limit_unavailable",
    "errors.fallback.request_failed",
    "errors.fallback.network_error",
}
SOURCE_ROOTS = (
    Path("apps/web/src"),
    Path("packages/ui/src"),
    Path("packages/shared-ts/src"),
)
FIELD_STRING_PATTERN = re.compile(
    r"\b(?P<field>title|detail|remediation_hint_key)\s*:\s*"
    r"(?:\"(?P<double>(?:\\.|[^\"\\])*)\"|'(?P<single>(?:\\.|[^'\\])*)')"
)
REMEDIATION_KEY_PATTERN = re.compile(r"^errors\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


class DictionaryResult:
    def __init__(self, entries: dict[str, dict[str, str]], errors: list[str]) -> None:
        self.entries = entries
        self.errors = errors


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    zh = parse_error_dictionary(root / ZH_DICTIONARY, ZH_DICTIONARY)
    en = parse_error_dictionary(root / EN_DICTIONARY, EN_DICTIONARY)
    errors = zh.errors + en.errors

    if zh.entries and en.entries:
        zh_keys = set(zh.entries)
        en_keys = set(en.entries)
        if zh_keys != en_keys:
            missing_en = sorted(zh_keys - en_keys)
            missing_zh = sorted(en_keys - zh_keys)
            errors.append(
                f"{RULE_ID}: dictionary key parity drift between {_display(ZH_DICTIONARY)} "
                f"and {_display(EN_DICTIONARY)}; missing_en={missing_en}; missing_zh={missing_zh}"
            )

    if zh.entries and (root / ".git").exists():
        missing_required = sorted(REQUIRED_ZH_KEYS - set(zh.entries))
        for key in missing_required:
            errors.append(f"{RULE_ID}: required key {key} missing from {_display(ZH_DICTIONARY)}")

    errors.extend(validate_sources(root, zh.entries))
    return errors


def parse_error_dictionary(path: Path, display_path: Path) -> DictionaryResult:
    if not path.exists():
        return DictionaryResult({}, [f"{RULE_ID}: missing dictionary {display_path}"])

    entries: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    seen_paths: set[tuple[str, ...]] = set()
    stack: list[tuple[int, str]] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent % 2 != 0:
            errors.append(f"{display_path}:{line_number}: indentation must use two-space levels")
            continue
        if ":" not in stripped:
            errors.append(f"{display_path}:{line_number}: expected key/value mapping")
            continue

        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        path_parts = tuple(part for _, part in stack) + (key,)
        if path_parts in seen_paths:
            errors.append(f"{display_path}:{line_number}: duplicate key {'.'.join(path_parts)}")
        seen_paths.add(path_parts)

        if value == "":
            stack.append((indent, key))
            continue

        if len(path_parts) != 4 or path_parts[0] != "errors":
            errors.append(f"{display_path}:{line_number}: unexpected scalar {'.'.join(path_parts)}")
            continue
        field = path_parts[3]
        if field not in REQUIRED_FIELDS:
            errors.append(f"{display_path}:{line_number}: unsupported field {field}")
            continue
        error_key = f"errors.{path_parts[1]}.{path_parts[2]}"
        entries.setdefault(error_key, {})[field] = _unquote(value)

    if not entries and not errors:
        errors.append(f"{RULE_ID}: {display_path} must define errors.* entries")

    for error_key, fields in sorted(entries.items()):
        for field in REQUIRED_FIELDS:
            value = fields.get(field)
            if value is None:
                errors.append(f"{display_path}: {error_key}.{field} is missing")
            elif not value.strip():
                errors.append(f"{display_path}: {error_key}.{field} must be non-empty")

    return DictionaryResult(entries, errors)


def validate_sources(root: Path, dictionary_entries: dict[str, dict[str, str]]) -> list[str]:
    errors: list[str] = []
    dictionary_keys = set(dictionary_entries)
    for source in iter_source_files(root):
        text = source.read_text(encoding="utf-8")
        display_path = source.relative_to(root).as_posix()
        for match in FIELD_STRING_PATTERN.finditer(text):
            field = match.group("field")
            raw_value = match.group("double") if match.group("double") is not None else match.group("single") or ""
            value = _unescape(raw_value)
            line = text.count("\n", 0, match.start()) + 1

            if field == "remediation_hint_key":
                if not REMEDIATION_KEY_PATTERN.match(value):
                    errors.append(
                        f"{display_path}:{line}: {RULE_ID}: remediation_hint_key "
                        f"must start with errors. and match errors.<scope>.<name>; "
                        f"add or correct the key in {_display(ZH_DICTIONARY)}"
                    )
                elif value not in dictionary_keys:
                    errors.append(
                        f"{display_path}:{line}: {RULE_ID}: remediation_hint_key "
                        f"{value!r} not found in {_display(ZH_DICTIONARY)}"
                    )
                continue

            if is_problem_detail_context(text, match.start()):
                if value.startswith("errors."):
                    if value not in dictionary_keys:
                        errors.append(
                            f"{display_path}:{line}: {RULE_ID}: {field} key "
                            f"{value!r} not found in {_display(ZH_DICTIONARY)}"
                        )
                    continue
                errors.append(
                    f"{display_path}:{line}: {RULE_ID}: hard-coded RFC 7807 {field} "
                    f"string is not allowed; move the message to {_display(ZH_DICTIONARY)}"
                )
    return errors


def iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for source_root in SOURCE_ROOTS:
        absolute_root = root / source_root
        if not absolute_root.exists():
            continue
        for path in absolute_root.rglob("*"):
            if path.is_file() and path.suffix in {".ts", ".tsx"} and not is_ignored_source(root, path):
                files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def is_ignored_source(root: Path, path: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    name = path.name
    if name.endswith((".test.ts", ".test.tsx", ".a11y.test.tsx", ".stories.tsx", ".d.ts")):
        return True
    if "/i18n/messages/" in relative:
        return True
    if relative.startswith("packages/shared-ts/openapi/"):
        return True
    if relative.startswith("packages/i18n/"):
        return True
    if relative.startswith("_bmad-output/"):
        return True
    return False


def is_problem_detail_context(text: str, position: int) -> bool:
    start = text.rfind("{", 0, position)
    while start != -1:
        end = find_matching_brace(text, start)
        if end is not None and end >= position:
            block = text[start : end + 1]
            has_status = (
                re.search(r"\bstatus\s*:\s*(?:\d|[A-Za-z_][A-Za-z0-9_.]*)", block)
                is not None
            )
            has_problem_marker = any(
                marker in block
                for marker in (
                    "errors",
                    "next_action_url",
                    "request_id",
                    "trace_id",
                    "remediation_hint_key",
                )
            )
            has_error_detail = "field_path" in block and "constraint" in block
            if (has_status and has_problem_marker) or has_error_detail:
                return True
        start = text.rfind("{", 0, start)
    return False


def find_matching_brace(text: str, start: int) -> int | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return _unescape(value[1:-1])
    return value


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")


def _display(path: Path) -> str:
    return path.as_posix()


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    errors = validate_repository(root)
    if errors:
        for error in errors:
            sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(f"{RULE_ID}: OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
