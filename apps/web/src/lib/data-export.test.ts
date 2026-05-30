import { afterEach, describe, expect, it, vi } from "vitest";

import {
  downloadDataExport,
  getDataExportStatus,
  requestDataExport,
} from "./api";

describe("data export API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs a JSON data export request by default with bearer token", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "export-json",
          status: "queued",
          format: "json",
          requested_at: "2026-05-30T00:00:00Z",
          sla_deadline_at: "2026-06-06T00:00:00Z",
          completed_at: null,
          expires_at: null,
          download_url: null,
          package_sha256: null,
          package_bytes: null,
          last_error: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await requestDataExport("jwt-test");

    expect(result.format).toBe("json");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/data-exports");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
    expect(init?.body).toBe(JSON.stringify({ format: "json" }));
  });

  it("POSTs a CSV data export request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "export-csv",
          status: "queued",
          format: "csv",
          requested_at: "2026-05-30T00:00:00Z",
          sla_deadline_at: "2026-06-06T00:00:00Z",
          completed_at: null,
          expires_at: null,
          download_url: null,
          package_sha256: null,
          package_bytes: null,
          last_error: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await requestDataExport("jwt-test", "csv");

    expect(result.format).toBe("csv");
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init?.body).toBe(JSON.stringify({ format: "csv" }));
  });

  it("GETs a data export status by id", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "export-1",
          status: "completed",
          format: "json",
          requested_at: "2026-05-30T00:00:00Z",
          sla_deadline_at: "2026-06-06T00:00:00Z",
          completed_at: "2026-05-30T00:01:00Z",
          expires_at: "2026-06-06T00:01:00Z",
          download_url: "/v1/auth/data-exports/export-1/download",
          package_sha256: "a".repeat(64),
          package_bytes: 128,
          last_error: null,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await getDataExportStatus("jwt-test", "export-1");

    expect(result.status).toBe("completed");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/data-exports/export-1");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
  });

  it("downloads CSV package with Authorization and zip filename", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(new Blob(["zip-bytes"], { type: "application/zip" }), {
        status: 200,
        headers: { "Content-Type": "application/zip" },
      }),
    );

    const result = await downloadDataExport("jwt-test", {
      id: "export-csv",
      format: "csv",
    });

    expect(result.filename).toBe("opticloud-pipl-data-export-export-csv.zip");
    expect(result.mediaType).toContain("application/zip");
    expect(await result.blob.text()).toBe("zip-bytes");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/data-exports/export-csv/download");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
  });

  it("turns failed downloads into client errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ title: "Conflict", detail: "not completed" }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(
      downloadDataExport("jwt-test", { id: "export-json", format: "json" }),
    ).rejects.toMatchObject({
      status: 409,
      title: "Conflict",
      detail: "not completed",
    });
  });
});
