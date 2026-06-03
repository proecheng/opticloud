import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

import {
  OptiCloudHTTPError,
  parseOptiCloudErrorResponse,
} from "../dist/src/index.js";

function loadPreservationFixture() {
  const fixturePath = path.resolve(
    process.cwd(),
    "../../tests/fixtures/sdk-rfc7807-preservation.json",
  );
  return JSON.parse(readFileSync(fixturePath, "utf8"));
}

test("parseOptiCloudErrorResponse preserves RFC7807 errors without mutable aliasing", () => {
  const body = loadPreservationFixture();
  const expectedErrors = structuredClone(body.errors);
  const expectedRaw = structuredClone(body);

  const error = parseOptiCloudErrorResponse(422, body);

  assert.equal(error.status, 422);
  assert.equal(error.title, "Invalid Prediction Data");
  assert.deepEqual(error.errors, expectedErrors);
  assert.deepEqual(error.raw, expectedRaw);
  assert.equal(error.next_action_url, expectedRaw.next_action_url);
  assert.equal(error.request_id, expectedRaw.request_id);
  assert.equal(error.trace_id, expectedRaw.trace_id);
  assert.deepEqual(error.locate("series[0].values"), {
    observed: [12.5, null, 13.1],
    metadata: { source: "csv", row: 7 },
  });
  assert.equal(error.locate("options.horizon"), null);
  assert.deepEqual(error.remediationKeys(), [
    "errors.422.invalid_prediction_data",
    "errors.422.invalid_prediction_data",
  ]);

  const errors = body.errors;
  const firstError = errors[0];
  firstError.value.metadata.row = 999;
  errors.push({ field_path: "mutated", value: "late" });
  body.request_id = "mutated-request";

  assert.deepEqual(error.errors, expectedErrors);
  assert.deepEqual(error.raw, expectedRaw);
  assert.deepEqual(error.locate("series[0].values"), {
    observed: [12.5, null, 13.1],
    metadata: { source: "csv", row: 7 },
  });
});

test("helpers preserve Python parity semantics", () => {
  const error = new OptiCloudHTTPError({
    status: 422,
    title: "Validation Error",
    detail: "multiple violations",
    errors: [
      {
        field_path: "options.tags[0]",
        value: "invalid",
        constraint: "must match allowed tag",
        remediation_hint_key: "errors.422.invalid_prediction_data",
      },
      {
        field_path: "options.tags[0]",
        value: "duplicate",
        constraint: "duplicate tag",
        remediation_hint_key: "errors.422.invalid_prediction_data",
      },
      {
        field_path: "obj",
        value: null,
        constraint: "infeasible_lp",
        remediation_hint_key: "errors.422.invalid_prediction_data",
      },
    ],
  });

  assert.equal(error.locate("options.tags[0]"), "invalid");
  assert.deepEqual(error.locateAll("options.tags[0]"), ["invalid", "duplicate"]);
  assert.deepEqual(error.findConstraint(/infeasible/), [
    {
      field_path: "obj",
      value: null,
      constraint: "infeasible_lp",
      remediation_hint_key: "errors.422.invalid_prediction_data",
    },
  ]);
  assert.deepEqual(error.remediationKeys(), [
    "errors.422.invalid_prediction_data",
    "errors.422.invalid_prediction_data",
    "errors.422.invalid_prediction_data",
  ]);
});

test("non-array errors payloads degrade to empty errors", () => {
  for (const badErrors of [{ field_path: "x" }, "not-an-array", 123, null]) {
    const error = parseOptiCloudErrorResponse(422, {
      title: "Bad errors payload",
      detail: "errors must be an array",
      status: 422,
      errors: badErrors,
    });

    assert.deepEqual(error.errors, []);
    assert.equal(error.locate("x"), undefined);
    assert.deepEqual(error.remediationKeys(), []);
  }
});
