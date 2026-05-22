// @vitest-environment happy-dom
/** Repro dashboard smoke tests. */

import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  rerunMock: vi.fn(),
  clipboardWriteText: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status = 400;
    title = "Bad Request";
    detail = "Request failed";
  },
  rerunReproductionVoucher: mocks.rerunMock,
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children?: ReactNode;
  }) => <a href={href} {...props}>{children}</a>,
}));

import ReproConsolePage from "./page";

describe("ReproConsolePage", () => {
  beforeEach(() => {
    mocks.rerunMock.mockReset();
  });

  it("renders fixtures and surfaces rerun results", async () => {
    mocks.rerunMock.mockResolvedValue({
      optimization_id: "opt-1",
      status: "completed",
      solution: { x: [1] },
      objective: 1,
      model_version: {
        provider_id: "scipy",
        kind: "open_source",
        version: "1.11.4",
        provider_url: "https://scipy.org",
      },
      solve_seconds: 1,
      created_at: "2026-05-22T03:00:00Z",
      completed_at: "2026-05-22T03:00:01Z",
      citation: null,
      ip_attribution: null,
      rerun_of_voucher_id: "repro-2026-K7X9P2",
      source_optimization_id: "11111111-1111-1111-1111-111111111111",
      reproducibility: {
        requested: true,
        request_fingerprint: "x",
        locked_model_version: {
          provider_id: "scipy",
          kind: "open_source",
          version: "1.11.4",
          provider_url: "https://scipy.org",
        },
        locked_solver: "highs",
        seed_locked: true,
        seed: null,
        voucher_id: "repro-2026-CHILD1",
      },
    });

    render(<ReproConsolePage />);

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("voucher-rerun"));

    expect(mocks.rerunMock).toHaveBeenCalledWith("sk-test", "repro-2026-K7X9P2");
    expect((await screen.findByTestId("voucher-rerun-child-result")).textContent).toBe(
      "repro-2026-CHILD1",
    );
    expect((await screen.findByTestId("voucher-rerun-source-result")).textContent).toBe(
      "source=11111111-1111-1111-1111-111111111111",
    );
  });
});
