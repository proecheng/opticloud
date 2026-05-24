import type { Meta, StoryObj } from "@storybook/react";
import { fn } from "@storybook/test";

import { SignupWizard } from "./index";

const meta = {
  title: "Tier 2/SignupWizard",
  component: SignupWizard,
  parameters: { layout: "padded" },
  args: {
    ariaLabel: "onboarding.wizard",
    title: "5 步跑通 Hello World",
    description: "注册、验证、拿 Key、导入 Postman、跑通第一个 LP。",
    onSkip: fn(),
    onResume: fn(),
  },
} satisfies Meta<typeof SignupWizard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const InProgress: Story = {
  args: {
    steps: [
      { id: "signup", label: "注册", state: "completed" },
      { id: "verify", label: "验证", state: "completed" },
      { id: "api-key", label: "拿 API Key", state: "current" },
      { id: "postman", label: "Postman 导入", state: "pending" },
      { id: "hello-world", label: "Hello World 跑通", state: "pending" },
    ],
  },
};

export const Completed: Story = {
  args: {
    steps: [
      { id: "signup", label: "注册", state: "completed" },
      { id: "verify", label: "验证", state: "completed" },
      { id: "api-key", label: "拿 API Key", state: "completed" },
      { id: "postman", label: "Postman 导入", state: "completed" },
      { id: "hello-world", label: "Hello World 跑通", state: "completed" },
    ],
  },
};

export const SupportPrompt: Story = {
  args: {
    steps: [
      { id: "signup", label: "注册", state: "completed" },
      { id: "verify", label: "验证", state: "completed" },
      { id: "api-key", label: "拿 API Key", state: "completed" },
      { id: "postman", label: "Postman 导入", state: "skipped" },
      { id: "hello-world", label: "Hello World 跑通", state: "current" },
    ],
    supportPrompt: {
      visible: true,
      title: "还没跑通？",
      description: "继续引导、打开 quickstart，或稍后再试。",
      actionLabel: "继续引导",
      onAction: fn(),
      secondaryAction: {
        label: "打开 quickstart",
        href: "/docs/quickstart",
      },
      dismissLabel: "稍后",
      onDismiss: fn(),
    },
  },
};
