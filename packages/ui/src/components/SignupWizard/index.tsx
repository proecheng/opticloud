"use client";

import {
  CheckCircle2,
  Circle,
  HelpCircle,
  PlayCircle,
  SkipForward,
} from "lucide-react";
import type { ReactNode } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type SignupWizardStepState = "completed" | "current" | "pending" | "skipped";

export interface SignupWizardStep {
  id: string;
  label: string;
  state: SignupWizardStepState;
  description?: string;
}

export interface SignupWizardSupportPrompt {
  visible: boolean;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryAction?: {
    label: string;
    href: string;
  };
  dismissLabel?: string;
  onDismiss?: () => void;
}

export interface SignupWizardProps {
  steps: SignupWizardStep[];
  ariaLabel: string;
  title?: ReactNode;
  description?: ReactNode;
  onSkip?: () => void;
  onResume?: () => void;
  supportPrompt?: SignupWizardSupportPrompt;
  className?: string;
}

const stateText: Record<SignupWizardStepState, string> = {
  completed: "已完成",
  current: "当前步骤",
  pending: "待完成",
  skipped: "已跳过",
};

const stateStyles: Record<SignupWizardStepState, string> = {
  completed: "border-success/40 bg-success/5 text-success",
  current: "border-primary/50 bg-primary/5 text-primary",
  pending: "border-border bg-background text-muted-foreground",
  skipped: "border-warning/50 bg-warning/5 text-warning",
};

function StepIcon({ state }: { state: SignupWizardStepState }): JSX.Element {
  const className = "h-4 w-4 shrink-0";
  if (state === "completed") return <CheckCircle2 className={className} />;
  if (state === "current") return <PlayCircle className={className} />;
  if (state === "skipped") return <SkipForward className={className} />;
  return <Circle className={className} />;
}

export function SignupWizard({
  steps,
  ariaLabel,
  title = "Onboarding",
  description,
  onSkip,
  onResume,
  supportPrompt,
  className,
}: SignupWizardProps): JSX.Element {
  const a11y = useA11y({ ariaLabel });

  return (
    <section
      {...a11y.attrs}
      className={cn(
        "rounded-lg border border-border bg-background p-4 shadow-sm",
        className,
      )}
      data-testid="signup-wizard"
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-base font-semibold">{title}</h2>
          {description && (
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              {description}
            </p>
          )}
        </div>
        {(onSkip || onResume) && (
          <div className="flex shrink-0 flex-wrap gap-2">
            {onResume && (
              <button
                type="button"
                onClick={onResume}
                className="min-h-touch rounded-md border border-primary px-3 py-1.5 text-sm text-primary hover:bg-primary/5"
              >
                继续引导
              </button>
            )}
            {onSkip && (
              <button
                type="button"
                onClick={onSkip}
                className="min-h-touch rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted"
              >
                跳过引导
              </button>
            )}
          </div>
        )}
      </div>

      <ol className="mt-4 grid gap-2 md:grid-cols-5">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={cn("rounded-md border p-3 text-sm", stateStyles[step.state])}
            data-testid="signup-wizard-step"
            data-state={step.state}
          >
            <div className="flex items-center gap-2">
              <StepIcon state={step.state} />
              <span className="text-xs font-medium text-muted-foreground">
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate font-medium">{step.label}</span>
            </div>
            <p className="mt-2 text-xs">{stateText[step.state]}</p>
            {step.description && (
              <p className="mt-1 text-xs text-muted-foreground">{step.description}</p>
            )}
          </li>
        ))}
      </ol>

      {supportPrompt?.visible && (
        <div
          role="status"
          aria-live="polite"
          className="mt-4 rounded-md border border-warning/50 bg-warning/10 p-3 text-sm text-warning"
          data-testid="signup-wizard-support"
        >
          <div className="flex gap-2">
            <HelpCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-medium">{supportPrompt.title}</p>
              {supportPrompt.description && (
                <p className="mt-1 text-xs">{supportPrompt.description}</p>
              )}
              {(supportPrompt.onAction ||
                supportPrompt.secondaryAction ||
                supportPrompt.onDismiss) && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {supportPrompt.onAction && (
                    <button
                      type="button"
                      onClick={supportPrompt.onAction}
                      className="min-h-touch rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground hover:bg-primary-600"
                    >
                      {supportPrompt.actionLabel ?? "继续"}
                    </button>
                  )}
                  {supportPrompt.secondaryAction && (
                    <a
                      href={supportPrompt.secondaryAction.href}
                      className="inline-flex min-h-touch items-center rounded-md border border-primary px-3 py-1.5 text-xs text-primary hover:bg-primary/5"
                    >
                      {supportPrompt.secondaryAction.label}
                    </a>
                  )}
                  {supportPrompt.onDismiss && (
                    <button
                      type="button"
                      onClick={supportPrompt.onDismiss}
                      className="min-h-touch rounded-md border border-warning/50 px-3 py-1.5 text-xs hover:bg-warning/10"
                    >
                      {supportPrompt.dismissLabel ?? "稍后"}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
