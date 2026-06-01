import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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
  owner_user_id_suffix: "very-long-owner-suffix-user-user-user-user",
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
      label: {
        zh: "近 7 天实际用量支出",
        en: "Last 7 days actual usage spend",
      },
    },
  ],
  line_items: [
    {
      id: "tx-1",
      created_at: "2026-05-10T00:00:00Z",
      kind: "charge",
      bucket: "monthly",
      label: {
        zh: "使用扣费-非常长的双语标签用于验证换行而不是溢出",
        en: "Usage charge with a very long bilingual label for wrapping",
      },
      direction: "debit",
      direction_label: { zh: "支出", en: "Debit" },
      amount: "-0.50",
      source_amount: "-0.5000",
      currency: "CNY",
      details: {
        authorization: "Bearer should-not-render",
        raw_payload: "secret solver payload",
      },
    },
  ],
};

describe("InvoiceCard", () => {
  it("renders the billing statement contract without raw details", () => {
    render(<InvoiceCard invoice={invoice} />);

    expect(screen.getByTestId("invoice-card")).toBeInTheDocument();
    expect(screen.getByText("OptiCloud 账单明细")).toBeInTheDocument();
    expect(screen.getByText("OptiCloud Billing Statement")).toBeInTheDocument();
    expect(screen.getByText("非税务发票 / Not a tax invoice")).toBeInTheDocument();
    expect(screen.getByText("¥1999.50")).toBeInTheDocument();
    expect(screen.getByText("-¥0.50")).toBeInTheDocument();
    expect(screen.getByText(/入门版 \/ Starter/)).toBeInTheDocument();
    expect(screen.getByText(/Last 7 days actual usage spend/)).toBeInTheDocument();
    expect(screen.getByText(/Usage charge with a very long bilingual label/)).toBeInTheDocument();
    expect(screen.queryByText(/Bearer should-not-render|secret solver payload/i)).not.toBeInTheDocument();
  });

  it("fires the parent-owned PDF callback", () => {
    const onDownloadPdf = vi.fn();
    render(<InvoiceCard invoice={invoice} onDownloadPdf={onDownloadPdf} />);

    fireEvent.click(screen.getByTestId("invoice-download"));

    expect(onDownloadPdf).toHaveBeenCalledTimes(1);
  });

  it("handles empty and malformed optional values safely", () => {
    render(
      <InvoiceCard
        invoice={{
          ...invoice,
          period_start: "not-a-date",
          period_end: "",
          subscription: {
            ...invoice.subscription,
            current_period_start: null,
            current_period_end: "bad-date",
          },
          usage_summary: [],
          line_items: [],
          line_item_count: 0,
        }}
        isDownloading
        onDownloadPdf={vi.fn()}
      />,
    );

    expect(screen.getByTestId("invoice-empty-line-items")).toHaveTextContent("暂无明细");
    expect(screen.getByTestId("invoice-download")).toBeDisabled();
    expect(screen.queryByText(/Invalid Date|NaN/i)).not.toBeInTheDocument();
  });
});
