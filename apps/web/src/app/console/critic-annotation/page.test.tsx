// @vitest-environment happy-dom
/** Critic annotation console smoke tests. */

import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  sampleId: null as string | null,
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    get: (key: string) => (key === "sample" ? mocks.sampleId : null),
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

import CriticAnnotationPage from "./page";

describe("CriticAnnotationPage", () => {
  beforeEach(() => {
    mocks.sampleId = null;
  });

  it("defaults to the first committed batch ticket", () => {
    render(<CriticAnnotationPage />);

    expect(screen.getByTestId("critic-sample-id").textContent).toBe("critic-cal-v1-031");
    expect(screen.getByTestId("critic-batch-progress").textContent).toBe("20 todo");
    expect(screen.getByTestId("critic-local-decision").textContent).toBe("unreviewed");
    expect(screen.getByText("OPTI-CRITIC-ANNOT")).toBeTruthy();
    expect(screen.getByText(/模型输出建议读取服务端环境变量/)).toBeTruthy();
  });

  it("loads a requested sample from the query string", () => {
    mocks.sampleId = "critic-cal-v1-050";

    render(<CriticAnnotationPage />);

    expect(screen.getByTestId("critic-sample-id").textContent).toBe("critic-cal-v1-050");
    expect(screen.getByText(/把结果摘要整理成更容易扫描/)).toBeTruthy();
  });

  it("shows not-found state for unknown samples", () => {
    mocks.sampleId = "critic-cal-v1-999";

    render(<CriticAnnotationPage />);

    expect(screen.getByText("Sample not found")).toBeTruthy();
    expect(screen.getByText("Open first batch ticket")).toBeTruthy();
  });

  it("updates local decision summary without persistence", () => {
    render(<CriticAnnotationPage />);

    fireEvent.click(screen.getByTestId("critic-decision-auto-block"));
    fireEvent.change(screen.getByLabelText("Adjudication note"), {
      target: { value: "needs lead review" },
    });

    expect(screen.getByText(/decision=auto-block/)).toBeTruthy();
    expect(screen.getByText(/note=needs lead review/)).toBeTruthy();
    expect(screen.getByTestId("critic-batch-progress").textContent).toBe("20 todo");
    expect(screen.getByTestId("critic-local-decision").textContent).toBe("auto-block");
  });
});
