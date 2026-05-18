"""OptiCloud Solver Orchestrator.

Endpoints:
- GET  /v1/algorithms                  (FR C1, no auth) — Story 2.1
- GET  /v1/algorithms/{k_algo}         (FR C2)
- POST /v1/optimizations               (FR E1, E3, E7, E9) — Story 3.1
- GET  /v1/optimizations/{id}          (FR E9)
- GET  /healthz / /readyz / /metrics   (Story 0.7)
"""

__version__ = "0.0.1"
