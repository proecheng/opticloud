import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";

import { ConfidenceLabel } from "./index";

describe("ConfidenceLabel", () => {
  it.each([
    { score: 0.95, expectedText: "0.95", tier: "high", zh: "高置信", en: "High confidence" },
    { score: 0.85, expectedText: "0.85", tier: "high", zh: "高置信", en: "High confidence" },
    { score: 0.8499, expectedText: "0.85", tier: "mid", zh: "中置信", en: "Medium confidence" },
    { score: 0.6, expectedText: "0.60", tier: "mid", zh: "中置信", en: "Medium confidence" },
    {
      score: 0.5999,
      expectedText: "0.60",
      tier: "low",
      zh: "低置信请人工 review",
      en: "Low confidence; human review recommended",
    },
  ] as const)("renders CRG14 tier for $score", ({ score, expectedText, tier, zh, en }) => {
    render(
      <ConfidenceLabel
        score={score}
        reasoningZh="Critic 已验证 schema、安全性和业务一致性。"
        reasoningEn="Critic validated schema, safety, and business consistency."
      />,
    );

    const label = screen.getByTestId("confidence-label");
    expect(label).toHaveAttribute("data-tier", tier);
    expect(label).toHaveTextContent(expectedText);
    expect(label).toHaveTextContent(zh);
    expect(label).toHaveAccessibleName(`Confidence: ${expectedText} - ${en}`);
  });

  it.each([
    { locale: "zh-CN", expectedLabel: "高置信", hiddenLabel: "High confidence" },
    { locale: "en-US", expectedLabel: "High confidence", hiddenLabel: "高置信" },
    { locale: "mixed", expectedLabel: "高置信 / High confidence", hiddenLabel: "" },
  ] as const)("renders locale-specific label for $locale", ({ locale, expectedLabel, hiddenLabel }) => {
    render(
      <ConfidenceLabel
        score={0.9}
        locale={locale}
        reasoningZh="Critic 已验证。"
        reasoningEn="Critic validated."
      />,
    );

    const label = screen.getByTestId("confidence-label");
    expect(label).toHaveTextContent(expectedLabel);
    if (hiddenLabel) {
      expect(within(label).queryByText(hiddenLabel)).not.toBeInTheDocument();
    }
  });

  it("keeps bilingual reasoning in a real aria-described element", () => {
    render(
      <ConfidenceLabel
        score={0.72}
        reasoningZh="Critic 置信度中等，建议提交前复核关键约束。"
        reasoningEn="Critic confidence is medium; review key constraints before submitting."
      />,
    );

    const label = screen.getByTestId("confidence-label");
    const describedBy = label.getAttribute("aria-describedby");
    expect(describedBy).toBeTruthy();
    const description = document.getElementById(describedBy ?? "");
    expect(description).not.toBeNull();
    expect(description).toHaveTextContent("Critic 置信度中等");
    expect(description).toHaveTextContent("Critic confidence is medium");
  });

  it("keeps accessible reasoning in compact mode without expanding badge text", () => {
    render(
      <ConfidenceLabel
        compact
        score={0.45}
        reasoningZh="Critic 置信度低，已转人工复核。"
        reasoningEn="Critic confidence is low; this has been routed for human review."
      />,
    );

    const label = screen.getByTestId("confidence-label");
    expect(label).toHaveTextContent("低置信请人工 review");
    expect(label).not.toHaveTextContent("Critic 置信度低");

    const describedBy = label.getAttribute("aria-describedby");
    expect(document.getElementById(describedBy ?? "")).toHaveTextContent("Critic 置信度低");
  });

  it.each([Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY, -0.2, 1.2])(
    "fails closed for invalid score %s",
    (score) => {
      render(<ConfidenceLabel score={score} reasoningZh="复核" reasoningEn="Review" />);

      const label = screen.getByTestId("confidence-label");
      expect(label).toHaveAttribute("data-tier", "low");
      expect(label).toHaveTextContent("0.00");
      expect(label).not.toHaveTextContent("NaN");
      expect(label).not.toHaveTextContent("Infinity");
    },
  );

  it("has no axe violations across high, mid, low, compact, and long reasoning states", async () => {
    const longReasoning =
      "Critic confidence is medium; review key variable bounds, objective direction, and constraint units before submitting this internal beta preview.";
    const { container } = render(
      <div>
        <ConfidenceLabel score={0.95} reasoningZh="高置信。" reasoningEn="High confidence." />
        <ConfidenceLabel score={0.72} reasoningZh="中置信。" reasoningEn={longReasoning} />
        <ConfidenceLabel score={0.45} reasoningZh="低置信。" reasoningEn="Low confidence." />
        <ConfidenceLabel compact score={0.88} reasoningZh="紧凑。" reasoningEn="Compact." />
      </div>,
    );

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});
