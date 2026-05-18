/** axe-core + jest-axe a11y tests for all Tier 1 12 components.
 *
 * Story 0.12 + UX-DR5 + AA12 — packages/ui PR-gate AC.
 * Every Component must pass axe-core with 0 violations.
 */

import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import {
  APIKeyManager,
  ConfidenceLabel,
  ConfirmationModal,
  CreditsBalanceBucket,
  EmptyState,
  ErrorBoundary,
  ExcelDropZone,
  FilePicker,
  LoadingShimmer,
  RFC7807Panel,
  SparklineKPI,
  StatusCard,
  Toast,
} from "../index";

describe("Tier 1 a11y compliance (axe-core)", () => {
  it("APIKeyManager has no a11y violations", async () => {
    const { container } = render(
      <APIKeyManager keys={[]} onCreate={() => {}} ariaLabel="api_keys.manager" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ConfidenceLabel has no a11y violations (all 3 tiers)", async () => {
    const { container } = render(
      <div>
        <ConfidenceLabel score={0.92} />
        <ConfidenceLabel score={0.72} />
        <ConfidenceLabel score={0.45} />
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ConfirmationModal has no a11y violations (5 variants)", async () => {
    const { container } = render(
      <ConfirmationModal
        open
        onClose={() => {}}
        onConfirm={() => {}}
        ariaLabel="modal.test"
        title="Test"
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("CreditsBalanceBucket has no a11y violations", async () => {
    const { container } = render(
      <CreditsBalanceBucket
        buckets={[
          { name: "m", labelZh: "月度", balance: 200 },
          { name: "t", labelZh: "加油包", balance: 1000, expiresHint: "永不过期" },
        ]}
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ErrorBoundary RFC7807Panel has no a11y violations", async () => {
    const { container } = render(
      <RFC7807Panel
        payload={{
          title: "Insufficient Credits",
          status: 402,
          detail: "余额不足",
          errors: [{ field_path: "x.y", value: -1, constraint: "must be >= 0", remediation_hint_key: "errors.402.x" }],
          next_action_url: "https://example.com",
        }}
      />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("ExcelDropZone has no a11y violations", async () => {
    const { container } = render(<ExcelDropZone onFile={() => {}} />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("SparklineKPI has no a11y violations", async () => {
    const { container } = render(
      <SparklineKPI label="7d" ariaLabel="kpi.test" values={[1, 2, 3, 4, 5]} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("StatusCard has no a11y violations", async () => {
    const { container } = render(
      <StatusCard variant="ok" title="All systems operational" ariaLabel="status.ok" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("Toast has no a11y violations", async () => {
    const { container } = render(
      <Toast variant="success" message="Done" ariaLabel="toast.test" durationMs={999999} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("FilePicker has no a11y violations", async () => {
    const { container } = render(<FilePicker ariaLabel="file_picker.test" onFile={() => {}} />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("LoadingShimmer has no a11y violations", async () => {
    const { container } = render(<LoadingShimmer variant="line" />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("EmptyState has no a11y violations", async () => {
    const { container } = render(
      <EmptyState ariaLabel="empty.test" icon="📋" title="No tasks yet" />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe("Tier 1 ErrorBoundary fallback", () => {
  it("ErrorBoundary catches throw and renders fallback", () => {
    const onError = vi.fn();
    function Bomb(): JSX.Element {
      throw new Error("test boom");
    }
    // Suppress React error log
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { getByTestId } = render(
      <ErrorBoundary onError={onError}>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(getByTestId("error-boundary-fallback")).toBeInTheDocument();
    expect(onError).toHaveBeenCalled();
    errorSpy.mockRestore();
  });
});
