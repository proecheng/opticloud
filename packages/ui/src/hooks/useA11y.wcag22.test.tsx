import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useA11y } from "./useA11y";

function Probe(): JSX.Element {
  const a11y = useA11y({
    ariaLabel: "wcag22.probe",
    ariaDescription: "wcag22.description",
    wcag22: {
      focusNotObscured: "minimum",
      consistentHelpId: "global-help",
      draggingAlternative: "file-picker",
    },
  });

  return (
    <div {...a11y.attrs} ref={a11y.ref} data-testid="probe">
      <p id={`${a11y.id}-desc`}>Description</p>
      <button type="button">Focusable</button>
    </div>
  );
}

describe("useA11y WCAG 2.2 readiness", () => {
  it("exposes stable WCAG 2.2 readiness attributes", () => {
    render(<Probe />);

    const probe = screen.getByTestId("probe");
    expect(probe).toHaveAttribute("aria-label", "wcag22.probe");
    expect(probe).toHaveAttribute("aria-describedby");
    expect(probe).toHaveAttribute("data-wcag22-focus-not-obscured", "minimum");
    expect(probe).toHaveAttribute("data-wcag22-consistent-help-id", "global-help");
    expect(probe).toHaveAttribute("data-wcag22-dragging-alternative", "file-picker");
  });

  it("scrolls focused descendants into view when focus-not-obscured readiness is enabled", () => {
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    render(<Probe />);
    screen.getByRole("button", { name: "Focusable" }).focus();

    expect(scrollIntoView).toHaveBeenCalledWith({
      block: "nearest",
      inline: "nearest",
    });
  });
});
