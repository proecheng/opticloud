"use client";
/** EmptyState (Tier 1). UX Spec Step 12 Empty State pattern. */
import type { ReactNode } from "react";

import { useA11y } from "../../hooks/useA11y";

export interface EmptyStateProps {
  ariaLabel: string;
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ ariaLabel, icon, title, description, action }: EmptyStateProps): JSX.Element {
  const a11y = useA11y({ ariaLabel });
  return (
    <div
      {...a11y.attrs}
      className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background p-12 text-center"
      data-testid="empty-state"
    >
      {icon && (
        <div className="mb-3 text-4xl text-muted-foreground" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="mb-1 text-lg font-medium">{title}</h3>
      {description && <p className="mb-4 max-w-md text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}
