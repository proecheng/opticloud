"""OptiCloud Auth Service — Story 0.6.

Endpoints (FR A1-A10):
- POST /v1/auth/signup     (FR A1 注册 + 手机+邮箱双因素)
- POST /v1/auth/login      (FR A1 后续)
- POST /v1/auth/api_keys   (FR A2 创建 API Key)
- GET  /v1/auth/api_keys   (FR A2 列表)
- DELETE /v1/auth/api_keys/{id}  (FR A2 吊销)
- GET  /healthz / /readyz  (Story 0.7)
"""

__version__ = "0.0.1"
