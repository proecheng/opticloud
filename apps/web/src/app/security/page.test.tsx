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

import SecurityDisclosurePage from "./page";

describe("SecurityDisclosurePage", () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it("renders publicly without auth redirects, browser storage, or network fetch", () => {
    const storageGet = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("public security page must not read browser storage");
    });
    const storageSet = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("public security page must not write browser storage");
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => {
      throw new Error("public security page must not fetch during render");
    });

    render(<SecurityDisclosurePage />);

    expect(screen.getByRole("heading", { name: "Security Disclosure" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "security@opticloud.cn" }).getAttribute("href")).toBe(
      "mailto:security@opticloud.cn",
    );
    expect(screen.queryByText("/auth/login")).toBeNull();
    expect(storageGet).not.toHaveBeenCalled();
    expect(storageSet).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("shows report requirements, SLA, safe harbor, and future policy boundaries", () => {
    render(<SecurityDisclosurePage />);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Security" }).getAttribute("href")).toBe(
      "/security",
    );

    expect(screen.getByText("Affected endpoint or service")).toBeTruthy();
    expect(screen.getByText("Vulnerability class and impact")).toBeTruthy();
    expect(screen.getByText("Reproduction steps or PoC")).toBeTruthy();
    expect(screen.getByText("CVSS estimate")).toBeTruthy();
    expect(screen.getByText("Reporter contact")).toBeTruthy();
    expect(screen.getByText(/Initial acknowledgement target/i).parentElement?.textContent).toContain(
      "48 hours",
    );
    expect(screen.getByText(/CVSS >= 7 remediation target/i).parentElement?.textContent).toContain(
      "7 days",
    );
    expect(screen.getByText(/Stop after minimal proof/i)).toBeTruthy();
    expect(screen.getByText(/Do not exfiltrate customer/i)).toBeTruthy();
    expect(screen.getByText(/Do not perform DDoS/i)).toBeTruthy();
    expect(screen.getAllByText(/synthetic or researcher-owned test data/i).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByText(/ordinary product bugs and support requests/i)).toBeTruthy();
    expect(screen.getAllByText(/handled by the follow-up J9 policy/i).length).toBeGreaterThan(0);
  });

  it("does not claim unimplemented automation is active", () => {
    render(<SecurityDisclosurePage />);

    expect(screen.queryByText(/SMTP auto-reply is active/i)).toBeNull();
    expect(screen.queryByText(/ticket automation is active/i)).toBeNull();
    expect(screen.queryByText(/CVE tracking is active/i)).toBeNull();
    expect(screen.queryByText(/bounty payment is active/i)).toBeNull();
    expect(screen.queryByText(/PGP encrypted intake is active/i)).toBeNull();
  });
});
