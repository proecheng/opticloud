// @vitest-environment happy-dom

import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test-utils/render-with-intl";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listBillingInvoices: vi.fn(),
  getBillingInvoice: vi.fn(),
  downloadBillingInvoicePdf: vi.fn(),
  getBillingUsageTrends: vi.fn(),
  getBillingBudget: vi.fn(),
  putBillingBudget: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children?: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status: number;
    title: string;
    detail: string;
    constructor(payload: { status: number; title: string; detail: string }) {
      super(payload.detail);
      this.status = payload.status;
      this.title = payload.title;
      this.detail = payload.detail;
    }
  },
  listBillingInvoices: mocks.listBillingInvoices,
  getBillingInvoice: mocks.getBillingInvoice,
  downloadBillingInvoicePdf: mocks.downloadBillingInvoicePdf,
  getBillingUsageTrends: mocks.getBillingUsageTrends,
  getBillingBudget: mocks.getBillingBudget,
  putBillingBudget: mocks.putBillingBudget,
}));

import BillingInvoicesPage from "./page";

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
      details: { reason: "solver_success" },
    },
  ],
};

const trends = {
  trend_contract: "billing_usage_trends_v1",
  generated_at: "2026-05-31T12:00:00Z",
  windows: [
    {
      window_days: 7,
      window_start: "2026-05-25T00:00:00Z",
      window_end: "2026-06-01T00:00:00Z",
      label: { zh: "近 7 天实际用量支出趋势", en: "Last 7 days actual usage spend trend" },
      currency: "CNY",
      total_actual_spend: "7.00",
      average_daily_spend: "1.00",
      points: [
        { date: "2026-05-25", actual_spend: "0.00", currency: "CNY" },
        { date: "2026-05-26", actual_spend: "1.00", currency: "CNY" },
        { date: "2026-05-27", actual_spend: "2.00", currency: "CNY" },
        { date: "2026-05-28", actual_spend: "0.00", currency: "CNY" },
        { date: "2026-05-29", actual_spend: "0.00", currency: "CNY" },
        { date: "2026-05-30", actual_spend: "3.00", currency: "CNY" },
        { date: "2026-05-31", actual_spend: "1.00", currency: "CNY" },
      ],
    },
    {
      window_days: 30,
      window_start: "2026-05-02T00:00:00Z",
      window_end: "2026-06-01T00:00:00Z",
      label: { zh: "近 30 天实际用量支出趋势", en: "Last 30 days actual usage spend trend" },
      currency: "CNY",
      total_actual_spend: "15.00",
      average_daily_spend: "0.50",
      points: Array.from({ length: 30 }, (_, index) => ({
        date: `2026-05-${String(index + 2).padStart(2, "0")}`,
        actual_spend: index === 29 ? "15.00" : "0.00",
        currency: "CNY",
      })),
    },
  ],
};

const budget = {
  budget_control_id: "budget-1",
  enabled: true,
  status: "active",
  monthly_budget_amount: "100.00",
  alert_threshold_ratio: "0.8000",
  period_start: "2026-06-01T00:00:00Z",
  period_end: "2026-07-01T00:00:00Z",
  actual_spend: "70.00",
  percent_used: "0.7000",
  currency: "CNY",
  alert_threshold_reached: false,
  paused: false,
  paused_at: null,
  pause_period_start: null,
  recent_events: [
    {
      id: "event-1",
      event_type: "billing.budget.alerted",
      period_start: "2026-06-01T00:00:00Z",
      period_end: "2026-07-01T00:00:00Z",
      occurred_at: "2026-06-03T00:00:00Z",
      budget_amount: "100.00",
      actual_spend: "80.00",
      percent_used: "0.8000",
      channels: ["email", "in_app"],
    },
  ],
};

describe("BillingInvoicesPage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listBillingInvoices.mockReset();
    mocks.getBillingInvoice.mockReset();
    mocks.downloadBillingInvoicePdf.mockReset();
    mocks.getBillingUsageTrends.mockReset();
    mocks.getBillingBudget.mockReset();
    mocks.putBillingBudget.mockReset();
    mocks.getBillingUsageTrends.mockResolvedValue(trends);
    mocks.getBillingBudget.mockResolvedValue(budget);
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated users to login", () => {
    renderWithIntl(<BillingInvoicesPage />);

    expect(mocks.push).toHaveBeenCalledWith("/auth/login");
  });

  it("renders invoice detail after loading the newest period", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [
        { period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" },
      ],
    });
    mocks.getBillingInvoice.mockResolvedValue(invoice);

    renderWithIntl(<BillingInvoicesPage />);

    expect(await screen.findByText("OptiCloud 账单明细")).toBeTruthy();
    expect(screen.getByText("OptiCloud Billing Statement")).toBeTruthy();
    expect(screen.getByText("非税务发票 / Not a tax invoice")).toBeTruthy();
    expect(screen.getByText("¥1999.50")).toBeTruthy();
    expect(screen.getByText("-¥0.50")).toBeTruthy();
    expect(screen.getByText("月度额度发放 / Monthly credit grant")).toBeTruthy();
    expect(await screen.findByText("用量趋势")).toBeTruthy();
    expect(screen.getByText("近 7 天实际用量支出趋势 / Last 7 days actual usage spend trend")).toBeTruthy();
    expect(screen.getByText("近 30 天实际用量支出趋势 / Last 30 days actual usage spend trend")).toBeTruthy();
    expect(await screen.findByText("月度预算")).toBeTruthy();
    expect(screen.getByText("¥100.00")).toBeTruthy();
    expect(screen.getByText("70%")).toBeTruthy();
    expect(screen.getByText(/已提醒/)).toBeTruthy();
    expect(mocks.getBillingUsageTrends).toHaveBeenCalledWith("jwt-test");
    expect(mocks.getBillingBudget).toHaveBeenCalledWith("jwt-test");
    expect(mocks.listBillingInvoices).toHaveBeenCalledWith("jwt-test");
    expect(mocks.getBillingInvoice).toHaveBeenCalledWith("jwt-test", "2026-05");
  });

  it("keeps invoice data visible when usage trends fail", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [{ period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" }],
    });
    mocks.getBillingInvoice.mockResolvedValue(invoice);
    mocks.getBillingUsageTrends.mockRejectedValue(
      new Error("trend service unavailable"),
    );

    renderWithIntl(<BillingInvoicesPage />);

    expect(await screen.findByText("OptiCloud 账单明细")).toBeTruthy();
    expect(screen.getByText(/用量趋势加载失败/)).toBeTruthy();
    expect(screen.getByText("¥1999.50")).toBeTruthy();
  });

  it("keeps invoices and trends visible when budget loading fails", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [{ period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" }],
    });
    mocks.getBillingInvoice.mockResolvedValue(invoice);
    mocks.getBillingBudget.mockRejectedValue(new Error("budget service unavailable"));

    renderWithIntl(<BillingInvoicesPage />);

    expect(await screen.findByText("OptiCloud 账单明细")).toBeTruthy();
    expect(await screen.findByText("预算加载失败：budget service unavailable")).toBeTruthy();
    expect(screen.getByText("近 7 天实际用量支出趋势 / Last 7 days actual usage spend trend")).toBeTruthy();
  });

  it("keeps the budget card visible when invoice loading fails", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [{ period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" }],
    });
    mocks.getBillingInvoice.mockRejectedValue(new Error("invoice service unavailable"));

    renderWithIntl(<BillingInvoicesPage />);

    expect(await screen.findByText("账单加载失败")).toBeTruthy();
    expect(await screen.findByTestId("budget-alert-card")).toBeTruthy();
    expect(screen.getByText("¥100.00")).toBeTruthy();
    expect(screen.getByText("近 7 天实际用量支出趋势 / Last 7 days actual usage spend trend")).toBeTruthy();
  });

  it("updates and disables monthly budget without hiding invoice content", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [{ period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" }],
    });
    mocks.getBillingInvoice.mockResolvedValue(invoice);
    mocks.putBillingBudget
      .mockResolvedValueOnce({
        ...budget,
        monthly_budget_amount: "80.00",
        actual_spend: "80.00",
        percent_used: "1.0000",
        status: "paused",
        paused: true,
      })
      .mockResolvedValueOnce({
        ...budget,
        enabled: false,
        status: "disabled",
        paused: false,
      });

    renderWithIntl(<BillingInvoicesPage />);
    await screen.findByText("OptiCloud 账单明细");

    fireEvent.change(screen.getByLabelText("预算金额"), { target: { value: "80.00" } });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    expect(await screen.findByText("预算已达到上限，新的扣费已暂停。")).toBeTruthy();
    expect(mocks.putBillingBudget).toHaveBeenCalledWith("jwt-test", {
      monthly_budget_amount: "80.00",
      enabled: true,
    });
    expect(screen.getByText("OptiCloud Billing Statement")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "停用预算" }));

    expect(await screen.findByText("预算控制已停用。")).toBeTruthy();
    expect(mocks.putBillingBudget).toHaveBeenLastCalledWith("jwt-test", { enabled: false });
  });

  it("loads a selected period independently", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [
        { period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" },
        { period: "2026-04", actual_spend: "1.00", net_credit_movement: "100.00" },
      ],
    });
    mocks.getBillingInvoice.mockResolvedValueOnce(invoice).mockResolvedValueOnce({
      ...invoice,
      period: "2026-04",
      net_credit_movement: "123.45",
    });

    renderWithIntl(<BillingInvoicesPage />);

    await screen.findByText("OptiCloud 账单明细");
    fireEvent.change(screen.getByLabelText("账单月份"), { target: { value: "2026-04" } });

    await waitFor(() => {
      expect(mocks.getBillingInvoice).toHaveBeenLastCalledWith("jwt-test", "2026-04");
    });
    expect(screen.getByText("¥123.45")).toBeTruthy();
  });

  it("downloads invoice PDFs through object URLs and avoids storage writes", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({
      items: [{ period: "2026-05", actual_spend: "0.50", net_credit_movement: "1999.50" }],
    });
    mocks.getBillingInvoice.mockResolvedValue(invoice);
    mocks.downloadBillingInvoicePdf.mockResolvedValue({
      blob: new Blob(["%PDF"], { type: "application/pdf" }),
      filename: "opticloud-invoice-2026-05.pdf",
      mediaType: "application/pdf",
    });
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:invoice");
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    const anchorClick = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const element = originalCreateElement(tagName);
      if (tagName.toLowerCase() === "a") {
        Object.defineProperty(element, "click", { value: anchorClick });
      }
      return element;
    });

    renderWithIntl(<BillingInvoicesPage />);
    await screen.findByText("OptiCloud 账单明细");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "下载 PDF" }));
    });

    expect(mocks.downloadBillingInvoicePdf).toHaveBeenCalledWith("jwt-test", "2026-05");
    expect(createObjectURL).toHaveBeenCalled();
    expect(anchorClick).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:invoice");
    expect(storageSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/invoice|pdf|token|budget/i),
      expect.any(String),
    );
  });

  it("keeps billing invoices discoverable from console navigation", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({ items: [] });

    renderWithIntl(<BillingInvoicesPage />);

    await screen.findByText("暂无账单");
    const nav = screen.getByRole("navigation", { name: "Console governance navigation" });
    expect(
      within(nav).getByRole("link", { name: "账单", current: "page" }).getAttribute("href"),
    ).toBe("/console/billing/invoices");
  });
});
