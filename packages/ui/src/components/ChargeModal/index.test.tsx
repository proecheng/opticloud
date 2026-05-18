/** ChargeModal unit tests (Story 5.A.1 AC8 + R1.6 Vitest lock). */

import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChargeModal } from "./index";

const baseProps = {
  open: true,
  amount: 6,
  currency: "CNY",
  balance: 50,
  purpose: "Test charge",
  referenceId: "00000000-0000-0000-0000-000000000000",
};

describe("ChargeModal", () => {
  it("renders amount and balance", () => {
    render(<ChargeModal {...baseProps} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.getByTestId("charge-amount")).toHaveTextContent("¥6.00");
    expect(screen.getByTestId("charge-balance-before")).toHaveTextContent("¥50.00");
    expect(screen.getByTestId("charge-balance-after")).toHaveTextContent("¥44.00");
  });

  it("fires onConfirm when user clicks Confirm", () => {
    const onConfirm = vi.fn();
    render(<ChargeModal {...baseProps} onConfirm={onConfirm} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByTestId("charge-confirm"));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("fires onCancel when user clicks Cancel", () => {
    const onCancel = vi.fn();
    render(<ChargeModal {...baseProps} onConfirm={vi.fn()} onCancel={onCancel} />);
    fireEvent.click(screen.getByTestId("charge-cancel"));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("disables Confirm when balance is insufficient", () => {
    render(
      <ChargeModal {...baseProps} balance={3} onConfirm={vi.fn()} onCancel={vi.fn()} />,
    );
    const confirm = screen.getByTestId("charge-confirm") as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    expect(screen.getByTestId("charge-warning")).toBeInTheDocument();
  });

  it("shows error message when parent passes `error` prop", () => {
    render(
      <ChargeModal
        {...baseProps}
        error="Server says no"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("charge-error")).toHaveTextContent("Server says no");
  });

  it("disables both buttons when isLoading", () => {
    render(
      <ChargeModal
        {...baseProps}
        isLoading
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    const confirm = screen.getByTestId("charge-confirm") as HTMLButtonElement;
    const cancel = screen.getByTestId("charge-cancel") as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);
    expect(cancel.disabled).toBe(true);
    expect(confirm).toHaveTextContent("Charging...");
  });

  it("returns null when open is false", () => {
    const { container } = render(
      <ChargeModal
        {...baseProps}
        open={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
