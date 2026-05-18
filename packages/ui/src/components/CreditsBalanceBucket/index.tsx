"use client";
/** CreditsBalanceBucket (Tier 1). FR B1 — 余额按桶 (月度/注册/教育/加油包). */
import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface CreditsBucket {
  name: string;
  /** zh-CN label (i18n). */
  labelZh: string;
  balance: number;
  /** Optional expires_at hint (e.g. "永不过期" for top-up, FR B9). */
  expiresHint?: string;
}

export interface CreditsBalanceBucketProps {
  buckets: CreditsBucket[];
  ariaLabel?: string;
}

export function CreditsBalanceBucket({
  buckets,
  ariaLabel = "credits.balance",
}: CreditsBalanceBucketProps): JSX.Element {
  const total = buckets.reduce((sum, b) => sum + b.balance, 0);
  const a11y = useA11y({
    ariaLabel,
    ariaDescription: `Total ${total} Credits across ${buckets.length} buckets`,
  });

  return (
    <div
      {...a11y.attrs}
      className="rounded-lg border border-border bg-background p-4"
      data-testid="credits-balance-bucket"
    >
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">Credits 余额</h3>
        <span className="font-mono text-2xl font-semibold text-primary">{total}</span>
      </div>
      <ul className="space-y-2">
        {buckets.map((b) => (
          <li
            key={b.name}
            className={cn(
              "flex items-center justify-between rounded border-l-2 border-primary/30 bg-muted px-3 py-2 text-sm",
            )}
          >
            <span>
              <span className="font-medium">{b.labelZh}</span>
              {b.expiresHint && (
                <span className="ml-2 text-xs text-muted-foreground">({b.expiresHint})</span>
              )}
            </span>
            <span className="font-mono">{b.balance}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
