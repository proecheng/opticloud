# LLM Provider Abstraction Runbook

Story M3.8 defines the shared, provider-agnostic LLM router contract used by future Chat and NL agents.

## Contract

- Logical aliases are `deepseek-v3.5`, `qwen-max`, and `mock-deterministic`.
- Provider IDs are `deepseek-compatible`, `qwen-compatible`, and `mock`.
- Provider model names are configuration values. Do not treat a logical alias as a permanent upstream model ID.
- The public API is `llm_router.complete(prompt: Prompt, model: str) -> Completion`.
- `Prompt` and `Completion` are the only schema boundary Future services should consume.

## Offline Mode

CI and local validation use deterministic offline transports. They do not read API keys, call provider APIs, open network connections, use Docker, or require `apps/chat-service`.

Run:

```bash
uv run python scripts/validate_llm_router_contract.py
uv run pytest tests/llm_router/test_implementations_parity.py -q
```

## Future Live Provider Injection

The DeepSeek and Qwen adapters accept future base URL and API-key provider callables. Live provider wiring must be introduced by a later runtime story with redaction review and explicit environment handling.

M3.8 must not commit API keys, live request/response captures, provider logs, customer prompts, environment files, or generated `reports/**` evidence.

## Incident Fallback Boundary

Fallback is explicit incident behavior. Normal `deepseek-v3.5` calls stay on the DeepSeek-compatible adapter unless the router is configured with that alias unavailable.

When incident mode is configured, `deepseek-v3.5` routes to `qwen-max` and returns the same `Completion` schema with a redacted fallback reason. This does not change customer-facing v1 SLO language and does not implement normal multi-LLM routing.

## Parity Report

`tools/llm_router/parity_report.example.json` is deterministic offline parity evidence for 100 committed prompts. It proves schema and offline behavior parity only. It does not prove real DeepSeek/Qwen semantic equivalence.

Future real provider parity evidence requires a separate operator evidence PR with redaction review.

## Failure Response

Block the PR until fixed when validation finds:

- schema drift
- alias or provider drift
- fewer or more than 100 reference prompts
- behavior parity below `0.85`
- global canned-output shortcuts
- unsafe metadata or secret-like content
- accidental live-provider dependency
- fake live-provider evidence claims
