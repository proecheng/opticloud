import { afterEach, describe, expect, it, vi } from "vitest";

import { submitLegalInquiry } from "./api";

describe("legal inquiry API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs legal inquiry to billing legal path with JWT and UUID idempotency", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          inquiry_id: "8a0b30c1-7008-4d06-bf0b-e9d22270e66d",
          status: "submitted",
          submitted_at: "2026-06-04T02:00:00Z",
          sla_due_at: "2026-06-05T02:00:00Z",
          sla_hours: 24,
          linear_ticket: {
            provider: "linear",
            status: "pending",
            reference: "OPTI-LEGAL-20260604-ABC123",
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await submitLegalInquiry(
      "jwt-team",
      {
        category: "pipl",
        contact_email: "legal@example.com",
        company_name: "ACME",
        subject: "DPA review",
        message: "Please review our data processing terms.",
        urgency: "normal",
      },
      "8a0b30c1-7008-4d06-bf0b-e9d22270e66d",
    );

    expect(result.linear_ticket.reference).toBe("OPTI-LEGAL-20260604-ABC123");
    const [url, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(url).toBe("http://localhost:8003/v1/legal/inquiry");
    expect(init?.method).toBe("POST");
    expect(headers.get("Authorization")).toBe("Bearer jwt-team");
    expect(headers.get("Idempotency-Key")).toBe("8a0b30c1-7008-4d06-bf0b-e9d22270e66d");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Accept-Language")).toBe("zh-CN");
    expect(headers.get("X-Billing-Charge-Id")).toBeNull();
    expect(headers.get("X-Internal-Service-Auth")).toBeNull();
    expect(headers.get("X-Internal-User-Id")).toBeNull();
    expect(JSON.parse(String(init?.body))).toMatchObject({
      category: "pipl",
      contact_email: "legal@example.com",
      subject: "DPA review",
      message: "Please review our data processing terms.",
    });
  });

  it("generates a UUID idempotency key when the caller does not provide one", async () => {
    const randomUUID = vi.fn(() => "11111111-2222-4333-8444-555555555555");
    vi.stubGlobal("crypto", { randomUUID });
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          inquiry_id: "8a0b30c1-7008-4d06-bf0b-e9d22270e66d",
          status: "submitted",
          submitted_at: "2026-06-04T02:00:00Z",
          sla_due_at: "2026-06-05T02:00:00Z",
          sla_hours: 24,
          linear_ticket: {
            provider: "linear",
            status: "pending",
            reference: "OPTI-LEGAL-20260604-ABC123",
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    await submitLegalInquiry("jwt-team", {
      category: "pipl",
      contact_email: "legal@example.com",
      subject: "DPA review",
      message: "Please review our data processing terms.",
      urgency: "normal",
    });

    const [, init] = fetchMock.mock.calls[0]!;
    const headers = new Headers(init?.headers);
    expect(randomUUID).toHaveBeenCalledOnce();
    expect(headers.get("Idempotency-Key")).toBe("11111111-2222-4333-8444-555555555555");
  });
});
