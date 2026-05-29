# Sandbox Logs Stream v1.5+ Handoff

Status: Deferred
Stage: M7-M8 / v1.5+
Owner: Chat Platform / Sandbox Runner / SDK Integration
Source story: 4.B.6
Current contract: `allow_logs_stream=true` is recognized and rejected fail-closed with `logs_stream_deferred`.

## Linear-Ready Ticket

Title: Implement sandbox stdout/stderr SSE logs streaming for v1.5+

Problem:
SDK integrators need bounded, real-time stdout/stderr visibility for long-running sandbox jobs. The current internal beta only supports synchronous sandbox execution and intentionally rejects `allow_logs_stream=true` before executor invocation.

Scope:
- Implement sandbox-runner stdout/stderr SSE lifecycle for `allow_logs_stream=true`.
- Proxy the stream through chat-service and the api-gateway streaming path.
- Add SDK and web consumer support only after the backend stream contract is audited.
- Preserve the synchronous `/v1/sandbox/execute` behavior for `allow_logs_stream=false`.

Out of scope for the current story:
- No current SSE runtime.
- No current SDK streaming method.
- No `/v1/chat/stream`, `/v1/sandbox/stream`, or `/v1/sandbox/logs` public route.
- No Console logs UI.

## Prerequisites

- Architecture P28: SSE lifecycle, heartbeat cadence, reconnect cursor, proxy timeout, and buffering strategy.
- Architecture P58: sandbox-runner stdout/stderr capture and pod logs API integration.
- Architecture P60: operator evidence, incident traceability, and production audit retention.
- Story 4.C.2 or equivalent Chat streaming UX contract.
- Api-gateway streaming proxy with timeout, buffering, and cancellation behavior documented.
- AIGC/filter chunk-boundary rules for streamed content.
- stdout/stderr redaction rules for tokens, tracebacks, host paths, provider payloads, queue payloads, and customer data.

## Acceptance Checklist

- `allow_logs_stream=false` keeps the synchronous execute contract unchanged.
- `allow_logs_stream=true` is available only behind the v1.5+ release gate.
- SSE events are bounded and do not include raw request bodies, generated code, stdin, host paths, provider payloads, queue payloads, secrets, or full tracebacks.
- Heartbeat and reconnect cursor behavior are tested through sandbox-runner, chat-service, and api-gateway.
- Cancellation closes sandbox execution and stream resources without orphaning pods or file handles.
- Redaction is applied before any chunk leaves sandbox-runner.
- Operator evidence records stream start, stream end, cancellation, timeout, policy block, and redaction counters without storing sensitive payloads.
- Contract tests prove `/v1/sandbox/execute` remains stable and streaming routes are not exposed before the v1.5 gate is enabled.
- SDK and web clients are released after backend and gateway contract tests pass.

## Security Boundaries

- Reject or redact secret-like values before streaming.
- Never stream raw generated code, stdin, full stdout/stderr, request bodies, provider payloads, queue payloads, host paths, or tracebacks.
- Keep network-disabled sandbox policy independent from logs streaming.
- Keep AIGC/filter and human-review semantics separate from transport mechanics.
- Do not use example evidence as live proof, customer data, production logs, third-party automation credentials, or real issue identifiers in implementation tests or documentation.

## Current Evidence

The current v1/internal beta story only reserves the feature flag and stable error code. It does not implement SSE, SDK streaming, api-gateway streaming proxying, or a Console logs UI.
