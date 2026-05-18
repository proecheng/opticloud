import type { Meta, StoryObj } from "@storybook/react";

import { LoadingShimmer } from "./index";

const meta = { title: "Tier 1/LoadingShimmer", component: LoadingShimmer, parameters: { layout: "centered" } } satisfies Meta<typeof LoadingShimmer>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Line: Story = { args: { variant: "line" } };
export const Avatar: Story = { args: { variant: "avatar" } };
export const Card: Story = { args: { variant: "card" } };
export const Stack: StoryObj = {
  render: () => (
    <div className="space-y-2" style={{ width: 300 }}>
      <LoadingShimmer variant="line" className="w-24" />
      <LoadingShimmer variant="line" />
      <LoadingShimmer variant="line" className="w-3/4" />
      <LoadingShimmer variant="card" />
    </div>
  ),
};
