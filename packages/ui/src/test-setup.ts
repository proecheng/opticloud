import "@testing-library/jest-dom/vitest";
import { toHaveNoViolations } from "jest-axe";
import { expect } from "vitest";

// jest-axe matcher for vitest (Story 0.12 + UX-DR5)
expect.extend(toHaveNoViolations as unknown as Parameters<typeof expect.extend>[0]);

declare module "vitest" {
  interface Assertion {
    toHaveNoViolations(): void;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
