import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SparklineKPI } from "./index";

describe("SparklineKPI", () => {
  it("renders finite values and chart points", () => {
    render(
      <SparklineKPI
        label="近 7 天"
        ariaLabel="billing.usage_trends.7d.actual_spend"
        values={[0, 1.5, 3]}
        unit="CNY"
      />,
    );

    expect(screen.getByTestId("sparkline-kpi")).toHaveTextContent("近 7 天");
    expect(screen.getByText("3")).toBeInTheDocument();
    const polyline = document.querySelector("polyline");
    expect(polyline?.getAttribute("points")).not.toMatch(/NaN|Infinity/);
  });

  it("normalizes empty and non-finite values without blank charts", () => {
    render(
      <SparklineKPI
        label="近 30 天"
        ariaLabel="billing.usage_trends.30d.actual_spend"
        values={[Number.NaN, Number.POSITIVE_INFINITY]}
        unit="CNY"
      />,
    );

    expect(screen.getByText("0")).toBeInTheDocument();
    const svg = document.querySelector("svg");
    const polyline = document.querySelector("polyline");
    expect(svg?.getAttribute("width")).toBe("120");
    expect(svg?.getAttribute("height")).toBe("40");
    expect(polyline?.getAttribute("points")).toBe("0,40 120,40");
  });

  it("falls back to one zero point for empty series", () => {
    render(
      <SparklineKPI
        label="空趋势"
        ariaLabel="billing.usage_trends.empty"
        values={[]}
        unit="CNY"
      />,
    );

    const polyline = document.querySelector("polyline");
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(polyline?.getAttribute("points")).toBe("0,40");
    expect(screen.getByTestId("sparkline-kpi").getAttribute("aria-describedby")).toBeTruthy();
  });
});
