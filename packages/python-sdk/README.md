# opticloud (Python SDK alpha)

OptiCloud Python SDK — **Story 0.4 alpha**.

## Install

```bash
# Future: pip install opticloud
# Current: uv pip install -e packages/python-sdk
```

## Quickstart

```python
from opticloud import OptiCloudHTTPError
from opticloud.client import OptiCloudClient

client = OptiCloudClient(api_key="sk-xxx")

# List algorithms (FR C1, no auth required actually but client sends key anyway)
algos = client.list_algorithms()
print(algos)
```

## Error handling — FG1.3 + L1 `error.locate()` helper

```python
try:
    client.optimize({"task_type": "lp", "st": {"A": [[1,1],[2,-1]], "b": [10, -1]}})
except OptiCloudHTTPError as e:
    print(f"[{e.status}] {e.title}: {e.detail}")

    # Locate violating value by field_path
    bad_value = e.locate("st.b[1]")
    # bad_value == -1, since "infeasible: b must be >= 0"

    # Or get all matching values
    all_bad = e.locate_all("st.b[1]")

    # Or find by constraint pattern
    infeasibility = e.find_constraint(r"infeasible")

    # Get i18n remediation keys
    keys = e.remediation_keys()
    # ["errors.422.infeasible"]

    # Full original response preserved (FG1.3 SDK contract)
    print(e.raw)
```

## SDK consistency (A-S3 / Story 8.B.6)

- Python: `e.locate("st.A[2][1]")` ✅
- Node SDK: `error.locate("st.A[2][1]")` ✅ via `@opticloud/sdk`
- Go SDK: `err.Locate("st.A[2][1]")` (future M5)

Python and Node preserve the original RFC 7807 `errors[]` structure through
`error.errors` and expose locate helpers with matching semantics. Go remains a
future SDK expansion.
