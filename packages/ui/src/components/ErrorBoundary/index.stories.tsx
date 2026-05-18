import type { Meta, StoryObj } from "@storybook/react";

import { ErrorBoundary, RFC7807Panel } from "./index";

const meta = { title: "Tier 1/ErrorBoundary", component: RFC7807Panel, parameters: { layout: "centered" } } satisfies Meta<typeof RFC7807Panel>;
export default meta;
type Story = StoryObj<typeof meta>;

export const InsufficientCredits402: Story = {
  args: {
    payload: {
      type: "https://api.opticloud.cn/errors/insufficient_credits",
      title: "Insufficient Credits",
      status: 402,
      detail: "余额不足。当前 50 Credits，本次预估消耗 605 Credits。",
      errors: [
        {
          field_path: "options.max_solve_seconds",
          value: 600,
          constraint: "estimated_credits > balance",
          remediation_hint_key: "errors.402.topup",
        },
      ],
      next_action_url: "https://console.opticloud.cn/topup?suggested_amount=10",
      request_id: "req_xyz789",
      trace_id: "trc_abc456",
    },
  },
};

export const InvalidLP422: Story = {
  args: {
    payload: {
      title: "Validation Error",
      status: 422,
      detail: "LP constraint violation in st.b",
      errors: [
        { field_path: "st.b[0]", value: -1, constraint: "must be >= 0", remediation_hint_key: "errors.422.non_negative" },
        { field_path: "st.A[2][1]", value: "abc", constraint: "must be number", remediation_hint_key: "errors.422.type_mismatch" },
      ],
      trace_id: "trc_xyz",
    },
  },
};

export const FallbackOnError: StoryObj<typeof ErrorBoundary> = {
  render: () => {
    function Bomb(): JSX.Element {
      throw new Error("Boom! React component crashed.");
    }
    return (
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    );
  },
};
