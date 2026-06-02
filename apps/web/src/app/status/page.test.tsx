// @vitest-environment happy-dom

import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

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

import { PUBLIC_STATUS_MODEL } from "@/lib/status-page";

import StatusPage, { StatusPageView } from "./page";

describe("StatusPage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("renders publicly without auth redirects or browser storage access", () => {
    const storageGet = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("public status page must not read browser storage");
    });
    const storageSet = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("public status page must not write browser storage");
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("public status page must not fetch during render");
    });

    render(<StatusPage />);

    expect(screen.getByRole("heading", { name: "OptiCloud Status" })).toBeTruthy();
    expect(screen.getByText("API Gateway")).toBeTruthy();
    expect(screen.getByText("Incident History")).toBeTruthy();
    expect(screen.queryByText("/auth/login")).toBeNull();
    expect(storageGet).not.toHaveBeenCalled();
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows incident history, RSS, and subscription discovery entries", () => {
    render(<StatusPage />);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Status" }).getAttribute("href")).toBe(
      "/status",
    );
    expect(
      screen
        .getAllByRole("link", { name: "RSS feed" })
        .map((link) => link.getAttribute("href")),
    ).toEqual(["/status/rss.xml", "/status/rss.xml"]);
    expect(screen.getByText("Email notifications")).toBeTruthy();
    expect(screen.getByText("Webhook callbacks")).toBeTruthy();
    expect(screen.getAllByText(/follow-up authenticated subscription flow/i)).toHaveLength(2);
    expect(screen.getAllByText("Solver queue latency above target").length).toBeGreaterThanOrEqual(
      2,
    );
  });

  it("renders an explicit empty state when incident history is empty", () => {
    render(<StatusPageView model={{ ...PUBLIC_STATUS_MODEL, incidents: [] }} />);

    expect(screen.getByText("No incidents reported")).toBeTruthy();
    expect(screen.getByText("No active incident in the public model.")).toBeTruthy();
  });
});
