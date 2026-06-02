// @vitest-environment happy-dom

import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigationMocks = vi.hoisted(() => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
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

vi.mock("next/navigation", () => ({
  notFound: navigationMocks.notFound,
}));

import StatusIncidentPostmortemPage from "./page";

describe("StatusIncidentPostmortemPage", () => {
  beforeEach(() => {
    navigationMocks.notFound.mockClear();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("renders a public P0 postmortem without auth, browser storage, or network access", async () => {
    const storageGet = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("public postmortem page must not read browser storage");
    });
    const storageSet = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("public postmortem page must not write browser storage");
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("public postmortem page must not fetch during render");
    });

    render(
      await StatusIncidentPostmortemPage({
        params: Promise.resolve({
          incidentId: "inc-2026-05-28-deepseek-provider-fallback",
        }),
      }),
    );

    expect(screen.getByRole("heading", { name: /DeepSeek provider outage/i })).toBeTruthy();
    expect(screen.getByText("Incident ID")).toBeTruthy();
    expect(screen.getByText("P0 / critical")).toBeTruthy();
    expect(screen.getByText("What happened")).toBeTruthy();
    expect(screen.getByText("Impact")).toBeTruthy();
    expect(screen.getByText("Detection")).toBeTruthy();
    expect(screen.getByText("Mitigation")).toBeTruthy();
    expect(screen.getByText("Root cause")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Mermaid timeline" })).toBeTruthy();
    expect(screen.getByText(/^timeline$/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Postmortem timeline" })).toBeTruthy();
    expect(screen.queryByText("/auth/login")).toBeNull();
    expect(screen.queryByText(/webhook/i)).toBeNull();
    expect(storageGet).not.toHaveBeenCalled();
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows follow-up ownership and SLA evidence", async () => {
    render(
      await StatusIncidentPostmortemPage({
        params: Promise.resolve({
          incidentId: "inc-2026-05-28-deepseek-provider-fallback",
        }),
      }),
    );

    expect(screen.getByText("Published within 24h SLA")).toBeTruthy();
    const followUps = screen.getByRole("list", { name: "Postmortem follow-up actions" });
    expect(within(followUps).getByText("SRE")).toBeTruthy();
    expect(within(followUps).getByText("Billing")).toBeTruthy();
    expect(screen.getByText(/compensation eligibility/i)).toBeTruthy();
    expect(screen.queryByText(/refund executed/i)).toBeNull();
  });

  it("returns notFound for unknown and non-P0 incidents", async () => {
    await expect(
      StatusIncidentPostmortemPage({
        params: Promise.resolve({ incidentId: "missing" }),
      }),
    ).rejects.toThrow("NEXT_NOT_FOUND");
    await expect(
      StatusIncidentPostmortemPage({
        params: Promise.resolve({ incidentId: "inc-2026-06-02-solver-latency" }),
      }),
    ).rejects.toThrow("NEXT_NOT_FOUND");

    expect(navigationMocks.notFound).toHaveBeenCalledTimes(2);
  });
});
