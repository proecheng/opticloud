import { afterEach, describe, expect, it, vi } from "vitest";

import { createTeachingGradingBatch, getTeachingGradingBatch } from "./api";

describe("teaching grading API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs a teaching grading batch with API-key auth and idempotency", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          grading_batch_id: "11111111-1111-4111-8111-111111111111",
          assignment_ref: "assign-001",
          rubric_version: "teaching-grading-v1",
          item_count: 1,
          graded_count: 1,
          not_gradable_count: 0,
          created_at: "2026-06-04T10:00:00Z",
          items: [
            {
              index: 0,
              student_ref: "stu-001",
              optimization_id: "22222222-2222-4222-8222-222222222222",
              grading_status: "graded",
              score: 100,
              max_score: 100,
              criteria: [
                {
                  code: "teaching_mode",
                  label_zh: "Teaching Mode",
                  passed: true,
                  points: 25,
                  max_points: 25,
                },
              ],
              feedback_zh: "已按 teaching-grading-v1 自动评分。",
            },
          ],
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await createTeachingGradingBatch(
      "sk-test",
      {
        assignment_ref: "assign-001",
        submissions: [
          {
            student_ref: "stu-001",
            optimization_id: "22222222-2222-4222-8222-222222222222",
          },
        ],
      },
      { idempotencyKey: "idem-grading-1" },
    );

    expect(result.items[0]?.grading_status).toBe("graded");
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://localhost:8002/v1/teaching/grading-batches");
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer sk-test");
    expect(headers.get("Idempotency-Key")).toBe("idem-grading-1");
    expect(JSON.parse(String(init?.body))).toEqual({
      assignment_ref: "assign-001",
      submissions: [
        {
          student_ref: "stu-001",
          optimization_id: "22222222-2222-4222-8222-222222222222",
        },
      ],
    });
  });

  it("GETs a teaching grading batch with encoded id and read-only API-key auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          grading_batch_id: "batch/with space",
          assignment_ref: "assign-001",
          rubric_version: "teaching-grading-v1",
          item_count: 0,
          graded_count: 0,
          not_gradable_count: 0,
          created_at: "2026-06-04T10:00:00Z",
          items: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getTeachingGradingBatch("sk-test", "batch/with space");

    expect(result.grading_batch_id).toBe("batch/with space");
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://localhost:8002/v1/teaching/grading-batches/batch%2Fwith%20space");
    expect(init?.method).toBeUndefined();
    expect(init?.body).toBeUndefined();
    expect(headers.get("Authorization")).toBe("Bearer sk-test");
    expect(headers.get("Idempotency-Key")).toBeNull();
  });
});
