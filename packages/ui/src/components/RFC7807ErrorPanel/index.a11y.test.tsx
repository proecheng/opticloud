import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { RFC7807ErrorPanel, type RFC7807ErrorPayload } from "./index";

const basePayload: RFC7807ErrorPayload = {
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
};

describe("RFC7807ErrorPanel a11y", () => {
  it("402 state has no axe violations", async () => {
    const { container } = render(<RFC7807ErrorPanel payload={basePayload} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("422 multi-field state has no axe violations", async () => {
    const { container } = render(
      <RFC7807ErrorPanel
        payload={{
          title: "Schema Invalid",
          status: 422,
          detail: "请求字段不符合求解模板。",
          errors: [
            {
              field_path: "st.A[2][1]",
              value: "abc",
              constraint: "must be number",
              remediation_hint_key: "errors.422.type_mismatch",
            },
            {
              field_path: "st.b[0]",
              value: -1,
              constraint: "must be >= 0",
              remediation_hint_key: "errors.422.non_negative",
            },
          ],
          next_action_url: "/docs/excel-upload-faq",
        }}
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("429 state has no axe violations", async () => {
    const { container } = render(
      <RFC7807ErrorPanel
        payload={{
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
        }}
        nextActionLabel="升级计划"
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it("unsafe URL without CTA has no axe violations", async () => {
    const { container } = render(
      <RFC7807ErrorPanel
        payload={{
          ...basePayload,
          next_action_url: "javascript:alert(1)",
        }}
      />,
    );
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
