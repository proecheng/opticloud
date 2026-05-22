import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { type VoucherCardVoucher, VoucherCard } from "./index";

const voucher: VoucherCardVoucher = {
  voucherId: "repro-2026-K7X9P2",
  status: "issued",
  createdAt: "2026-05-22T02:56:27.000Z",
  lockedSolver: "highs",
  lockedModelVersion: {
    provider_id: "scipy",
    name: "linprog",
    version: "1.11.4",
  },
  requestFingerprint: "0123456789abcdef0123456789abcdef0123456789abcdef",
  seedLocked: true,
  seed: null,
};

describe("VoucherCard a11y", () => {
  it("default state has no violations", async () => {
    const { container } = render(<VoucherCard voucher={voucher} canRerun />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("anonymous state has no violations", async () => {
    const { container } = render(
      <VoucherCard voucher={{ ...voucher, anonymous: true }} canRerun />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("rerunning state has no violations", async () => {
    const { container } = render(
      <VoucherCard voucher={voucher} canRerun isRerunning />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("disabled expired state has no violations", async () => {
    const { container } = render(
      <VoucherCard voucher={{ ...voucher, status: "expired" }} canRerun />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
