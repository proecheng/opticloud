# @opticloud/sdk

Minimal OptiCloud Node SDK error contract package.

This package preserves RFC 7807 `errors[]` detail objects exactly for client-side inspection. It does not yet implement a full HTTP API client or generated OpenAPI operations.

```ts
import { parseOptiCloudErrorResponse } from "@opticloud/sdk";

const error = parseOptiCloudErrorResponse(422, problemBody);

console.log(error.errors);
console.log(error.locate("st.A[2][1]"));
console.log(error.remediationKeys());
```

Wire-format fields such as `next_action_url` and `remediation_hint_key` stay in snake_case so SDK users can inspect the original API contract without field-name drift.
