import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { VoucherCard, type VoucherCardVoucher } from "./index";

const baseVoucher: VoucherCardVoucher = {
  voucherId: "repro-2026-K7X9P2",
  status: "issued",
  createdAt: "2026-05-22T02:56:27.000Z",
  expiresAt: "2031-05-22T02:56:27.000Z",
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

const meta = {
  title: "Tier 3/VoucherCard",
  component: VoucherCard,
  parameters: { layout: "padded" },
  args: {
    voucher: baseVoucher,
    canRerun: true,
    onRerun: fn(),
    onCopyVoucherId: fn(),
  },
} satisfies Meta<typeof VoucherCard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const AnonymousBlindReview: Story = {
  args: {
    voucher: { ...baseVoucher, anonymous: true },
  },
};

export const ChildRerun: Story = {
  args: {
    voucher: {
      ...baseVoucher,
      status: "rerun_child",
      voucherId: "repro-2026-M4N8Q1",
      rerunOfVoucherId: "repro-2026-K7X9P2",
      sourceOptimizationId: "11111111-1111-1111-1111-111111111111",
    },
    rerunResult: {
      childVoucherId: "repro-2026-M4N8Q1",
      rerunOfVoucherId: "repro-2026-K7X9P2",
      sourceOptimizationId: "11111111-1111-1111-1111-111111111111",
    },
  },
};

export const Rerunning: Story = {
  args: { isRerunning: true },
};

export const ExpiredDisabled: Story = {
  args: {
    voucher: { ...baseVoucher, status: "expired" },
    canRerun: false,
  },
};

export const WithError: Story = {
  args: {
    rerunError: "voucher expired after 5 years",
  },
};
