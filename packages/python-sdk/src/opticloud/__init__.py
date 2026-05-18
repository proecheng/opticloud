"""OptiCloud Python SDK — alpha (Story 0.4).

Key features:
- error.locate(field_path) helper (FG1.3 + L1 + A-S3 三语言 consistent API)
- Async + sync clients via httpx
- RFC 7807 + errors[] full preservation (FG1.3 SDK contract)
"""

from opticloud.errors import OptiCloudError, OptiCloudHTTPError

__version__ = "0.0.1a1"
__all__ = ["OptiCloudError", "OptiCloudHTTPError"]
