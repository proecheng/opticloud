# SBOM History — Story 0.8 + RE2-9 + Architecture G7 联动

Daily Software Bill of Materials (SPDX-JSON) per service.

## Layout

```
sbom-history/
├── 2026-05-17/
│   ├── auth-service.spdx.json     # syft output (SPDX 2.3 JSON)
│   ├── auth-service.cve-report.json  # grype scan against NVD + GHSA
│   └── auth-service.diff.json     # vs prior day, from scripts/sbom_diff.py
├── 2026-05-18/
│   └── ...
```

## Retention

- **Hot (sbom-history/ in repo)**: 90 days (Architecture Concern #14)
- **Warm (S3 Standard-IA)**: 1 year
- **Cold (S3 Glacier)**: 5 years (G7 联动 — Image 5y SLA)

Migration is automated by `.github/workflows/sbom-archive.yml` (M3 Story M3.9).

## Use cases

1. **PR gate** (Story 0.8) — block merge if major version bump or high/critical CVE
2. **Daily scan** (RE2-9) — Linear ticket auto-creation on dependency drift
3. **Supply chain audit** (CRG6 + Sandbox Audit M3.7) — diff vs previous quarter for compliance evidence
4. **Voucher Reproducibility** (R3 + Story 6.B.3) — voucher rerun fetches matching SBOM to verify identical deps

## Manual scan

```bash
# Generate SBOM for current auth-service dev image
scripts/build_and_sign.sh auth-service dev

# Diff today vs yesterday
python scripts/sbom_diff.py \
  --old infra/sbom-history/$(date -u -d 'yesterday' +%Y-%m-%d)/auth-service.spdx.json \
  --new infra/sbom-history/$(date -u +%Y-%m-%d)/auth-service.spdx.json
```
