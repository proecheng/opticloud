import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { InvoiceCard, type InvoiceCardInvoice } from "./index";

const invoice: InvoiceCardInvoice = {
  period: "2026-05",
  period_start: "2026-05-01T00:00:00Z",
  period_end: "2026-06-01T00:00:00Z",
  status: "final",
  status_label: { zh: "已结算", en: "Final" },
  net_credit_movement: "1999.50",
  actual_spend: "0.50",
  currency: "CNY",
  line_item_count: 1,
  title: { zh: "OptiCloud 账单明细", en: "OptiCloud Billing Statement" },
  tax_disclaimer: { zh: "非税务发票", en: "Not a tax invoice" },
  owner_user_id_suffix: "owner-suffix",
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
      window_days: 30,
      actual_spend: "0.50",
      currency: "CNY",
      label: { zh: "近 30 天实际用量支出", en: "Last 30 days actual usage spend" },
    },
  ],
  line_items: [
    {
      id: "tx-1",
      created_at: "2026-05-10T00:00:00Z",
      kind: "charge",
      bucket: "monthly",
      label: { zh: "使用扣费", en: "Usage charge" },
      direction: "debit",
      direction_label: { zh: "支出", en: "Debit" },
      amount: "-0.50",
      source_amount: "-0.5000",
      currency: "CNY",
      details: { raw_payload: "hidden" },
    },
  ],
};

describe("InvoiceCard a11y", () => {
  it("default state has no violations", async () => {
    const { container } = render(<InvoiceCard invoice={invoice} onDownloadPdf={() => undefined} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("empty line item state has no violations", async () => {
    const { container } = render(
      <InvoiceCard invoice={{ ...invoice, line_items: [], line_item_count: 0 }} />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
