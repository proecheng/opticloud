"use client";
/** APIKeyManager (Tier 1). FR A2 + CRG12 (api_key mask + Reveal toggle + Copy 单独 + warning). */
import { useState } from "react";

import { useA11y } from "../../hooks/useA11y";
import { cn } from "../../lib/cn";

export interface APIKey {
  id: string;
  prefix: string;
  label: string;
  scope: string[];
  createdAt: string;
  expiresAt?: string;
  revokedAt?: string;
}

export interface APIKeyManagerProps {
  keys: APIKey[];
  /** Show full key (returned ONCE on creation — CRG12 mask + reveal). */
  newKeyValue?: string;
  onRevoke?: (id: string) => void;
  onCreate?: () => void;
  ariaLabel?: string;
}

export function APIKeyManager({
  keys,
  newKeyValue,
  onRevoke,
  onCreate,
  ariaLabel = "api_keys.manager",
}: APIKeyManagerProps): JSX.Element {
  const [revealed, setRevealed] = useState(false);
  const a11y = useA11y({ ariaLabel });

  return (
    <div {...a11y.attrs} className="rounded-lg border border-border bg-background p-4" data-testid="api-key-manager">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold">API Keys</h3>
        {onCreate && (
          <button
            type="button"
            onClick={onCreate}
            className="min-h-touch rounded-md bg-primary px-3 py-1 text-sm text-primary-foreground hover:bg-primary-600"
          >
            + 新建 API Key
          </button>
        )}
      </div>

      {/* CRG12: api_key mask + Reveal toggle (5s auto-hide in production) */}
      {newKeyValue && (
        <div
          className="mb-4 rounded border-l-4 border-primary bg-primary/5 p-3 text-sm"
          data-testid="new-key-banner"
        >
          <div className="mb-2 font-medium text-primary">⚠️ 新 API Key（仅显示一次，请立即复制）</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded bg-background px-2 py-1 font-mono text-xs">
              {revealed ? newKeyValue : `${newKeyValue.slice(0, 6)}_${"•".repeat(36)}`}
            </code>
            <button
              type="button"
              onClick={() => setRevealed(!revealed)}
              className="min-h-touch rounded border border-border px-2 py-1 text-xs hover:bg-muted"
              aria-label="api_key.toggle_reveal"
            >
              {revealed ? "隐藏" : "显示"}
            </button>
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard.writeText(newKeyValue);
              }}
              className="min-h-touch rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary-600"
              aria-label="api_key.copy"
            >
              复制
            </button>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            ⚠️ 请勿截图分享 / API Key 等同密码 (CRG12)
          </p>
        </div>
      )}

      <ul className="space-y-2">
        {keys.length === 0 && <li className="text-sm text-muted-foreground">暂无 API Key</li>}
        {keys.map((k) => (
          <li
            key={k.id}
            className={cn(
              "flex items-center justify-between rounded border border-border bg-muted px-3 py-2 text-sm",
              k.revokedAt && "opacity-50",
            )}
          >
            <div className="flex-1">
              <div className="font-medium">{k.label}</div>
              <div className="font-mono text-xs text-muted-foreground">
                {k.prefix}_••• ({k.scope.join(", ") || "no scopes"})
              </div>
            </div>
            {!k.revokedAt && onRevoke && (
              <button
                type="button"
                onClick={() => onRevoke(k.id)}
                className="min-h-touch rounded border border-danger px-2 py-1 text-xs text-danger hover:bg-danger/10"
                aria-label={`revoke_api_key_${k.id}`}
              >
                吊销
              </button>
            )}
            {k.revokedAt && <span className="text-xs text-muted-foreground">已吊销</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}
