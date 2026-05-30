// @vitest-environment happy-dom

import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  requestDataExport: vi.fn(),
  getDataExportStatus: vi.fn(),
  downloadDataExport: vi.fn(),
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
  requestDataExport: mocks.requestDataExport,
  getDataExportStatus: mocks.getDataExportStatus,
  downloadDataExport: mocks.downloadDataExport,
}));

import DataExportsConsolePage from "./page";

const queuedJson = {
  id: "json-export",
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
};

const completedJson = {
  ...queuedJson,
  status: "completed",
  completed_at: "2026-05-30T00:01:00Z",
  expires_at: "2026-06-06T00:01:00Z",
  download_url: "/v1/auth/data-exports/json-export/download",
  package_sha256: "a".repeat(64),
  package_bytes: 128,
};

const failedCsv = {
  id: "csv-export",
  status: "failed",
  format: "csv",
  requested_at: "2026-05-30T00:00:00Z",
  sla_deadline_at: "2026-06-06T00:00:00Z",
  completed_at: null,
  expires_at: null,
  download_url: null,
  package_sha256: null,
  package_bytes: null,
  last_error: "RuntimeError: data export failed",
};

const expiredJson = {
  ...queuedJson,
  status: "expired",
  expires_at: "2026-05-30T00:01:00Z",
};

describe("DataExportsConsolePage", () => {
  beforeEach(() => {
    vi.useRealTimers();
    mocks.push.mockReset();
    mocks.requestDataExport.mockReset();
    mocks.getDataExportStatus.mockReset();
    mocks.downloadDataExport.mockReset();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("redirects unauthenticated users to login", () => {
    render(<DataExportsConsolePage />);

    expect(mocks.push).toHaveBeenCalledWith("/auth/login");
  });

  it("requests JSON and polls only that format", async () => {
    vi.useFakeTimers();
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.requestDataExport.mockResolvedValueOnce(queuedJson);
    mocks.getDataExportStatus.mockResolvedValueOnce(completedJson);

    render(<DataExportsConsolePage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "请求 JSON" }));
    });
    expect(mocks.requestDataExport).toHaveBeenCalledWith("jwt-test", "json");
    expect(screen.getAllByText("排队中").length).toBeGreaterThan(0);

    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(mocks.getDataExportStatus).toHaveBeenCalledWith("jwt-test", "json-export");
    expect(screen.getAllByText("可下载").length).toBeGreaterThan(0);
    expect(mocks.getDataExportStatus).toHaveBeenCalledTimes(1);
  });

  it("keeps CSV failed state separate from JSON status", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.requestDataExport.mockResolvedValueOnce(failedCsv);

    render(<DataExportsConsolePage />);

    fireEvent.click(screen.getByRole("tab", { name: "CSV" }));
    fireEvent.click(screen.getByRole("button", { name: "请求 CSV" }));

    await waitFor(() => {
      expect(screen.getAllByText("失败").length).toBeGreaterThan(0);
    });
    expect(await screen.findByText("RuntimeError: data export failed")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "JSON" }));
    expect(screen.getAllByText("未请求").length).toBeGreaterThan(0);
  });

  it("renders expired exports as a new-request terminal state", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.requestDataExport.mockResolvedValueOnce(expiredJson);

    render(<DataExportsConsolePage />);

    fireEvent.click(screen.getByRole("button", { name: "请求 JSON" }));

    await waitFor(() => {
      expect(screen.getAllByText("已过期").length).toBeGreaterThan(0);
    });
    expect(await screen.findByText("导出包已过期，请重新发起同一格式请求。")).toBeTruthy();
    expect((screen.getByRole("button", { name: "请求 JSON" }) as HTMLButtonElement).disabled).toBe(
      false,
    );
  });

  it("ignores stale polling responses after the format state has moved on", async () => {
    vi.useFakeTimers();
    sessionStorage.setItem("jwt_access", "jwt-test");
    const newerJson = { ...queuedJson, id: "json-export-new" };
    const staleCompletedJson = { ...completedJson, id: "json-export-old" };
    mocks.requestDataExport.mockResolvedValueOnce(newerJson);
    mocks.getDataExportStatus.mockResolvedValueOnce(staleCompletedJson);

    render(<DataExportsConsolePage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "请求 JSON" }));
    });
    await act(async () => {
      vi.advanceTimersByTime(2000);
    });

    expect(screen.getByText("json-export-new")).toBeTruthy();
    expect(screen.queryByText("json-export-old")).toBeNull();
    expect(screen.getAllByText("排队中").length).toBeGreaterThan(0);
  });

  it("downloads completed exports with object URL revocation and no storage writes", async () => {
    sessionStorage.setItem("jwt_access", "jwt-test");
    mocks.requestDataExport.mockResolvedValueOnce(completedJson);
    mocks.downloadDataExport.mockResolvedValueOnce({
      blob: new Blob(["{}"], { type: "application/json" }),
      filename: "opticloud-pipl-data-export-json-export.json",
      mediaType: "application/json",
    });
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:download");
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

    render(<DataExportsConsolePage />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "请求 JSON" }));
    });
    const statusPanel = screen.getByText("当前状态").closest("div")?.parentElement?.parentElement;
    expect(statusPanel).not.toBeNull();
    expect(within(statusPanel as HTMLElement).getByText("可下载")).toBeTruthy();
    fireEvent.click(within(statusPanel as HTMLElement).getByRole("button", { name: "下载" }));

    await waitFor(() => {
      expect(mocks.downloadDataExport).toHaveBeenCalledWith("jwt-test", completedJson);
    });
    expect(createObjectURL).toHaveBeenCalled();
    expect(anchorClick).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:download");
    expect(storageSet).not.toHaveBeenCalledWith(
      expect.stringMatching(/export|package|token/i),
      expect.any(String),
    );
  });
});
