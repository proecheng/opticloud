import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { type VoucherCardVoucher, VoucherCard } from "./index";

const baseVoucher: VoucherCardVoucher = {
  voucherId: "repro-2026-K7X9P2",
  status: "issued",
  createdAt: "2026-05-22T02:56:27.000Z",
  lockedSolver: "highs",
  lockedModelVersion: {
    provider_id: "scipy",
    name: "linprog",
    version: "1.11.4",
  },
  requestFingerprint: "fixture-fingerprint-2026-issued-voucher",
  seedLocked: true,
  seed: null,
};

describe("VoucherCard", () => {
  it("renders the public voucher contract", () => {
    render(<VoucherCard voucher={baseVoucher} canRerun />);

    expect(screen.getByTestId("voucher-card")).toBeInTheDocument();
    expect(screen.getByText("repro-2026-K7X9P2")).toBeInTheDocument();
    expect(screen.getByTestId("voucher-status")).toHaveTextContent("Issued");
    expect(screen.getByTestId("voucher-solver")).toHaveTextContent("highs");
    expect(screen.getByTestId("voucher-model")).toHaveTextContent(
      "scipy/linprog@1.11.4",
    );
    expect(screen.getByTestId("voucher-fingerprint")).toHaveTextContent(
      "fixture-fi...oucher",
    );
    expect(screen.getByTestId("voucher-seed")).toHaveTextContent("Locked (null)");
    expect(screen.queryByText(/email|phone|api key|raw payload/i)).not.toBeInTheDocument();
  });

  it("renders anonymous only when true", () => {
    const { rerender } = render(<VoucherCard voucher={baseVoucher} />);
    expect(screen.queryByTestId("voucher-anonymous")).not.toBeInTheDocument();
    expect(screen.queryByText(/anonymous: false|anonymous: null/i)).not.toBeInTheDocument();

    rerender(<VoucherCard voucher={{ ...baseVoucher, anonymous: true }} />);
    expect(screen.getByTestId("voucher-anonymous")).toHaveTextContent("Anonymous");
  });

  it("fires copy and rerun callbacks with voucher ID", () => {
    const onCopyVoucherId = vi.fn();
    const onRerun = vi.fn();
    render(
      <VoucherCard
        voucher={baseVoucher}
        canRerun
        onCopyVoucherId={onCopyVoucherId}
        onRerun={onRerun}
      />,
    );

    fireEvent.click(screen.getByTestId("voucher-copy"));
    expect(onCopyVoucherId).toHaveBeenCalledWith("repro-2026-K7X9P2");

    fireEvent.click(screen.getByTestId("voucher-rerun"));
    expect(onRerun).toHaveBeenCalledWith("repro-2026-K7X9P2");
  });

  it("disables rerun for non-rerunnable states", () => {
    render(<VoucherCard voucher={{ ...baseVoucher, status: "expired" }} canRerun />);

    const rerun = screen.getByTestId("voucher-rerun") as HTMLButtonElement;
    expect(rerun.disabled).toBe(true);
    expect(screen.getByTestId("voucher-rerun-status")).toHaveTextContent(
      "cannot be rerun",
    );
  });

  it("disables rerun while parent is rerunning", () => {
    render(<VoucherCard voucher={baseVoucher} canRerun isRerunning />);

    const rerun = screen.getByTestId("voucher-rerun") as HTMLButtonElement;
    expect(rerun.disabled).toBe(true);
    expect(screen.getByTestId("voucher-rerun-status")).toHaveTextContent(
      "in progress",
    );
  });

  it("shows lineage and successful child rerun result", () => {
    render(
      <VoucherCard
        voucher={{
          ...baseVoucher,
          status: "rerun_child",
          rerunOfVoucherId: "repro-2026-PARENT",
          sourceOptimizationId: "11111111-1111-1111-1111-111111111111",
          childVoucherId: "repro-2026-CHILD1",
        }}
        canRerun
        rerunResult={{
          childVoucherId: "repro-2026-CHILD2",
          rerunOfVoucherId: "repro-2026-K7X9P2",
          sourceOptimizationId: "22222222-2222-2222-2222-222222222222",
        }}
      />,
    );

    expect(screen.getByTestId("voucher-lineage")).toHaveTextContent(
      "repro-2026-PARENT",
    );
    expect(screen.getByTestId("voucher-source-optimization")).toHaveTextContent(
      "11111111-1111-1111-1111-111111111111",
    );
    expect(screen.getByTestId("voucher-child")).toHaveTextContent("repro-2026-CHILD1");
    expect(screen.getByTestId("voucher-rerun-child-result")).toHaveTextContent(
      "repro-2026-CHILD2",
    );
  });

  it("shows rerun errors without dumping raw payloads", () => {
    render(
      <VoucherCard voucher={baseVoucher} canRerun rerunError="voucher expired after 5 years" />,
    );

    expect(screen.getByTestId("voucher-rerun-status")).toHaveTextContent(
      "voucher expired after 5 years",
    );
    expect(screen.queryByText(/traceback|input_payload|authorization/i)).not.toBeInTheDocument();
  });
});
