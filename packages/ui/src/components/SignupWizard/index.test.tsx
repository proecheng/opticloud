import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SignupWizard, type SignupWizardStep } from "./index";

const steps: SignupWizardStep[] = [
  { id: "signup", label: "注册", state: "completed" },
  { id: "verify", label: "验证", state: "current" },
  { id: "api-key", label: "拿 API Key", state: "pending" },
  { id: "postman", label: "Postman 导入", state: "pending" },
  { id: "hello-world", label: "Hello World 跑通", state: "pending" },
];

describe("SignupWizard", () => {
  it("renders a five-step progress model", () => {
    render(<SignupWizard steps={steps} ariaLabel="onboarding.wizard" />);

    expect(screen.getByTestId("signup-wizard")).toBeInTheDocument();
    expect(screen.getAllByTestId("signup-wizard-step")).toHaveLength(5);
    expect(screen.getByText("验证")).toBeInTheDocument();
    expect(screen.getByText("当前步骤")).toBeInTheDocument();
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });

  it("marks skipped steps without losing completed progress", () => {
    render(
      <SignupWizard
        steps={[
          steps[0]!,
          { id: "verify", label: "验证", state: "skipped" },
          steps[2]!,
          steps[3]!,
          steps[4]!,
        ]}
        ariaLabel="onboarding.wizard"
      />,
    );

    expect(screen.getByText("已跳过")).toBeInTheDocument();
    expect(screen.getByText("已完成")).toBeInTheDocument();
  });

  it("fires skip and resume actions", () => {
    const onSkip = vi.fn();
    const onResume = vi.fn();
    render(
      <SignupWizard
        steps={steps}
        ariaLabel="onboarding.wizard"
        onSkip={onSkip}
        onResume={onResume}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "跳过引导" }));
    fireEvent.click(screen.getByRole("button", { name: "继续引导" }));

    expect(onSkip).toHaveBeenCalledOnce();
    expect(onResume).toHaveBeenCalledOnce();
  });

  it("shows proactive support banner state", () => {
    render(
      <SignupWizard
        steps={steps}
        ariaLabel="onboarding.wizard"
        supportPrompt={{
          visible: true,
          title: "还没跑通？",
          description: "继续引导或稍后再试。",
          actionLabel: "继续",
          onAction: vi.fn(),
          secondaryAction: {
            label: "打开 quickstart",
            href: "/docs/quickstart",
          },
          dismissLabel: "稍后",
          onDismiss: vi.fn(),
        }}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("还没跑通？");
    expect(screen.getByRole("link", { name: "打开 quickstart" })).toHaveAttribute(
      "href",
      "/docs/quickstart",
    );
  });
});
