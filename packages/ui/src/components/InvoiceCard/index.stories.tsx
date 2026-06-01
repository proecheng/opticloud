import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

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
    {
      id: "tx-2",
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

const meta = {
  title: "Tier 2/InvoiceCard",
  component: InvoiceCard,
  parameters: { layout: "padded" },
  args: {
    invoice,
    onDownloadPdf: fn(),
  },
} satisfies Meta<typeof InvoiceCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Downloading: Story = {
  args: { isDownloading: true },
};

export const EmptyLineItems: Story = {
  args: {
    invoice: { ...invoice, line_items: [], line_item_count: 0 },
    onDownloadPdf: undefined,
  },
};

export const LongContent: Story = {
  args: {
    invoice: {
      ...invoice,
      owner_user_id_suffix: "very-long-owner-suffix-1234567890abcdef1234567890abcdef",
      net_credit_movement: "9999999999.99",
      actual_spend: "123456789.99",
      line_items: invoice.line_items.map((item) => ({
        ...item,
        label: {
          zh: `${item.label.zh}-非常长的制造业计费项目名称用于验证响应式换行`,
          en: `${item.label.en} with a long bilingual statement label for responsive wrapping`,
        },
      })),
    },
  },
};
