"use client";
/** StatusCard (Tier 1). Generic status display — used for Status Page (FR O1), Plan badge, etc. */
import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export type StatusVariant = "ok" | "warning" | "error" | "info";

export interface StatusCardProps {
  variant: StatusVariant;
  title: string;
  description?: string;
  ariaLabel: string;
  icon?: React.ReactNode;
}

const variantStyles: Record<StatusVariant, string> = {
  ok: "border-success text-success bg-success/5",
  warning: "border-warning text-warning bg-warning/5",
  error: "border-danger text-danger bg-danger/5",
  info: "border-primary text-primary bg-primary/5",
};

export function StatusCard(props: StatusCardProps): JSX.Element {
  const a11y = useA11y({ ariaLabel: props.ariaLabel, role: "status" });
  return (
    <div
      {...a11y.attrs}
      className={cn(
        "flex items-start gap-3 rounded-md border-l-4 p-4",
        variantStyles[props.variant],
      )}
      data-testid="status-card"
      data-variant={props.variant}
    >
      {props.icon && <span aria-hidden="true">{props.icon}</span>}
      <div>
        <h3 className="font-semibold">{props.title}</h3>
        {props.description && <p className="mt-1 text-sm">{props.description}</p>}
      </div>
    </div>
  );
}
