import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RFC7807ErrorPanel } from "./index";

describe("RFC7807ErrorPanel", () => {
  it("renders 402 detail, field remediation, metadata, and a safe next_action_url CTA", () => {
    render(
      <RFC7807ErrorPanel
        payload={{
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
        }}
        remediationMessages={{ "errors.402.topup": "加油包 ¥10 后重试" }}
        nextActionLabel=" "
      />,
    );

    expect(screen.getByRole("alert")).toHaveAttribute("aria-live", "assertive");
    expect(screen.getByText("[402] Insufficient Credits")).toBeInTheDocument();
    expect(screen.getByText("余额不足。当前 50 Credits，本次预估消耗 605 Credits。")).toBeInTheDocument();
    expect(screen.getByText("options.max_solve_seconds")).toBeInTheDocument();
    expect(screen.getByText("estimated_credits > balance")).toBeInTheDocument();
    expect(screen.getByText("加油包 ¥10 后重试")).toBeInTheDocument();
    expect(screen.getByText("value: 600")).toBeInTheDocument();
    expect(screen.getByText("request: req_xyz789")).toBeInTheDocument();
    expect(screen.getByText("trace: trc_abc456")).toBeInTheDocument();
    expect(screen.getByText("type: https://api.opticloud.cn/errors/insufficient_credits")).toBeInTheDocument();
    expect(screen.getByText("instance: /v1/optimizations")).toBeInTheDocument();

    const cta = screen.getByRole("link", { name: "下一步操作" });
    expect(cta).toHaveAttribute(
      "href",
      "https://console.opticloud.cn/topup?suggested_amount=10",
    );
  });

  it("renders 422 multiple field errors with mapped and fallback remediation while preserving 0 and false values", () => {
    render(
      <RFC7807ErrorPanel
        payload={{
          title: "Schema Invalid",
          status: 422,
          detail: "请求字段不符合求解模板。",
          errors: [
            {
              field_path: "st.A[2][1]",
              value: 0,
              constraint: "must be positive",
              remediation_hint_key: "errors.422.positive",
            },
            {
              field_path: "options.reproducible",
              value: false,
              constraint: "must be true for anonymous voucher",
              remediation_hint_key: "errors.422.reproducible_required",
            },
          ],
        }}
        remediationMessages={{ "errors.422.positive": "把该单元格改成正数" }}
      />,
    );

    expect(screen.getByText("st.A[2][1]")).toBeInTheDocument();
    expect(screen.getByText("value: 0")).toBeInTheDocument();
    expect(screen.getByText("把该单元格改成正数")).toBeInTheDocument();
    expect(screen.getByText("options.reproducible")).toBeInTheDocument();
    expect(screen.getByText("value: false")).toBeInTheDocument();
    expect(screen.getByText("errors.422.reproducible_required")).toBeInTheDocument();
    expect(screen.queryByText("undefined")).not.toBeInTheDocument();
  });

  it("rejects unsafe next_action_url and never renders legacy next_action", () => {
    render(
      <RFC7807ErrorPanel
        payload={
          {
            title: "Unsafe URL",
            status: 429,
            detail: "请求过于频繁。",
            errors: [
              {
                field_path: "rate_limit",
                value: "3/s",
                constraint: "free plan limit exceeded",
                remediation_hint_key: "errors.429.rate_limit_exceeded",
              },
            ],
            next_action_url: "javascript:alert(1)",
            next_action: "https://console.opticloud.cn/billing/plans",
          } as never
        }
      />,
    );

    expect(screen.queryByRole("link", { name: "下一步操作" })).not.toBeInTheDocument();
    expect(screen.queryByText("https://console.opticloud.cn/billing/plans")).not.toBeInTheDocument();
  });

  it("redacts sensitive values and truncates long previews", () => {
    render(
      <RFC7807ErrorPanel
        payload={{
          title: "Validation Error",
          status: 400,
          detail: "请求字段错误。",
          instance: "/v1/optimizations?authorization=Bearer sk-secret-token-abcdefghijklmnopqrstuvwxyz",
          errors: [
            {
              field_path: "headers.Authorization",
              value: "Bearer sk-secret-token-abcdefghijklmnopqrstuvwxyz",
              constraint: "must not be submitted in body",
              remediation_hint_key: "errors.400.auth_header",
            },
            {
              field_path: "body.description",
              value: "x".repeat(240),
              constraint: "must be shorter",
              remediation_hint_key: "errors.400.too_long",
            },
            {
              field_path: "body.raw",
              value: { provider_payload: "do-not-render" },
              constraint: "must be primitive",
              remediation_hint_key: "errors.400.primitive",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("value: 已隐藏敏感值")).toBeInTheDocument();
    expect(screen.getByText("instance: 已隐藏敏感值")).toBeInTheDocument();
    expect(screen.queryByText(/sk-secret-token/)).not.toBeInTheDocument();
    expect(screen.getByText(/value: x{80,}.../)).toBeInTheDocument();
    expect(screen.queryByText(/x{180,}/)).not.toBeInTheDocument();
    expect(screen.getByText("value: 复杂值已隐藏")).toBeInTheDocument();
    expect(screen.queryByText(/do-not-render/)).not.toBeInTheDocument();
  });
});
