/** /algorithms/[k_algo] — 算法详情页 (Story 2.2, FR C2).
 *
 * 公开免鉴权 — fetches GET /v1/algorithms/{k_algo}; renders header + Python/cURL
 * snippets (synthesized from examples[0].input) + Provider 透明 + try-it-now CTA.
 *
 * 404 path: shows StatusCard + 返回算法目录 link.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import { AttributionBadge, attributionLine } from "@/components/AttributionBadge";
import { CodeBlock } from "@/components/CodeBlock";
import {
  type Algorithm,
  OptiCloudClientError,
  getAlgorithm,
} from "@/lib/api";

const TIER_COLOR: Record<string, string> = {
  T1: "bg-success/10 text-success border-success/30",
  T2: "bg-success/10 text-success border-success/30",
  T3: "bg-primary/10 text-primary border-primary/30",
  T4: "bg-primary/10 text-primary border-primary/30",
  T5: "bg-warning/10 text-warning border-warning/30",
  T6: "bg-danger/10 text-danger border-danger/30",
  P1: "bg-success/10 text-success border-success/30",
  P2: "bg-primary/10 text-primary border-primary/30",
  P3: "bg-primary/10 text-primary border-primary/30",
  P4: "bg-warning/10 text-warning border-warning/30",
  P5: "bg-danger/10 text-danger border-danger/30",
};

const STATUS_LABEL: Record<string, string> = {
  v1: "✅ v1 上线",
  v1_late: "🟡 v1 末",
  v2: "⏳ v2",
  audited: "✅ 已审核",
  shadow: "🔍 灰度",
};

const PLACEHOLDER_INPUT: Record<string, unknown> = {
  task_type: "lp",
  minimize: { c: [1] },
  st: { A: [[1]], b: [1] },
};

function buildPythonSnippet(algo: Algorithm, exampleInput: Record<string, unknown>): string {
  const json = JSON.stringify(exampleInput, null, 4).replace(/\n/g, "\n    ");
  return `import os
import requests

API_KEY = os.getenv("OPTICLOUD_API_KEY", "sk-...")
BASE_URL = os.getenv("OPTICLOUD_BASE_URL", "https://api.opticloud.cn")

# ${algo.description_zh}
resp = requests.post(
    f"{BASE_URL}/v1/optimizations",
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Idempotency-Key": "demo-001",  # change per call (P23)
    },
    json=${json},
    timeout=60,
)
resp.raise_for_status()
print(resp.json())
`;
}

function buildCurlSnippet(exampleInput: Record<string, unknown>): string {
  const json = JSON.stringify(exampleInput);
  return `curl -X POST https://api.opticloud.cn/v1/optimizations \\
  -H "Authorization: Bearer \${OPTICLOUD_API_KEY:-sk-...}" \\
  -H "Content-Type: application/json" \\
  -H "Idempotency-Key: demo-001" \\
  -d '${json}'
`;
}

export default function AlgorithmDetailPage(): JSX.Element {
  const params = useParams<{ k_algo: string }>();
  const kAlgoRaw = params?.k_algo;
  const kAlgo = Array.isArray(kAlgoRaw) ? kAlgoRaw[0] : kAlgoRaw;

  const [algo, setAlgo] = useState<Algorithm | null>(null);
  const [error, setError] = useState<{ kind: "not-found" | "other"; message: string } | null>(
    null,
  );

  useEffect(() => {
    if (!kAlgo) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await getAlgorithm(kAlgo);
        if (!cancelled) setAlgo(data);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof OptiCloudClientError && err.status === 404) {
          setError({ kind: "not-found", message: err.detail });
        } else {
          setError({ kind: "other", message: String((err as Error).message) });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [kAlgo]);

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              ← 算法目录
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              注册
            </Link>
          </nav>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-8">
        {error?.kind === "not-found" && (
          <div data-testid="algorithm-detail-404">
            <StatusCard
              variant="error"
              title={`未知算法：${kAlgo ?? ""}`}
              description={error.message}
              ariaLabel="algorithm.detail.not_found"
            />
            <div className="mt-4 text-center">
              <Link href="/algorithms" className="text-primary hover:underline">
                ← 返回算法目录
              </Link>
            </div>
          </div>
        )}

        {error?.kind === "other" && (
          <StatusCard
            variant="error"
            title="加载算法详情失败"
            description={error.message}
            ariaLabel="algorithm.detail.error"
          />
        )}

        {!error && algo === null && (
          <div className="space-y-3">
            <LoadingShimmer variant="card" />
            <LoadingShimmer variant="card" />
            <LoadingShimmer variant="card" />
          </div>
        )}

        {algo && !error && (
          <article className="space-y-8">
            <header data-testid="algorithm-detail-header">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="font-mono text-2xl font-bold">{algo.k_algo}</h1>
                <span
                  className={
                    "rounded-md border px-2 py-0.5 text-xs font-medium " +
                    (TIER_COLOR[algo.tier] ?? "border-border")
                  }
                >
                  {algo.tier}
                </span>
                <span className="text-xs text-muted-foreground">
                  {STATUS_LABEL[algo.status] ?? algo.status}
                </span>
                <span className="rounded bg-muted px-2 py-1 font-mono text-xs">
                  task_type: {algo.task_type}
                </span>
                <AttributionBadge attribution={algo.ip_attribution} />
              </div>
              <p className="mt-3 text-base">{algo.description_zh}</p>
              <p className="mt-1 text-sm text-muted-foreground">{algo.description_en}</p>

              <div className="mt-4 flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 p-3 text-xs">
                <span className="font-medium text-muted-foreground">Provider:</span>
                <code className="font-mono">{algo.model_version.provider_id}</code>
                <span className="text-muted-foreground">·</span>
                <span>{algo.model_version.kind}</span>
                <span className="text-muted-foreground">·</span>
                <span>v{algo.model_version.version}</span>
                <span className="text-muted-foreground">·</span>
                <a
                  href={algo.model_version.provider_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  ↗ {algo.model_version.provider_url}
                </a>
              </div>
            </header>

            <section
              data-testid="ip-attribution-block"
              aria-labelledby="ip-attribution-heading"
              className="rounded-lg border border-border bg-muted/30 p-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h2 id="ip-attribution-heading" className="text-lg font-semibold">
                  IP Attribution
                </h2>
                <AttributionBadge attribution={algo.ip_attribution} />
              </div>
              <p className="mt-2 text-sm" data-testid="ip-attribution-line">
                {attributionLine(algo.ip_attribution)}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {algo.ip_attribution.summary_zh}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Contract anchor:{" "}
                <code className="font-mono">{algo.ip_attribution.contract_anchor}</code>
              </p>
            </section>

            <section>
              <h2 className="mb-3 text-lg font-semibold">Try it now</h2>
              {algo.examples.length > 0 ? (
                <>
                  <p className="mb-3 text-sm text-muted-foreground">
                    示例：<strong>{algo.examples[0].name}</strong> —{" "}
                    {algo.examples[0].description}
                  </p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <CodeBlock
                      lang="python"
                      code={buildPythonSnippet(
                        algo,
                        algo.examples[0].input as Record<string, unknown>,
                      )}
                      testId="snippet-python"
                    />
                    <CodeBlock
                      lang="bash"
                      code={buildCurlSnippet(algo.examples[0].input as Record<string, unknown>)}
                      testId="snippet-curl"
                    />
                  </div>
                </>
              ) : (
                <div data-testid="snippet-placeholder">
                  <p className="mb-3 text-sm text-warning">
                    ⚠ 示例载荷待补充（M2 内补齐其余 7 个 SKU）—
                    以下是基于 task_type 的占位载荷，结构仅供参考。
                  </p>
                  <div className="grid gap-4 md:grid-cols-2">
                    <CodeBlock
                      lang="python"
                      code={buildPythonSnippet(algo, {
                        ...PLACEHOLDER_INPUT,
                        task_type: algo.task_type,
                      })}
                      testId="snippet-python"
                    />
                    <CodeBlock
                      lang="bash"
                      code={buildCurlSnippet({
                        ...PLACEHOLDER_INPUT,
                        task_type: algo.task_type,
                      })}
                      testId="snippet-curl"
                    />
                  </div>
                </div>
              )}
            </section>

            {algo.citation && (
              <section data-testid="citation-block" aria-labelledby="citation-heading">
                <h2
                  id="citation-heading"
                  className="mb-2 text-lg font-semibold"
                >
                  📚 引用本算法
                </h2>
                <p className="mb-3 text-sm text-muted-foreground">
                  <span data-testid="citation-authors">{algo.citation.authors_label_zh}</span>
                  <span className="px-1">·</span>
                  <span>{algo.citation.venue}</span>
                  <span className="px-1">·</span>
                  <span>{algo.citation.year}</span>
                </p>
                {algo.citation.doi && (
                  <p className="mb-3 text-sm">
                    DOI:{" "}
                    <a
                      href={encodeURI(`https://doi.org/${algo.citation.doi}`)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                      data-testid="citation-doi"
                    >
                      {algo.citation.doi}
                    </a>
                  </p>
                )}
                {!algo.citation.doi && algo.citation.url && (
                  <p className="mb-3 text-sm">
                    <a
                      href={encodeURI(algo.citation.url)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                      data-testid="citation-url"
                    >
                      ↗ 查看出处
                    </a>
                  </p>
                )}
                <CodeBlock
                  lang="bash"
                  code={algo.citation.bibtex}
                  testId="citation-bibtex"
                  label="BibTeX"
                  ariaLabel="复制 BibTeX 代码"
                />
              </section>
            )}

            <section>
              <h2 className="mb-3 text-lg font-semibold">Example input JSON</h2>
              {algo.examples.length > 0 ? (
                <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
                  {JSON.stringify(algo.examples[0].input, null, 2)}
                </pre>
              ) : (
                <EmptyState
                  ariaLabel="algorithm.detail.examples_empty"
                  icon="📋"
                  title="示例输入即将上线（M2）"
                  description="后续 PR 会为本 SKU 补齐至少 1 个 example."
                />
              )}
            </section>

            <section className="flex flex-wrap gap-3 border-t border-border pt-6">
              <Link
                href="/auth/signup"
                className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
              >
                3 分钟注册拿 API Key
              </Link>
              {algo.task_type === "lp" && (
                <Link
                  href="/demo/charge"
                  className="min-h-touch rounded-md border border-border px-4 py-2 text-foreground hover:bg-muted"
                >
                  免登录试跑 ChargeModal (J1 路径)
                </Link>
              )}
            </section>
          </article>
        )}
      </section>
    </main>
  );
}
