-- Story 1.11 — geo anomaly risk score signal for API Key usage (NFR-S4).
-- Idempotent: safe to re-run.
--
-- This rule is intentionally disabled in v1. It records score/evidence in
-- risk_flags and users.risk_score, but must not count toward Story 1.5's
-- distinct-enabled-rules auto-freeze threshold.

INSERT INTO risk_rules (code, label_zh, description, enabled) VALUES
    (
        'geo_anomaly',
        'API Key 异常地理跨越',
        'NFR-S4 — API Key continuous-use geography changed between known distant regions; evidence-only score signal in v1',
        false
    )
ON CONFLICT (code) DO UPDATE
SET label_zh = EXCLUDED.label_zh,
    description = EXCLUDED.description,
    enabled = false;
