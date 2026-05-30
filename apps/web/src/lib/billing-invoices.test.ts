import { afterEach, describe, expect, it, vi } from "vitest";

import {
  downloadBillingInvoicePdf,
  getBillingInvoice,
  listBillingInvoices,
} from "./api";

const invoice = {
  period: "2026-05",
  period_start: "2026-05-01T00:00:00Z",
  period_end: "2026-06-01T00:00:00Z",
  status: "final",
  status_label: { zh: "已结算", en: "Final" },
  net_credit_movement: "1999.50",
  actual_spend: "0.50",
  currency: "CNY",
  line_item_count: 2,
  title: { zh: "OptiCloud 账单明细", en: "OptiCloud Billing Statement" },
  tax_disclaimer: { zh: "非税务发票", en: "Not a tax invoice" },
  owner_user_id_suffix: "1234abcd",
  subscription: {
    plan_code: "starter",
    plan_label: "Starter",
    plan_label_zh: "入门版",
    status: "active",
    current_period_start: "2026-05-01T00:00:00Z",
    current_period_end: "2026-06-01T00:00:00Z",
  },
  credit_subtotal: "2005.50",
  debit_subtotal: "6.00",
  trend_contract: "invoice_summary",
  usage_summary: [
    {
      window_days: 7,
      actual_spend: "0.50",
      currency: "CNY",
      label: { zh: "近 7 天实际用量支出", en: "Last 7 days actual usage spend" },
    },
  ],
  line_items: [
    {
      id: "tx-1",
      created_at: "2026-05-01T00:00:00Z",
      kind: "monthly_refill",
      bucket: "monthly",
      label: { zh: "月度额度发放", en: "Monthly credit grant" },
      direction: "credit",
      direction_label: { zh: "收入", en: "Credit" },
      amount: "2000.00",
      source_amount: "2000.0000",
      currency: "CNY",
      details: {},
    },
  ],
};

describe("billing invoice API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("lists billing invoices with bearer auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [invoice] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await listBillingInvoices("jwt-test");

    expect(result.items[0]?.period).toBe("2026-05");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8003/v1/billing/invoices");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
  });

  it("gets one billing invoice by encoded period", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(invoice), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getBillingInvoice("jwt-test", "2026-05");

    expect(result.title.en).toBe("OptiCloud Billing Statement");
    const [url] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8003/v1/billing/invoices/2026-05");
  });

  it("downloads a PDF invoice with Authorization and deterministic filename", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(new Blob(["%PDF invoice"], { type: "application/pdf" }), {
        status: 200,
        headers: { "Content-Type": "application/pdf" },
      }),
    );

    const result = await downloadBillingInvoicePdf("jwt-test", "2026-05");

    expect(result.filename).toBe("opticloud-invoice-2026-05.pdf");
    expect(result.mediaType).toBe("application/pdf");
    expect(await result.blob.text()).toBe("%PDF invoice");
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8003/v1/billing/invoices/2026-05/download");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
  });

  it("turns failed PDF downloads into client errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ title: "Invoice Not Found", detail: "missing" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(downloadBillingInvoicePdf("jwt-test", "2026-04")).rejects.toMatchObject({
      status: 404,
      title: "Invoice Not Found",
      detail: "missing",
    });
  });
});
