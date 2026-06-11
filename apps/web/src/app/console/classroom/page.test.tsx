// @vitest-environment happy-dom

import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test-utils/render-with-intl";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
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

import ClassroomPage from "./page";

function renderWithJwt(): void {
  sessionStorage.setItem("jwt_access", "jwt-classroom");
  renderWithIntl(<ClassroomPage />);
}

function fillValidForm(): void {
  fireEvent.change(screen.getByLabelText("Teacher contact / master planning email"), {
    target: { value: "professor@example.edu" },
  });
  fireEvent.change(screen.getByLabelText("Course name"), {
    target: { value: "Optimization 101" },
  });
  fireEvent.change(screen.getByLabelText("Student seats"), {
    target: { value: "50" },
  });
  fireEvent.change(screen.getByLabelText("Shared Credits monthly request"), {
    target: { value: "2000" },
  });
}

describe("ClassroomPage", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    sessionStorage.clear();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("redirects unauthenticated users to login", async () => {
    renderWithIntl(<ClassroomPage />);

    await waitFor(() => {
      expect(mocks.push).toHaveBeenCalledWith("/auth/login");
    });
  });

  it("renders a local v1 manual cohort draft without network or storage writes", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storageSet = vi.spyOn(Storage.prototype, "setItem");
    renderWithJwt();
    storageSet.mockClear();
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Generate local Classroom stub" }));

    expect(await screen.findByText("Local v1 Classroom Plan stub")).toBeTruthy();
    expect(screen.getByText("professor@example.edu")).toBeTruthy();
    expect(screen.getByText("Optimization 101")).toBeTruthy();
    expect(screen.getByText("50")).toBeTruthy();
    expect(screen.getByText("2000 Credits")).toBeTruthy();
    expect(screen.getByText("manual request / planning estimate")).toBeTruthy();
    expect(screen.getByText("v1 manual handling")).toBeTruthy();
    expect(screen.getByText(/no teacher master account/)).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storageSet).not.toHaveBeenCalled();
  });

  it("blocks cohorts above 200 seats with explicit copy", async () => {
    renderWithJwt();
    fillValidForm();
    fireEvent.change(screen.getByLabelText("Student seats"), {
      target: { value: "201" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Generate local Classroom stub" }));

    expect(
      await screen.findByText("Classroom Plan cohort is capped at 200 students."),
    ).toBeTruthy();
    expect(screen.queryByText("Local v1 Classroom Plan stub")).toBeNull();
  });

  it("renders LMS planned status and privacy/ethics boundaries", async () => {
    renderWithJwt();
    fillValidForm();
    fireEvent.change(screen.getByLabelText("LMS provider"), {
      target: { value: "canvas" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Generate local Classroom stub" }));

    expect((await screen.findAllByText("Canvas")).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("LTI 1.3 foundation / planned")).toBeTruthy();
    expect(screen.getByText("connected=false")).toBeTruthy();
    expect(screen.getByText(/students register with education email/i)).toBeTruthy();
    expect(screen.getByText(/No LMS gradebook/i)).toBeTruthy();
    expect(screen.getByText(/Student input belongs to students/)).toBeTruthy();
    expect(screen.getByText(/not Provider training data/)).toBeTruthy();
    expect(screen.getByText(/IRB or school ethics path/)).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Academic Provider Handbook" }).getAttribute("href"),
    ).toBe("/docs/academic-provider-handbook");
  });

  it("does not ask for or render student roster or sensitive classroom artifacts", async () => {
    renderWithJwt();

    expect(screen.queryByLabelText(/student email/i)).toBeNull();
    expect(screen.queryByLabelText(/grade/i)).toBeNull();
    expect(screen.queryByLabelText(/LMS token/i)).toBeNull();
    expect(screen.queryByText(/api key/i)).toBeNull();
    expect(screen.queryByText(/jwt/i)).toBeNull();
    expect(screen.queryByText(/raw roster/i)).toBeNull();
    expect(screen.queryByText(/billing ref/i)).toBeNull();
    expect(screen.queryByText(/Provider training payload/i)).toBeNull();
  });

  it("includes Classroom in Console navigation", () => {
    renderWithJwt();

    expect(screen.getByRole("link", { name: "Classroom" }).getAttribute("href")).toBe(
      "/console/classroom",
    );
  });
});
