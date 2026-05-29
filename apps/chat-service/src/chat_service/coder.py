from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from opticloud_shared.llm_router import Completion, LLMRouterError, Prompt, PromptMessage, complete
from opticloud_shared.llm_router.registry import CANONICAL_MODEL_ALIASES
from pydantic import ValidationError

from chat_service.router_preview import SUPPORTED_TASK_TYPES
from chat_service.schemas import (
    ChatLocale,
    CoderCodeArtifact,
    CoderPreview,
    CoderPreviewSource,
    CoderValidationError,
    FormulatorPreview,
    TaskType,
)

CompletionFunc = Callable[[Prompt, str], Completion]

LLM_CODER_SOURCE: CoderPreviewSource = "llm_coder_internal_beta"
TEMPLATE_CODER_SOURCE: CoderPreviewSource = "template_coder_internal_beta"
HEURISTIC_CODER_SOURCE: CoderPreviewSource = "heuristic_coder_internal_beta"
_DETERMINISTIC_MARKER = "coder generation"
_SECRET_PATTERN = re.compile(
    r"(sk-[A-Za-z0-9_-]{4,}|api[_-]?key|bearer\s+[A-Za-z0-9._-]+|"
    r"authorization|cookie|password|token|raw_response|provider_request|provider_response|"
    r"deterministic_digest)",
    re.IGNORECASE,
)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```")
_ALLOWED_IMPORTS = {"pydantic", "typing", "math", "statistics", "datetime", "json", "decimal"}
_BLOCKED_RUNTIME_SYMBOLS = {
    "builtins",
    "httpx",
    "importlib",
    "ortools",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
}
_DANGEROUS_CALLS = {
    "__import__",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}

CODER_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "task_type": {"type": "string", "enum": list(SUPPORTED_TASK_TYPES)},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "artifact": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["python"]},
                "code": {"type": "string"},
                "entrypoint": {"type": "string"},
                "input_model": {"type": "string"},
                "output_model": {"type": "string"},
                "imports": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "language",
                "code",
                "entrypoint",
                "input_model",
                "output_model",
                "imports",
            ],
        },
        "validation_errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_path": {"type": "string"},
                    "message": {"type": "string"},
                    "remediation_hint_key": {"type": "string"},
                },
                "required": ["field_path", "message"],
            },
        },
    },
    "required": ["task_type", "artifact"],
}


@dataclass(frozen=True)
class CoderRouteResult:
    preview: CoderPreview
    coder_invoked: bool
    provider_request_sent: Literal[False] = False


def build_coder_prompt(
    *,
    message: str,
    locale: ChatLocale,
    prompt_id: str,
    formulator_preview: FormulatorPreview,
) -> Prompt:
    return Prompt(
        prompt_id=prompt_id,
        task="coder_generation",
        locale=locale,
        messages=[
            PromptMessage(
                role="system",
                content=(
                    "Generate a safe Python code artifact preview for the structured "
                    "OptiCloud task. Return JSON with task_type and artifact only. "
                    "Do not execute code, call solvers, use network, or access files."
                ),
            ),
            PromptMessage(
                role="user",
                content=json.dumps(
                    {
                        "formulator_preview": {
                            "status": formulator_preview.status,
                            "task_type": formulator_preview.task_type,
                            "variables": formulator_preview.variables,
                            "objective": formulator_preview.objective,
                            "constraints": formulator_preview.constraints,
                            "validation_errors": [
                                error.model_dump(exclude_none=True)
                                for error in formulator_preview.validation_errors
                            ],
                        },
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        ],
        response_schema=CODER_RESPONSE_SCHEMA,
        metadata={"formulator_task_type": formulator_preview.task_type},
    )


def parse_coder_completion(
    text: str,
    *,
    formulator_preview: FormulatorPreview,
    original_message: str | None = None,
) -> CoderPreview | None:
    if formulator_preview.status != "extracted":
        return _non_extracted_preview(formulator_preview)

    if not _formulator_has_codegen_content(formulator_preview):
        return _clarification_preview(
            formulator_preview.task_type,
            field_path="formulator_preview.variables",
            message="structured formulation is required before code generation",
            remediation_hint_key="chat.coder.formulator_extracted_required",
        )

    if _looks_like_deterministic_text(text):
        return _template_preview(formulator_preview, original_message=original_message)

    payload = _parse_json_payload(text)
    if payload is None:
        return None
    if _payload_contains_unsafe_text(payload, original_message=original_message):
        return None

    confidence = payload.get("confidence")
    if confidence is not None and (
        not isinstance(confidence, int | float) or not 0.0 <= float(confidence) <= 1.0
    ):
        return None

    task_type = payload.get("task_type")
    if task_type not in SUPPORTED_TASK_TYPES or task_type != formulator_preview.task_type:
        return None

    reported_errors = _coerce_validation_errors(
        payload.get("validation_errors", []),
        original_message=original_message,
    )
    if reported_errors is None:
        return None
    if reported_errors:
        return CoderPreview(
            status="needs_clarification",
            source=HEURISTIC_CODER_SOURCE,
            task_type=formulator_preview.task_type,
            artifact=None,
            validation_errors=reported_errors,
            supported_task_types=list(SUPPORTED_TASK_TYPES),
        )

    artifact_payload = payload.get("artifact")
    if not isinstance(artifact_payload, dict):
        return None
    if _payload_contains_unsafe_text(artifact_payload, original_message=original_message):
        return None

    try:
        artifact = CoderCodeArtifact.model_validate(artifact_payload)
    except ValidationError:
        return _clarification_preview(
            formulator_preview.task_type,
            field_path="artifact",
            message="code artifact schema is invalid",
            remediation_hint_key="chat.coder.artifact_invalid",
        )

    validation_errors = validate_code_artifact(artifact, original_message=original_message)
    if validation_errors:
        return CoderPreview(
            status="needs_clarification",
            source=HEURISTIC_CODER_SOURCE,
            task_type=formulator_preview.task_type,
            artifact=None,
            validation_errors=validation_errors[:10],
            supported_task_types=list(SUPPORTED_TASK_TYPES),
        )

    return CoderPreview(
        status="generated",
        source=LLM_CODER_SOURCE,
        task_type=formulator_preview.task_type,
        artifact=artifact,
        validation_errors=[],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def generate_code_with_llm(
    *,
    message: str,
    locale: ChatLocale,
    prompt_id: str,
    formulator_preview: FormulatorPreview,
    completion_func: CompletionFunc = complete,
    model_alias: str = "deepseek-v3.5",
) -> CoderRouteResult:
    if formulator_preview.task_type == "unknown" or formulator_preview.status == "skipped":
        return CoderRouteResult(
            preview=_skipped_preview(formulator_preview.task_type),
            coder_invoked=False,
        )
    if formulator_preview.status != "extracted":
        return CoderRouteResult(
            preview=_non_extracted_preview(formulator_preview),
            coder_invoked=False,
        )
    if not _formulator_has_codegen_content(formulator_preview):
        return CoderRouteResult(
            preview=_clarification_preview(
                formulator_preview.task_type,
                field_path="formulator_preview.variables",
                message="structured formulation is required before code generation",
                remediation_hint_key="chat.coder.formulator_extracted_required",
            ),
            coder_invoked=False,
        )
    if model_alias not in CANONICAL_MODEL_ALIASES:
        return CoderRouteResult(
            preview=_clarification_preview(
                formulator_preview.task_type,
                field_path="coder.model",
                message="supported model alias is required",
                remediation_hint_key="chat.coder.model_required",
            ),
            coder_invoked=False,
        )

    try:
        prompt = build_coder_prompt(
            message=message,
            locale=locale,
            prompt_id=prompt_id,
            formulator_preview=formulator_preview,
        )
    except ValidationError:
        return CoderRouteResult(
            preview=_clarification_preview(
                formulator_preview.task_type,
                field_path="coder.prompt",
                message="safe coder prompt is required",
                remediation_hint_key="chat.coder.prompt_invalid",
            ),
            coder_invoked=False,
        )

    try:
        completion = completion_func(prompt, model_alias)
    except LLMRouterError:
        return CoderRouteResult(
            preview=_clarification_preview(
                formulator_preview.task_type,
                field_path="coder.completion",
                message="code generation completion is unavailable",
                remediation_hint_key="chat.coder.completion_unavailable",
            ),
            coder_invoked=True,
        )

    if completion.finish_reason != "stop":
        return CoderRouteResult(
            preview=_clarification_preview(
                formulator_preview.task_type,
                field_path="coder.completion",
                message="code generation completion did not finish safely",
                remediation_hint_key="chat.coder.completion_unavailable",
            ),
            coder_invoked=True,
        )

    preview = parse_coder_completion(
        completion.text,
        formulator_preview=formulator_preview,
        original_message=message,
    )
    if preview is None:
        preview = _clarification_preview(
            formulator_preview.task_type,
            field_path="coder.completion",
            message="code generation completion is invalid",
            remediation_hint_key="chat.coder.completion_invalid",
        )

    return CoderRouteResult(preview=preview, coder_invoked=True)


def validate_code_artifact(
    artifact: CoderCodeArtifact,
    *,
    original_message: str | None = None,
) -> list[CoderValidationError]:
    errors: list[CoderValidationError] = []
    if _MARKDOWN_FENCE_PATTERN.search(artifact.code):
        errors.append(_validation_error("artifact.code", "python source must not use markdown"))
    if _payload_contains_unsafe_text(artifact.model_dump(), original_message=original_message):
        errors.append(_validation_error("artifact.code", "python source must be redacted"))

    try:
        tree = ast.parse(artifact.code)
    except SyntaxError:
        return [_validation_error("artifact.code", "python source must parse successfully")]

    declared_imports = set(artifact.imports)
    ast_imports = _collect_imports(tree)
    if declared_imports != ast_imports or not ast_imports <= _ALLOWED_IMPORTS:
        errors.append(_validation_error("artifact.imports", "only approved imports are allowed"))

    class_defs = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    function_defs = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }

    input_model = class_defs.get(artifact.input_model)
    output_model = class_defs.get(artifact.output_model)
    entrypoint = function_defs.get(artifact.entrypoint)

    if input_model is None or not _inherits_basemodel(input_model):
        errors.append(
            _validation_error("artifact.input_model", "input model must inherit BaseModel")
        )
    if output_model is None or not _inherits_basemodel(output_model):
        errors.append(
            _validation_error("artifact.output_model", "output model must inherit BaseModel")
        )
    if entrypoint is None or isinstance(entrypoint, ast.AsyncFunctionDef):
        errors.append(
            _validation_error("artifact.entrypoint", "entrypoint must be a sync function")
        )
    else:
        if (
            not entrypoint.args.args
            or entrypoint.args.args[0].annotation is None
            or entrypoint.returns is None
        ):
            errors.append(
                _validation_error("artifact.entrypoint", "entrypoint annotations are required")
            )
        if any(isinstance(child, ast.Yield | ast.YieldFrom) for child in ast.walk(entrypoint)):
            errors.append(
                _validation_error("artifact.entrypoint", "entrypoint must not be a generator")
            )

    if _has_dangerous_call_or_attribute(tree):
        errors.append(_validation_error("artifact.code", "dynamic execution is not allowed"))

    return errors[:10]


def _parse_json_payload(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _looks_like_deterministic_text(text: str) -> bool:
    return _DETERMINISTIC_MARKER in text.lower()


def _payload_contains_unsafe_text(value: object, *, original_message: str | None) -> bool:
    original = original_message.strip() if original_message else None
    if isinstance(value, str):
        if _SECRET_PATTERN.search(value):
            return True
        return bool(original and original in value)
    if isinstance(value, dict):
        for key, child in value.items():
            if _payload_contains_unsafe_text(str(key), original_message=original):
                return True
            if _payload_contains_unsafe_text(child, original_message=original):
                return True
    if isinstance(value, list):
        return any(
            _payload_contains_unsafe_text(child, original_message=original) for child in value
        )
    return False


def _coerce_validation_errors(
    value: object,
    *,
    original_message: str | None,
) -> list[CoderValidationError] | None:
    if not isinstance(value, list) or len(value) > 10:
        return None
    errors: list[CoderValidationError] = []
    for item in value:
        if not isinstance(item, dict):
            return None
        if set(item) - {"field_path", "message", "remediation_hint_key"}:
            return None
        field_path = item.get("field_path")
        message = item.get("message")
        remediation_hint_key = item.get("remediation_hint_key")
        if not isinstance(field_path, str) or not isinstance(message, str):
            return None
        if remediation_hint_key is not None and not isinstance(remediation_hint_key, str):
            return None
        if _payload_contains_unsafe_text(
            [field_path, message, remediation_hint_key],
            original_message=original_message,
        ):
            return None
        try:
            errors.append(
                CoderValidationError(
                    field_path=field_path,
                    message=message,
                    remediation_hint_key=remediation_hint_key,
                )
            )
        except ValidationError:
            return None
    return errors


def _collect_imports(tree: ast.AST) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _inherits_basemodel(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "BaseModel":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
            return True
    return False


def _has_dangerous_call_or_attribute(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DANGEROUS_CALLS:
                return True
            if isinstance(func, ast.Attribute):
                if func.attr in _DANGEROUS_CALLS:
                    return True
                if _root_name(func) in _BLOCKED_RUNTIME_SYMBOLS:
                    return True
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return True
    return False


def _root_name(node: ast.AST) -> str | None:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    return current.id if isinstance(current, ast.Name) else None


def _template_preview(
    formulator_preview: FormulatorPreview,
    *,
    original_message: str | None,
) -> CoderPreview:
    artifact = _template_artifact(formulator_preview)
    errors = validate_code_artifact(artifact, original_message=original_message)
    if errors:
        return CoderPreview(
            status="needs_clarification",
            source=HEURISTIC_CODER_SOURCE,
            task_type=formulator_preview.task_type,
            artifact=None,
            validation_errors=errors,
            supported_task_types=list(SUPPORTED_TASK_TYPES),
        )
    return CoderPreview(
        status="generated",
        source=TEMPLATE_CODER_SOURCE,
        task_type=formulator_preview.task_type,
        artifact=artifact,
        validation_errors=[],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def _template_artifact(formulator_preview: FormulatorPreview) -> CoderCodeArtifact:
    task_type_literal = json.dumps(formulator_preview.task_type)
    code = f"""
from pydantic import BaseModel


class TaskInput(BaseModel):
    variables: dict[str, object]
    objective: dict[str, object]
    constraints: dict[str, object]


class TaskPayload(BaseModel):
    task_type: str
    variables: dict[str, object]
    objective: dict[str, object]
    constraints: dict[str, object]


def build_payload(data: TaskInput) -> TaskPayload:
    return TaskPayload(
        task_type={task_type_literal},
        variables=data.variables,
        objective=data.objective,
        constraints=data.constraints,
    )
""".strip()
    return CoderCodeArtifact(
        language="python",
        code=code,
        entrypoint="build_payload",
        input_model="TaskInput",
        output_model="TaskPayload",
        imports=["pydantic"],
    )


def _formulator_has_codegen_content(formulator_preview: FormulatorPreview) -> bool:
    return bool(formulator_preview.variables) and (
        bool(formulator_preview.objective) or bool(formulator_preview.constraints)
    )


def _non_extracted_preview(formulator_preview: FormulatorPreview) -> CoderPreview:
    if formulator_preview.task_type == "unknown" or formulator_preview.status == "skipped":
        return _skipped_preview(formulator_preview.task_type)
    return _clarification_preview(
        formulator_preview.task_type,
        field_path="formulator_preview.variables",
        message="structured formulation is required before code generation",
        remediation_hint_key="chat.coder.formulator_extracted_required",
    )


def _skipped_preview(task_type: TaskType) -> CoderPreview:
    return CoderPreview(
        status="skipped",
        source=HEURISTIC_CODER_SOURCE,
        task_type=task_type,
        artifact=None,
        validation_errors=[
            CoderValidationError(
                field_path="formulator_preview.task_type",
                message="formulator task_type is unknown",
                remediation_hint_key="chat.coder.task_type_required",
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def _clarification_preview(
    task_type: TaskType,
    *,
    field_path: str,
    message: str,
    remediation_hint_key: str,
) -> CoderPreview:
    return CoderPreview(
        status="needs_clarification",
        source=HEURISTIC_CODER_SOURCE,
        task_type=task_type,
        artifact=None,
        validation_errors=[
            CoderValidationError(
                field_path=field_path,
                message=message,
                remediation_hint_key=remediation_hint_key,
            )
        ],
        supported_task_types=list(SUPPORTED_TASK_TYPES),
    )


def _validation_error(field_path: str, message: str) -> CoderValidationError:
    return CoderValidationError(field_path=field_path, message=message)
