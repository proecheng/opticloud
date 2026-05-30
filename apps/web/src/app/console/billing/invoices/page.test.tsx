// @vitest-environment happy-dom

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listBillingInvoices: vi.fn(),
  getBillingInvoice: vi.fn(),
  downloadBillingInvoicePdf: vi.fn(),
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

describe("BillingInvoicesPage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listBillingInvoices.mockReset();
    mocks.getBillingInvoice.mockReset();
    mocks.downloadBillingInvoicePdf.mockReset();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated users to login", () => {
    render(<BillingInvoicesPage />);

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

    render(<BillingInvoicesPage />);

    expect(await screen.findByText("OptiCloud 账单明细")).toBeTruthy();
    expect(screen.getByText("OptiCloud Billing Statement")).toBeTruthy();
    expect(screen.getByText("非税务发票 / Not a tax invoice")).toBeTruthy();
    expect(screen.getByText("¥1999.50")).toBeTruthy();
    expect(screen.getByText("-¥0.50")).toBeTruthy();
    expect(screen.getByText("月度额度发放 / Monthly credit grant")).toBeTruthy();
    expect(mocks.listBillingInvoices).toHaveBeenCalledWith("jwt-test");
    expect(mocks.getBillingInvoice).toHaveBeenCalledWith("jwt-test", "2026-05");
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
      net_credit_movement: "100.00",
    });

    render(<BillingInvoicesPage />);

    await screen.findByText("OptiCloud 账单明细");
    fireEvent.change(screen.getByLabelText("账单月份"), { target: { value: "2026-04" } });

    await waitFor(() => {
      expect(mocks.getBillingInvoice).toHaveBeenLastCalledWith("jwt-test", "2026-04");
    });
    expect(screen.getByText("¥100.00")).toBeTruthy();
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

    render(<BillingInvoicesPage />);
    await screen.findByText("OptiCloud 账单明细");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "下载 PDF" }));
    });

    expect(mocks.downloadBillingInvoicePdf).toHaveBeenCalledWith("jwt-test", "2026-05");
    expect(createObjectURL).toHaveBeenCalled();
    expect(anchorClick).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:invoice");
    expect(storageSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/invoice|pdf|token/i),
      expect.any(String),
    );
  });

  it("keeps billing invoices discoverable from console navigation", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.listBillingInvoices.mockResolvedValue({ items: [] });

    render(<BillingInvoicesPage />);

    await screen.findByText("暂无账单");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "账单" }).getAttribute("href")).toBe(
      "/console/billing/invoices",
    );
  });
});
