/** CodeBlock — copy-paste-ready code surface with 📋 / ✅ 已复制 toggle.
 *
 * Originally lived inline in `algorithms/[k_algo]/page.tsx` (Story 2.2),
 * extended with `label` + `ariaLabel` props in Story 6.A.1 review-patch
 * sweep, extracted here in Story 6.A.2 as the third consumer (academic
 * page BibTeX grid) makes the rule-of-three move worthwhile.
 *
 * The `"use client"` directive is required because the toggle uses
 * `useState` + the Clipboard API. A server component (like /academic
 * page in 6.A.2) can still import this — Next.js App Router renders
 * client children as their own bundle chunk on demand.
 */
"use client";

import { useState } from "react";

export function CodeBlock({
  lang,
  code,
  testId,
  label,
  ariaLabel,
}: {
  lang: "python" | "bash";
  code: string;
  testId: string;
  /** Story 6.A.1 — optional override for the upper-left label (default: Python / cURL). */
  label?: string;
  /** Story 6.A.1 — optional override for the copy-button aria-label. */
  ariaLabel?: string;
}): JSX.Element {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API missing — graceful no-op; user can still select+Ctrl-C
    }
  };

  const computedLabel = label ?? (lang === "python" ? "Python" : "cURL");
  const computedAriaLabel = ariaLabel ?? `复制 ${computedLabel} 代码`;

  return (
    <div className="relative rounded-md border border-border bg-muted/30" data-testid={testId}>
      <div className="flex items-center justify-between border-b border-border px-3 py-1.5">
        <span className="font-mono text-xs uppercase text-muted-foreground">
          {computedLabel}
        </span>
        <button
          type="button"
          onClick={() => void handleCopy()}
          className="min-h-touch rounded px-2 py-1 text-xs text-primary hover:bg-primary/10"
          aria-label={computedAriaLabel}
        >
          {copied ? "✅ 已复制" : "📋 复制"}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 font-mono text-xs leading-relaxed">{code}</pre>
    </div>
  );
}
