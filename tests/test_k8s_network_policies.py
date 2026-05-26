from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / "infra" / "k8s" / "production"
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_k8s_network_policies.py"


def _load_validator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_k8s_network_policies", VALIDATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_resources() -> list[dict[str, Any]]:
    validator = _load_validator()
    resources = validator.load_resources(MANIFEST_DIR)
    return copy.deepcopy(resources)


def _assert_invalid(resources: list[dict[str, Any]], expected: str) -> None:
    validator = _load_validator()
    errors = validator.validate_resources(resources)
    assert any(expected in error for error in errors), errors


def test_committed_k8s_network_policies_validate_from_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), str(MANIFEST_DIR)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "k8s network policies OK" in result.stdout


def test_missing_required_namespace_is_rejected() -> None:
    resources = [
        resource
        for resource in _load_resources()
        if not (resource.get("kind") == "Namespace" and resource["metadata"]["name"] == "prod-data")
    ]

    _assert_invalid(resources, "missing Namespace prod-data")


def test_extra_production_namespace_is_rejected() -> None:
    resources = _load_resources()
    resources.append(
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "prod-extra",
                "labels": {
                    "opticloud.io/environment": "production",
                    "opticloud.io/network-domain": "extra",
                    "pod-security.kubernetes.io/enforce": "restricted",
                    "pod-security.kubernetes.io/audit": "restricted",
                    "pod-security.kubernetes.io/warn": "restricted",
                },
            },
        }
    )

    _assert_invalid(resources, "production namespaces must be exactly")


def test_extra_nonproduction_namespace_is_rejected() -> None:
    resources = _load_resources()
    resources.append(
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "prod-extra",
                "labels": {
                    "opticloud.io/network-domain": "extra",
                    "pod-security.kubernetes.io/enforce": "restricted",
                    "pod-security.kubernetes.io/audit": "restricted",
                    "pod-security.kubernetes.io/warn": "restricted",
                },
            },
        }
    )

    _assert_invalid(resources, "manifest namespaces must be exactly")


def test_unsupported_kubernetes_resource_is_rejected() -> None:
    resources = _load_resources()
    resources.append(
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "out-of-scope",
                "namespace": "prod-core",
            },
            "spec": {},
        }
    )

    _assert_invalid(resources, "unsupported Kubernetes resource kind: Deployment")


def test_network_policy_outside_required_namespaces_is_rejected() -> None:
    resources = _load_resources()
    resources.append(
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "out-of-scope",
                "namespace": "prod-extra",
            },
            "spec": {
                "podSelector": {},
                "policyTypes": ["Ingress", "Egress"],
            },
        }
    )

    _assert_invalid(resources, "NetworkPolicy out-of-scope has unsupported namespace prod-extra")


def test_missing_default_deny_is_rejected() -> None:
    resources = [
        resource
        for resource in _load_resources()
        if not (
            resource.get("kind") == "NetworkPolicy"
            and resource["metadata"]["namespace"] == "prod-ai"
            and resource["metadata"]["name"] == "default-deny"
        )
    ]

    _assert_invalid(resources, "prod-ai missing default-deny ingress+egress NetworkPolicy")


def test_forbidden_data_to_core_egress_is_rejected() -> None:
    resources = _load_resources()
    resources.append(
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "bad-data-to-core",
                "namespace": "prod-data",
            },
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [
                    {
                        "to": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {
                                        "opticloud.io/network-domain": "core",
                                    },
                                },
                            },
                        ],
                    },
                ],
            },
        }
    )

    _assert_invalid(resources, "forbidden egress present prod-data -> prod-core")


def test_wildcard_namespace_selector_is_rejected() -> None:
    resources = _load_resources()
    resources.append(
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": "bad-wildcard",
                "namespace": "prod-core",
            },
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress"],
                "egress": [{"to": [{"namespaceSelector": {}}]}],
            },
        }
    )

    _assert_invalid(resources, "prod-core/bad-wildcard must not use namespaceSelector: {}")
