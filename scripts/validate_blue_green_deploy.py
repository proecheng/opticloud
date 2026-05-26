"""Validate M3.3b lean docker-compose blue/green deployment assets.

The checks are intentionally static: no Docker daemon, cloud credentials, proxy
reload, or network access is required.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = REPO_ROOT / "scripts" / "deploy" / "blue-green.sh"
DEFAULT_BLUE_COMPOSE = REPO_ROOT / "docker-compose.blue.yml"
DEFAULT_GREEN_COMPOSE = REPO_ROOT / "docker-compose.green.yml"
REQUIRED_SERVICES = {"web", "api-gateway", "solver-orchestrator"}
REQUIRED_SCRIPT_MARKERS = {
    "COMPOSE_CMD",
    "BLUE_GREEN_STATE_FILE",
    "BLUE_GREEN_BLUE_HEALTH_URL",
    "BLUE_GREEN_GREEN_HEALTH_URL",
    "BLUE_GREEN_SWITCH_CMD",
    "BLUE_GREEN_TIMEOUT_SECONDS",
    "BLUE_GREEN_HEALTH_INTERVAL_SECONDS",
}
FORBIDDEN_SCOPE_PATTERNS = {
    "Kubernetes command": re.compile(r"\b(kubectl|kubernetes)\b", re.IGNORECASE),
    "Helm": re.compile(r"\bhelm\b", re.IGNORECASE),
    "Terraform": re.compile(r"\bterraform\b", re.IGNORECASE),
    "Argo": re.compile(r"\b(argocd|argo\s+rollouts?)\b", re.IGNORECASE),
    "ACK": re.compile(r"\bACK\b"),
    "cloud credential command": re.compile(r"\b(aliyun|aws|gcloud|az)\b", re.IGNORECASE),
}
SECRET_KEY_PATTERNS = re.compile(
    r"(SECRET|PASSWORD|TOKEN|PRIVATE[_-]?KEY|ACCESS[_-]?KEY|CREDENTIAL)",
    re.IGNORECASE,
)


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: compose document must be a YAML object")
    return data


def _service_map(compose: dict[str, Any]) -> dict[str, Any]:
    services = compose.get("services")
    return services if isinstance(services, dict) else {}


def _environment_map(service: dict[str, Any]) -> dict[str, str]:
    environment = service.get("environment", {})
    if isinstance(environment, dict):
        return {str(key): str(value) for key, value in environment.items()}
    if isinstance(environment, list):
        result = {}
        for item in environment:
            if isinstance(item, str) and "=" in item:
                key, value = item.split("=", 1)
                result[key] = value
        return result
    return {}


def _port_mapping(service: dict[str, Any]) -> tuple[str, str] | None:
    ports = service.get("ports")
    if not isinstance(ports, list) or len(ports) != 1:
        return None
    port = ports[0]
    if not isinstance(port, str):
        return None
    if ":" not in port:
        return None
    host, container = port.rsplit(":", 1)
    return host.strip('"'), container


def _host_port_default(host_port: str) -> str:
    match = re.fullmatch(r"\$\{[A-Z0-9_]+:-(\d+)\}", host_port)
    if match:
        return match.group(1)
    return host_port


def _has_healthcheck(service: dict[str, Any]) -> bool:
    healthcheck = service.get("healthcheck")
    if not isinstance(healthcheck, dict):
        return False
    test = healthcheck.get("test")
    return isinstance(test, list) and any("/healthz" in str(item) for item in test)


def _ordered_markers(text: str, markers: list[str]) -> bool:
    position = -1
    for marker in markers:
        next_position = text.find(marker, position + 1)
        if next_position == -1:
            return False
        position = next_position
    return True


def _function_body(script_text: str, name: str) -> str:
    match = re.search(rf"^{name}\(\) \{{\n(?P<body>.*?)(?=^}}\n)", script_text, re.M | re.S)
    return match.group("body") if match else ""


def validate_scope_texts(source_texts: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for source, text in source_texts.items():
        for label, pattern in FORBIDDEN_SCOPE_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{source} contains out-of-scope {label}")
    return errors


def validate_script(script_text: str) -> list[str]:
    errors: list[str] = []

    for marker in REQUIRED_SCRIPT_MARKERS:
        if marker not in script_text:
            errors.append(f"blue-green.sh missing required environment marker {marker}")

    for command in ("deploy", "rollback", "status"):
        if f"{command})" not in script_text:
            errors.append(f"blue-green.sh missing {command} command dispatch")
        if f"{command}()" not in script_text:
            errors.append(f"blue-green.sh missing {command} function")

    if "deploy <image_tag>" not in script_text:
        errors.append("blue-green.sh usage must document deploy <image_tag>")
    if "[[ $# -ne 2 ]]" not in script_text or "[[ $# -ne 1 ]]" not in script_text:
        errors.append("blue-green.sh must validate command argument counts")
    if "OPTICLOUD_ROLLBACK_IMAGE_TAG:-latest" in script_text:
        errors.append("rollback must not silently fall back to latest")
    if "rollback image tag unavailable" not in script_text:
        errors.append("rollback must fail safely when previous image tag is unavailable")

    deploy_body = _function_body(script_text, "deploy")
    deploy_markers = [
        'compose_up "${inactive}" "${image_tag}"',
        'wait_for_health "${inactive}"',
        'switch_traffic "${inactive}"',
        'write_state "${inactive}" "${image_tag}" "${active}" "${active_image_tag}"',
        'compose_stop "${active}"',
    ]
    if not deploy_body or not _ordered_markers(deploy_body, deploy_markers):
        errors.append(
            "deploy flow must start inactive, wait health, switch, write state, then stop active"
        )

    rollback_body = _function_body(script_text, "rollback")
    rollback_markers = [
        'compose_up "${previous}" "${rollback_image_tag}"',
        'wait_for_health "${previous}"',
        'switch_traffic "${previous}"',
        'write_state "${previous}" "${rollback_image_tag}" "${active}" "${active_image_tag}"',
        'compose_stop "${active}"',
    ]
    if not rollback_body or not _ordered_markers(rollback_body, rollback_markers):
        errors.append(
            "rollback flow must start previous, wait health, switch, write state, then stop active"
        )

    return errors


def validate_compose_documents(
    blue_compose: dict[str, Any],
    green_compose: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    if blue_compose.get("name") != "opticloud-blue":
        errors.append("docker-compose.blue.yml must set name: opticloud-blue")
    if green_compose.get("name") != "opticloud-green":
        errors.append("docker-compose.green.yml must set name: opticloud-green")

    blue_services = _service_map(blue_compose)
    green_services = _service_map(green_compose)
    blue_service_names = set(blue_services)
    green_service_names = set(green_services)
    if blue_service_names != REQUIRED_SERVICES:
        errors.append(
            "blue compose services must be exactly " + ", ".join(sorted(REQUIRED_SERVICES))
        )
    if green_service_names != REQUIRED_SERVICES:
        errors.append(
            "green compose services must be exactly " + ", ".join(sorted(REQUIRED_SERVICES))
        )
    if blue_service_names != green_service_names:
        errors.append("blue/green services must match exactly")

    blue_host_ports: dict[str, str] = {}
    green_host_ports: dict[str, str] = {}
    container_names: set[str] = set()
    all_host_ports: dict[str, str] = {}

    for slot, services, host_ports in (
        ("blue", blue_services, blue_host_ports),
        ("green", green_services, green_host_ports),
    ):
        for service_name in sorted(REQUIRED_SERVICES & set(services)):
            service = services[service_name]
            if not isinstance(service, dict):
                errors.append(f"{slot}/{service_name} service must be an object")
                continue

            container_name = service.get("container_name")
            expected_container = f"opticloud-{slot}-{service_name}"
            if container_name != expected_container:
                errors.append(f"{slot}/{service_name} container_name must be {expected_container}")
            if isinstance(container_name, str):
                if container_name in container_names:
                    errors.append(f"duplicate container_name {container_name}")
                container_names.add(container_name)

            environment = _environment_map(service)
            if environment.get("OPTICLOUD_SLOT") != slot:
                errors.append(f"{slot}/{service_name} must set OPTICLOUD_SLOT={slot}")
            for key in environment:
                if SECRET_KEY_PATTERNS.search(key):
                    errors.append(f"{slot}/{service_name} embeds forbidden secret-like env key {key}")

            image = service.get("image")
            if not isinstance(image, str) or "${OPTICLOUD_IMAGE_TAG:-latest}" not in image:
                errors.append(f"{slot}/{service_name} image must use OPTICLOUD_IMAGE_TAG")

            port_mapping = _port_mapping(service)
            if port_mapping is None:
                errors.append(f"{slot}/{service_name} must define exactly one host:container port")
            else:
                host_port, container_port = port_mapping
                default_host_port = _host_port_default(host_port)
                host_ports[service_name] = default_host_port
                port_owner = f"{slot}/{service_name}"
                previous_owner = all_host_ports.get(default_host_port)
                if previous_owner is not None:
                    errors.append(
                        f"host port {default_host_port} reused by {previous_owner} and {port_owner}"
                    )
                all_host_ports[default_host_port] = port_owner
                if not container_port.isdigit():
                    errors.append(f"{slot}/{service_name} container port must be numeric")

            if not _has_healthcheck(service):
                errors.append(f"{slot}/{service_name} must define /healthz healthcheck")

    duplicate_ports = {
        port for port in blue_host_ports.values() if port in set(green_host_ports.values())
    }
    if duplicate_ports:
        errors.append("blue/green host ports must be distinct: " + ", ".join(sorted(duplicate_ports)))

    return errors


def validate_assets(
    script_text: str,
    blue_compose: dict[str, Any],
    green_compose: dict[str, Any],
    source_texts: dict[str, str] | None = None,
) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_scope_texts(source_texts or {}))
    errors.extend(validate_script(script_text))
    errors.extend(validate_compose_documents(blue_compose, green_compose))
    return errors


def validate_paths(script: Path, blue_compose: Path, green_compose: Path) -> list[str]:
    script_text = script.read_text(encoding="utf-8")
    blue_text = blue_compose.read_text(encoding="utf-8")
    green_text = green_compose.read_text(encoding="utf-8")
    return validate_assets(
        script_text,
        load_yaml(blue_compose),
        load_yaml(green_compose),
        {
            str(script): script_text,
            str(blue_compose): blue_text,
            str(green_compose): green_text,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lean blue/green deploy assets")
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--blue-compose", type=Path, default=DEFAULT_BLUE_COMPOSE)
    parser.add_argument("--green-compose", type=Path, default=DEFAULT_GREEN_COMPOSE)
    args = parser.parse_args()

    try:
        errors = validate_paths(args.script, args.blue_compose, args.green_compose)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        sys.stderr.write(f"ERROR: unable to load blue/green deploy assets: {exc}\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"ERROR: {error}\n")
        return 1

    sys.stdout.write("blue/green deploy assets OK\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
