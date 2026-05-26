"""Validate M3.3a production Kubernetes namespace and NetworkPolicy manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

DOMAIN_LABEL = "opticloud.io/network-domain"
REQUIRED_NAMESPACES = {
    "prod-core": "core",
    "prod-ai": "ai",
    "prod-data": "data",
}
REQUIRED_NAMESPACE_SET = set(REQUIRED_NAMESPACES)
POD_SECURITY_LABELS = {
    "pod-security.kubernetes.io/enforce": "restricted",
    "pod-security.kubernetes.io/audit": "restricted",
    "pod-security.kubernetes.io/warn": "restricted",
}
ALLOWED_APP_FLOWS = {
    ("prod-core", "prod-ai"),
    ("prod-core", "prod-data"),
    ("prod-ai", "prod-data"),
}
FORBIDDEN_APP_FLOWS = {
    ("prod-data", "prod-core"),
    ("prod-data", "prod-ai"),
    ("prod-ai", "prod-core"),
}
ALLOWED_RESOURCE_KINDS = {"Namespace", "NetworkPolicy"}


def load_resources(manifest_dir: Path) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for path in sorted(manifest_dir.glob("*.yaml")):
        for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
            if document is None:
                continue
            if not isinstance(document, dict):
                raise ValueError(f"{path}: each YAML document must be an object")
            document["_source_path"] = str(path)
            resources.append(document)
    return resources


def _metadata(resource: dict[str, Any]) -> dict[str, Any]:
    metadata = resource.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _spec(resource: dict[str, Any]) -> dict[str, Any]:
    spec = resource.get("spec")
    return spec if isinstance(spec, dict) else {}


def _labels(resource: dict[str, Any]) -> dict[str, str]:
    labels = _metadata(resource).get("labels")
    return labels if isinstance(labels, dict) else {}


def _namespace(resource: dict[str, Any]) -> str:
    namespace = _metadata(resource).get("namespace")
    return namespace if isinstance(namespace, str) else ""


def _name(resource: dict[str, Any]) -> str:
    name = _metadata(resource).get("name")
    return name if isinstance(name, str) else ""


def _is_default_deny(policy: dict[str, Any]) -> bool:
    spec = _spec(policy)
    return (
        _name(policy) == "default-deny"
        and spec.get("podSelector") == {}
        and set(spec.get("policyTypes", [])) == {"Ingress", "Egress"}
        and "ingress" not in spec
        and "egress" not in spec
    )


def _namespace_label_selector(peer: object) -> str | None:
    if not isinstance(peer, dict):
        return None
    selector = peer.get("namespaceSelector")
    if not isinstance(selector, dict):
        return None
    match_labels = selector.get("matchLabels")
    if not isinstance(match_labels, dict):
        return None
    domain = match_labels.get(DOMAIN_LABEL)
    return domain if isinstance(domain, str) else None


def _has_empty_namespace_selector(policy: dict[str, Any]) -> bool:
    for direction in ("ingress", "egress"):
        rules = _spec(policy).get(direction, [])
        if not isinstance(rules, list):
            continue
        peer_key = "from" if direction == "ingress" else "to"
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            peers = rule.get(peer_key, [])
            if not isinstance(peers, list):
                continue
            for peer in peers:
                if isinstance(peer, dict) and peer.get("namespaceSelector") == {}:
                    return True
    return False


def _policy_allows_egress_to_domain(policy: dict[str, Any], domain: str) -> bool:
    rules = _spec(policy).get("egress", [])
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        peers = rule.get("to", [])
        if not isinstance(peers, list):
            continue
        if any(_namespace_label_selector(peer) == domain for peer in peers):
            return True
    return False


def _policy_allows_ingress_from_domain(policy: dict[str, Any], domain: str) -> bool:
    rules = _spec(policy).get("ingress", [])
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        peers = rule.get("from", [])
        if not isinstance(peers, list):
            continue
        if any(_namespace_label_selector(peer) == domain for peer in peers):
            return True
    return False


def _policy_allows_same_namespace(policy: dict[str, Any]) -> bool:
    spec = _spec(policy)
    if spec.get("podSelector") != {}:
        return False
    ingress = spec.get("ingress", [])
    egress = spec.get("egress", [])
    return _has_peer_with_only_pod_selector(ingress, "from") and _has_peer_with_only_pod_selector(
        egress, "to"
    )


def _has_peer_with_only_pod_selector(rules: object, peer_key: str) -> bool:
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        peers = rule.get(peer_key, [])
        if not isinstance(peers, list):
            continue
        for peer in peers:
            if isinstance(peer, dict) and peer == {"podSelector": {}}:
                return True
    return False


def _policy_allows_dns(policy: dict[str, Any]) -> bool:
    rules = _spec(policy).get("egress", [])
    if not isinstance(rules, list):
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        ports = rule.get("ports", [])
        peers = rule.get("to", [])
        if not isinstance(ports, list) or not isinstance(peers, list):
            continue
        has_dns_ports = {("UDP", 53), ("TCP", 53)}.issubset(
            {
                (port.get("protocol"), port.get("port"))
                for port in ports
                if isinstance(port, dict)
            }
        )
        has_kube_dns_peer = any(
            isinstance(peer, dict)
            and peer.get("namespaceSelector", {}).get("matchLabels", {}).get(
                "kubernetes.io/metadata.name"
            )
            == "kube-system"
            and peer.get("podSelector", {}).get("matchLabels", {}).get("k8s-app")
            == "kube-dns"
            for peer in peers
        )
        if has_dns_ports and has_kube_dns_peer:
            return True
    return False


def _resources_by_kind(resources: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [resource for resource in resources if resource.get("kind") == kind]


def validate_resources(resources: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    namespaces = {_name(resource): resource for resource in _resources_by_kind(resources, "Namespace")}
    policies = _resources_by_kind(resources, "NetworkPolicy")
    policies_by_namespace = {
        namespace: [policy for policy in policies if _namespace(policy) == namespace]
        for namespace in REQUIRED_NAMESPACES
    }

    for resource in resources:
        kind = resource.get("kind")
        if kind not in ALLOWED_RESOURCE_KINDS:
            errors.append(f"unsupported Kubernetes resource kind: {kind}")

    if set(namespaces) != REQUIRED_NAMESPACE_SET:
        actual = ", ".join(sorted(namespaces)) or "<none>"
        expected = ", ".join(sorted(REQUIRED_NAMESPACE_SET))
        errors.append(f"manifest namespaces must be exactly {expected}; got {actual}")

    for namespace, domain in REQUIRED_NAMESPACES.items():
        resource = namespaces.get(namespace)
        if resource is None:
            errors.append(f"missing Namespace {namespace}")
            continue
        labels = _labels(resource)
        if labels.get(DOMAIN_LABEL) != domain:
            errors.append(f"Namespace {namespace} must label {DOMAIN_LABEL}={domain}")
        for key, expected in POD_SECURITY_LABELS.items():
            if labels.get(key) != expected:
                errors.append(f"Namespace {namespace} must label {key}={expected}")

    production_namespaces = {
        name
        for name, resource in namespaces.items()
        if _labels(resource).get("opticloud.io/environment") == "production"
    }
    if production_namespaces != REQUIRED_NAMESPACE_SET:
        actual = ", ".join(sorted(production_namespaces)) or "<none>"
        expected = ", ".join(sorted(REQUIRED_NAMESPACE_SET))
        errors.append(f"production namespaces must be exactly {expected}; got {actual}")

    for policy in policies:
        if _namespace(policy) not in REQUIRED_NAMESPACE_SET:
            errors.append(f"NetworkPolicy {_name(policy)} has unsupported namespace {_namespace(policy)}")

    for namespace, namespace_policies in policies_by_namespace.items():
        if not any(_is_default_deny(policy) for policy in namespace_policies):
            errors.append(f"{namespace} missing default-deny ingress+egress NetworkPolicy")
        if not any(_policy_allows_same_namespace(policy) for policy in namespace_policies):
            errors.append(f"{namespace} missing same-namespace allow policy")
        if not any(_policy_allows_dns(policy) for policy in namespace_policies):
            errors.append(f"{namespace} missing kube-dns egress allow policy")

    for policy in policies:
        if _has_empty_namespace_selector(policy):
            errors.append(f"{_namespace(policy)}/{_name(policy)} must not use namespaceSelector: {{}}")

    domain_to_namespace = {domain: namespace for namespace, domain in REQUIRED_NAMESPACES.items()}
    for source, target in ALLOWED_APP_FLOWS:
        target_domain = REQUIRED_NAMESPACES[target]
        source_domain = REQUIRED_NAMESPACES[source]
        source_policies = policies_by_namespace[source]
        target_policies = policies_by_namespace[target]
        if not any(_policy_allows_egress_to_domain(policy, target_domain) for policy in source_policies):
            errors.append(f"missing allowed egress {source} -> {target}")
        if not any(_policy_allows_ingress_from_domain(policy, source_domain) for policy in target_policies):
            errors.append(f"missing allowed ingress {source} -> {target}")

    for source, target in FORBIDDEN_APP_FLOWS:
        target_domain = REQUIRED_NAMESPACES[target]
        source_domain = REQUIRED_NAMESPACES[source]
        source_policies = policies_by_namespace[source]
        target_policies = policies_by_namespace[target]
        if any(_policy_allows_egress_to_domain(policy, target_domain) for policy in source_policies):
            errors.append(f"forbidden egress present {source} -> {target}")
        if any(_policy_allows_ingress_from_domain(policy, source_domain) for policy in target_policies):
            errors.append(f"forbidden ingress present {source} -> {target}")

    for policy in policies:
        for direction in ("ingress", "egress"):
            rules = _spec(policy).get(direction, [])
            if not isinstance(rules, list):
                continue
            peer_key = "from" if direction == "ingress" else "to"
            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                peers = rule.get(peer_key, [])
                if not isinstance(peers, list):
                    continue
                for peer in peers:
                    selected_domain = _namespace_label_selector(peer)
                    if selected_domain is not None and selected_domain not in domain_to_namespace:
                        errors.append(
                            f"{_namespace(policy)}/{_name(policy)} selects unknown domain {selected_domain}"
                        )

    return errors


def validate_manifest_dir(manifest_dir: Path) -> list[str]:
    return validate_resources(load_resources(manifest_dir))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate OptiCloud production K8s policies")
    parser.add_argument("manifest_dir", type=Path, help="Path to infra/k8s/production")
    args = parser.parse_args()

    try:
        errors = validate_manifest_dir(args.manifest_dir)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        sys.stderr.write(f"ERROR: unable to load manifests: {exc}\n")
        return 1

    if errors:
        for error in errors:
            sys.stderr.write(f"ERROR: {error}\n")
        return 1

    sys.stdout.write(f"k8s network policies OK: {args.manifest_dir}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
