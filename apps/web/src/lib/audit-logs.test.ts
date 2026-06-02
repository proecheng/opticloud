import { beforeEach, describe, expect, it, vi } from "vitest";

import { listMyAuditLogs, OptiCloudClientError } from "./api";

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("listMyAuditLogs", () => {
  it("calls the user audit logs endpoint with Authorization and query params", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          next_cursor: "cursor-2",
          limit: 25,
          from: "2026-06-01T00:00:00Z",
          to: "2026-06-02T00:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await listMyAuditLogs("jwt-test", {
      from: "2026-06-01T00:00:00Z",
      to: "2026-06-02T00:00:00Z",
      limit: 25,
      cursor: "cursor-1",
    });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://localhost:8001/v1/me/audit-logs?from=2026-06-01T00%3A00%3A00Z&to=2026-06-02T00%3A00%3A00Z&limit=25&cursor=cursor-1",
    );
    const headers = new Headers(init.headers);
    expect(headers.get("Authorization")).toBe("Bearer jwt-test");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Accept-Language")).toBeTruthy();
    expect(result.next_cursor).toBe("cursor-2");
  });

  it("omits empty optional params and preserves limit zero for backend validation", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [],
          next_cursor: null,
          limit: 50,
          from: "2026-06-01T00:00:00Z",
          to: "2026-06-02T00:00:00Z",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await listMyAuditLogs("jwt-test", {
      from: "",
      to: "  ",
      cursor: null,
      limit: 0,
    });

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8001/v1/me/audit-logs?limit=0");
  });

  it("surfaces normalized RFC7807 errors", async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({
          title: "Unauthorized",
          detail: "missing Authorization",
          request_id: "req-1",
        }),
        { status: 401, headers: { "Content-Type": "application/json" } },
      ),
    );

    try {
      await listMyAuditLogs("bad-jwt");
      throw new Error("expected request to fail");
    } catch (err) {
      expect(err).toBeInstanceOf(OptiCloudClientError);
      expect(err).toMatchObject({
        status: 401,
        title: "Unauthorized",
        detail: "missing Authorization",
        request_id: "req-1",
      });
    }
  });
});
