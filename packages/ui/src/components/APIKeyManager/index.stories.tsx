import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { APIKeyManager } from "./index";

const meta = { title: "Tier 1/APIKeyManager", component: APIKeyManager, parameters: { layout: "centered" } } satisfies Meta<typeof APIKeyManager>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Empty: Story = { args: { keys: [], onCreate: fn() } };

export const TypicalUser: Story = {
  args: {
    onCreate: fn(),
    onRevoke: fn(),
    keys: [
      { id: "k1", prefix: "sk-AB3", label: "Production", scope: ["optimize:write", "billing:read"], createdAt: "2026-05-10T08:00:00Z" },
      { id: "k2", prefix: "sk-XY9", label: "Local dev", scope: ["optimize:read"], createdAt: "2026-05-15T14:32:00Z" },
      { id: "k3", prefix: "sk-Z01", label: "Old test", scope: ["optimize:read"], createdAt: "2026-04-01T10:00:00Z", revokedAt: "2026-05-01T10:00:00Z" },
    ],
  },
};

/** Story 1.1b J1 Vertical Slice — 注册成功 modal scenario. */
export const NewKeyReveal: Story = {
  args: {
    onCreate: fn(),
    onRevoke: fn(),
    newKeyValue: "sk-AB3_eyJlcnJvcl9rZXkiOiJ0ZXN0LXRlc3QtYXJjaC1rZXktOTk5OS1leUpsXMP",
    keys: [
      { id: "k1", prefix: "sk-AB3", label: "First Key", scope: ["optimize:write"], createdAt: "2026-05-17T09:00:00Z" },
    ],
  },
};
