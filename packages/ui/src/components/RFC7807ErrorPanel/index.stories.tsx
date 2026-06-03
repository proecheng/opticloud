import type { Meta, StoryObj } from "@storybook/react";

import { RFC7807ErrorPanel } from "./index";

const meta = {
  title: "Tier 2/RFC7807ErrorPanel",
  component: RFC7807ErrorPanel,
  parameters: { layout: "centered" },
} satisfies Meta<typeof RFC7807ErrorPanel>;

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
      instance: "/v1/optimizations",
      request_id: "req_xyz789",
      trace_id: "trc_abc456",
      next_action_url: "https://console.opticloud.cn/topup?suggested_amount=10",
    },
    remediationMessages: {
      "errors.402.topup": "加油包 ¥10 后重试",
    },
  },
};

export const SchemaInvalid422: Story = {
  args: {
    payload: {
      title: "Schema Invalid",
      status: 422,
      detail: "请求字段不符合求解模板。",
      errors: [
        {
          field_path: "st.b[0]",
          value: -1,
          constraint: "must be >= 0",
          remediation_hint_key: "errors.422.non_negative",
        },
        {
          field_path: "st.A[2][1]",
          value: "abc",
          constraint: "must be number",
          remediation_hint_key: "errors.422.type_mismatch",
        },
      ],
      next_action_url: "/docs/excel-upload-faq",
    },
    remediationMessages: {
      "errors.422.non_negative": "把该单元格改成非负数",
      "errors.422.type_mismatch": "检查模板列类型后重新上传",
    },
  },
};

export const RateLimit429: Story = {
  args: {
    payload: {
      title: "Rate Limit Exceeded",
      status: 429,
      detail: "Free 用户请求超过 3 RPS。",
      errors: [
        {
          field_path: "rate_limit",
          value: "3/s",
          constraint: "free plan limit exceeded",
          remediation_hint_key: "errors.429.rate_limit_exceeded",
        },
      ],
      next_action_url: "https://console.opticloud.cn/billing/plans",
    },
    nextActionLabel: "升级计划",
  },
};

export const LongFieldAndMetadata: Story = {
  args: {
    payload: {
      type: "https://api.opticloud.cn/errors/very-long-validation-error-name-that-wraps",
      title: "Validation Error",
      status: 422,
      detail:
        "字段路径和约束非常长时，面板需要保持可扫描、可换行，并避免把 CTA 挤压到不可读状态。",
      errors: [
        {
          field_path:
            "payload.jobs[12].constraints.vehicle_routes[3].time_windows[17].latest_arrival_seconds",
          value: "x".repeat(180),
          constraint:
            "must be smaller than depot closing time and greater than earliest_arrival_seconds",
          remediation_hint_key:
            "errors.422.time_window_latest_arrival_must_be_after_earliest",
        },
      ],
      instance: "/v1/optimizations/demo/very-long-instance-path-with-query?task_type=vrptw",
      request_id: "req_very_long_identifier_abcdefghijklmnopqrstuvwxyz0123456789",
      trace_id: "trc_very_long_identifier_abcdefghijklmnopqrstuvwxyz0123456789",
      next_action_url: "/docs/excel-upload-faq",
    },
  },
};

export const MissingNextAction: Story = {
  args: {
    payload: {
      title: "Not Found",
      status: 404,
      detail: "未找到指定资源。",
      errors: [],
      trace_id: "trc_missing_action",
    },
  },
};

export const UnsafeUrlRejected: Story = {
  args: {
    payload: {
      title: "Unsafe URL",
      status: 400,
      detail: "next_action_url 使用了不允许的 URL scheme。",
      errors: [
        {
          field_path: "next_action_url",
          value: "javascript:alert(1)",
          constraint: "must be safe recovery URL",
          remediation_hint_key: "errors.400.unsafe_next_action_url",
        },
      ],
      next_action_url: "javascript:alert(1)",
    },
  },
};
