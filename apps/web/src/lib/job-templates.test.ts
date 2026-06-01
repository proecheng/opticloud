import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createJobTemplate,
  deleteJobTemplate,
  getJobTemplate,
  listJobTemplates,
} from "./api";

const detail = {
  id: "2c4e9e2a-6bdf-49ef-bf03-12d8ee160bef",
  name: "月度销量基线",
  description: "saved prediction",
  source_kind: "prediction",
  source_id: "1b5205ef-3baa-49c4-b31c-9b1e11e9ef7c",
  task_type: "forecast",
  payload_schema_version: "prediction_request_v1",
  payload_json: { family: "arima", data: [1, 2, 3], horizon: 3 },
  payload_sha256: "abc123",
  version: 1,
  root_template_id: "2c4e9e2a-6bdf-49ef-bf03-12d8ee160bef",
  parent_template_id: null,
  created_at: "2026-06-01T01:00:00Z",
  updated_at: "2026-06-01T01:00:00Z",
};

describe("job templates API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates a job template against solver with API-key auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(detail), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await createJobTemplate("sk-test", {
      name: "月度销量基线",
      description: "saved prediction",
      source_kind: "prediction",
      source_id: "1b5205ef-3baa-49c4-b31c-9b1e11e9ef7c",
    });

    expect(result.payload_schema_version).toBe("prediction_request_v1");
    expect(result.payload_json.family).toBe("arima");
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://localhost:8002/v1/job-templates");
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer sk-test");
    expect(init?.body).toBe(
      JSON.stringify({
        name: "月度销量基线",
        description: "saved prediction",
        source_kind: "prediction",
        source_id: "1b5205ef-3baa-49c4-b31c-9b1e11e9ef7c",
      }),
    );
  });

  it("lists and reads templates without requiring payloads in list items", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ items: [{ ...detail, payload_json: undefined }] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(detail), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );

    const listed = await listJobTemplates("sk-test");
    const read = await getJobTemplate("sk-test", detail.id);

    expect(listed.items[0]?.id).toBe(detail.id);
    expect("payload_json" in (listed.items[0] ?? {})).toBe(false);
    expect(read.payload_json.horizon).toBe(3);
    expect(fetchMock.mock.calls[0]?.[0]).toBe("http://localhost:8002/v1/job-templates");
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `http://localhost:8002/v1/job-templates/${detail.id}`,
    );
  });

  it("deletes templates with 204 response support", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(deleteJobTemplate("sk-test", detail.id)).resolves.toBeUndefined();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe(`http://localhost:8002/v1/job-templates/${detail.id}`);
    expect(init?.method).toBe("DELETE");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer sk-test");
  });

  it("preserves RFC7807-style errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          title: "Source Task Not Completed",
          status: 422,
          detail: "source task status is queued, expected completed",
          errors: [
            {
              field_path: "source_id",
              value: detail.source_id,
              constraint: "source task status must be completed",
              remediation_hint_key: "errors.422.source_task_not_completed",
            },
          ],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      createJobTemplate("sk-test", {
        name: "bad",
        source_kind: "prediction",
        source_id: detail.source_id,
      }),
    ).rejects.toMatchObject({
      status: 422,
      title: "Source Task Not Completed",
      errors: [
        expect.objectContaining({
          field_path: "source_id",
          constraint: "source task status must be completed",
        }),
      ],
    });
  });
});
