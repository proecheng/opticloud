"""SBOM daily diff scanner — RE2-9 fix.

Compares two SPDX-JSON SBOMs (today vs yesterday) and produces:
- Added packages
- Removed packages
- Version bumps (split by major / minor / patch)
- CVE alerts (if --cve-db provided)

Usage:
    uv run python scripts/sbom_diff.py \
        --old infra/sbom-history/2026-05-16/auth-service.spdx.json \
        --new infra/sbom-history/2026-05-17/auth-service.spdx.json \
        [--cve-db ./cve-db.json] \
        [--linear-ticket]

Exit codes:
    0: no breaking changes
    1: major version bump without ADR / high CVE detected → block PR
    2: minor changes → Linear ticket created (informational)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    license: str = "UNKNOWN"

    def __hash__(self) -> int:
        return hash((self.name, self.version))


def load_sbom(path: Path) -> dict[str, Package]:
    """Load SPDX JSON SBOM into {name: Package}."""
    data = json.loads(path.read_text())
    pkgs: dict[str, Package] = {}
    for p in data.get("packages", []):
        name = p.get("name", "")
        version = p.get("versionInfo", p.get("version", "unknown"))
        license_str = p.get("licenseConcluded", p.get("licenseDeclared", "UNKNOWN"))
        if name:
            pkgs[name] = Package(name=name, version=version, license=license_str)
    return pkgs


def _semver_parts(ver: str) -> tuple[int, int, int]:
    """Parse semver to (major, minor, patch); ignore pre-release suffixes."""
    base = ver.split("+")[0].split("-")[0]
    parts = base.split(".")
    try:
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return 0, 0, 0
    return major, minor, patch


def classify_bump(old_ver: str, new_ver: str) -> str:
    """Classify version change as major / minor / patch / equal / downgrade / unparseable."""
    old_t = _semver_parts(old_ver)
    new_t = _semver_parts(new_ver)
    if old_t == new_t:
        return "equal"
    if new_t < old_t:
        return "downgrade"
    if new_t[0] > old_t[0]:
        return "major"
    if new_t[1] > old_t[1]:
        return "minor"
    if new_t[2] > old_t[2]:
        return "patch"
    return "unknown"


def diff_sboms(old: dict[str, Package], new: dict[str, Package]) -> dict[str, list[dict[str, str]]]:
    """Return categorized diff."""
    old_names = set(old.keys())
    new_names = set(new.keys())

    added = sorted(new_names - old_names)
    removed = sorted(old_names - new_names)
    common = old_names & new_names

    bumps: dict[str, list[dict[str, str]]] = {
        "major": [],
        "minor": [],
        "patch": [],
        "downgrade": [],
    }
    for name in sorted(common):
        if old[name].version != new[name].version:
            bump_kind = classify_bump(old[name].version, new[name].version)
            if bump_kind in bumps:
                bumps[bump_kind].append(
                    {"name": name, "old": old[name].version, "new": new[name].version}
                )

    return {
        "added": [{"name": n, "version": new[n].version} for n in added],
        "removed": [{"name": n, "version": old[n].version} for n in removed],
        **bumps,
    }


def check_cves(packages: dict[str, Package], cve_db_path: Path | None) -> list[dict[str, str]]:
    """Cross-reference packages against CVE DB (CRG6 supply chain alert)."""
    if cve_db_path is None or not cve_db_path.exists():
        return []
    cve_db = json.loads(cve_db_path.read_text())
    # Simple lookup; real implementation uses OSV.dev / Snyk API
    alerts = []
    for name, pkg in packages.items():
        for cve in cve_db.get("vulnerabilities", []):
            if cve.get("package") == name and cve.get("version_pattern", "").startswith(pkg.version):
                alerts.append(
                    {
                        "package": name,
                        "version": pkg.version,
                        "cve_id": cve.get("id", "unknown"),
                        "severity": cve.get("severity", "unknown"),
                    }
                )
    return alerts


def main() -> int:
    parser = argparse.ArgumentParser(description="OptiCloud SBOM daily diff")
    parser.add_argument("--old", type=Path, required=True, help="Yesterday's SBOM")
    parser.add_argument("--new", type=Path, required=True, help="Today's SBOM")
    parser.add_argument("--cve-db", type=Path, default=None)
    parser.add_argument("--linear-ticket", action="store_true", help="Create Linear ticket on changes")
    args = parser.parse_args()

    old_pkgs = load_sbom(args.old)
    new_pkgs = load_sbom(args.new)
    diff = diff_sboms(old_pkgs, new_pkgs)

    cve_alerts = check_cves(new_pkgs, args.cve_db)

    # Print human-readable report
    print(f"SBOM diff: {args.old.name} → {args.new.name}")
    print(f"  Added:      {len(diff['added'])}")
    print(f"  Removed:    {len(diff['removed'])}")
    print(f"  Major bumps: {len(diff['major'])}")
    print(f"  Minor bumps: {len(diff['minor'])}")
    print(f"  Patch bumps: {len(diff['patch'])}")
    print(f"  Downgrades:  {len(diff['downgrade'])}")
    print(f"  CVE alerts:  {len(cve_alerts)}")

    if diff["major"]:
        print("\n🔴 Major version bumps (require ADR before merge):")
        for b in diff["major"]:
            print(f"    {b['name']}: {b['old']} → {b['new']}")

    if cve_alerts:
        print("\n🔴 CVE alerts (CRG6 supply chain):")
        for a in cve_alerts:
            print(f"    {a['package']}@{a['version']}: {a['cve_id']} ({a['severity']})")

    # Output structured JSON for CI consumption
    output_path = args.new.parent / f"{args.new.stem}.diff.json"
    output_path.write_text(json.dumps({"diff": diff, "cve_alerts": cve_alerts}, indent=2))
    print(f"\n  ℹ️  Structured diff written to {output_path}")

    # Exit codes for CI gating
    if diff["major"] or any(a["severity"] in ("high", "critical") for a in cve_alerts):
        print("\n❌ Blocking: major bump or high/critical CVE detected.")
        return 1
    if diff["added"] or diff["removed"] or diff["minor"] or diff["downgrade"] or cve_alerts:
        print("\n🟡 Changes detected — Linear ticket recommended.")
        if args.linear_ticket:
            # Placeholder; real implementation calls Linear API
            print("    (Linear ticket creation pending — implement in Sprint 0 W2)")
        return 2
    print("\n✅ No changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
