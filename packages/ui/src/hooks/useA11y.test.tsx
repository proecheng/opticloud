/** Tests for useA11y Hook (Story 0.12). */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { useA11y } from "./useA11y";

function TestComponent(props: {
  ariaLabel: string;
  trapFocus?: boolean;
  onEscape?: () => void;
}) {
  const a11y = useA11y({
    ariaLabel: props.ariaLabel,
    trapFocus: props.trapFocus,
    escapeToClose: props.onEscape,
  });
  return (
    <div {...a11y.attrs} ref={a11y.ref}>
      <button type="button">First</button>
      <button type="button">Last</button>
    </div>
  );
}

describe("useA11y", () => {
  it("sets aria-label attribute", () => {
    render(<TestComponent ariaLabel="modal.confirm" />);
    const el = screen.getByLabelText("modal.confirm");
    expect(el).toBeInTheDocument();
  });

  it("generates stable id for ARIA linking", () => {
    render(<TestComponent ariaLabel="t1" />);
    const el = screen.getByLabelText("t1");
    expect(el.id).toMatch(/.+/); // useId produces non-empty
  });

  it("fires escapeToClose on ESC key", async () => {
    const onEscape = vi.fn();
    const user = userEvent.setup();
    render(<TestComponent ariaLabel="t1" onEscape={onEscape} />);
    await user.keyboard("{Escape}");
    expect(onEscape).toHaveBeenCalledOnce();
  });

  it("warns in dev when aria-label missing", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    function MissingLabel() {
      // @ts-expect-error intentional: testing missing required prop
      const a11y = useA11y({ ariaLabel: "" });
      return <div {...a11y.attrs} ref={a11y.ref} />;
    }
    render(<MissingLabel />);
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });
});
