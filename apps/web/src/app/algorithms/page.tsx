/** /algorithms — 公开免鉴权 catalog 浏览页（Story 2.1 + FR C1, C2, C3）.
 *
 * 演示 OptiCloud 支持的算法清单，便于销售 demo / 学界 / 投资人查看。
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import { Algorithm, listAlgorithms } from "@/lib/api";

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

export default function AlgorithmsPage(): JSX.Element {
  const [algos, setAlgos] = useState<Algorithm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    void (async () => {
      try {
        const data = await listAlgorithms();
        setAlgos(data);
      } catch (err) {
        setError(String((err as Error).message));
      }
    })();
  }, []);

  const filtered =
    algos === null
      ? null
      : filter === "all"
        ? algos
        : algos.filter((a) =>
            filter === "optimization"
              ? a.tier.startsWith("T")
              : a.tier.startsWith("P"),
          );

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/" className="text-muted-foreground hover:text-foreground">
              首页
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

      <section className="bg-muted py-12">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <h1 className="text-balance text-3xl font-bold">算法目录</h1>
          <p className="mt-2 text-balance text-muted-foreground">
            公开免鉴权 — `GET /v1/algorithms`（FR C1）·{" "}
            <span className="font-mono">
              {algos === null ? "..." : `${algos.length} 个算法`}
            </span>{" "}
            · Provider 全透明（含 provider_url）
          </p>

          <div className="mt-4 inline-flex rounded-md border border-border bg-background p-1">
            {[
              { v: "all", label: "全部" },
              { v: "optimization", label: "优化 (T1-T6)" },
              { v: "prediction", label: "预测 (P1-P5)" },
            ].map((tab) => (
              <button
                key={tab.v}
                type="button"
                onClick={() => setFilter(tab.v)}
                className={
                  "min-h-touch rounded px-4 py-1 text-sm " +
                  (filter === tab.v
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted")
                }
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 py-8">
        {error && (
          <StatusCard
            variant="error"
            title="加载算法目录失败"
            description={error}
            ariaLabel="algorithms.error"
          />
        )}

        {algos === null && !error && (
          <div className="space-y-3">
            <LoadingShimmer variant="card" />
            <LoadingShimmer variant="card" />
            <LoadingShimmer variant="card" />
          </div>
        )}

        {filtered && filtered.length === 0 && (
          <EmptyState
            ariaLabel="algorithms.empty"
            icon="📂"
            title="此分类暂无算法"
            description="切换 Tab 看更多。"
          />
        )}

        {filtered && filtered.length > 0 && (
          <ul className="space-y-3">
            {filtered.map((algo) => (
              <li
                key={algo.k_algo}
                className="rounded-lg border border-border bg-background p-5"
                data-testid="algorithm-card"
              >
                <Link
                  href={`/algorithms/${algo.k_algo}`}
                  aria-label={`查看 ${algo.k_algo} 详情`}
                  className="block rounded transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <code className="font-mono font-semibold">
                          {algo.k_algo}
                        </code>
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
                        <span className="ml-auto text-xs text-primary">详情 →</span>
                      </div>
                      <p className="mt-2 text-sm">{algo.description_zh}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {algo.description_en}
                      </p>
                    </div>
                    <div className="text-right text-xs">
                      <span className="rounded bg-muted px-2 py-1 font-mono">
                        task_type: {algo.task_type}
                      </span>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
                    <span className="font-medium">Provider:</span>
                    <code className="font-mono">{algo.model_version.provider_id}</code>
                    <span>·</span>
                    <span>{algo.model_version.kind}</span>
                    <span>·</span>
                    <span>v{algo.model_version.version}</span>
                  </div>
                </Link>

                {/* Provider URL link kept outside the card-Link so users can click through to the source without navigating away. */}
                <div className="mt-2 text-xs">
                  <a
                    href={algo.model_version.provider_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    ↗ {algo.model_version.provider_url}
                  </a>
                </div>

                {algo.examples.length > 0 && (
                  <details className="mt-3 rounded bg-muted/50 p-3 text-xs">
                    <summary className="cursor-pointer font-medium">
                      📋 示例输入（{algo.examples[0]?.name}）
                    </summary>
                    <p className="mt-2 text-muted-foreground">
                      {algo.examples[0]?.description}
                    </p>
                    <pre className="mt-2 overflow-x-auto rounded bg-background p-2 font-mono">
                      {JSON.stringify(algo.examples[0]?.input, null, 2)}
                    </pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="mt-12 border-t border-border bg-background py-6 text-center text-sm text-muted-foreground">
        <p>
          想试跑？{" "}
          <Link href="/auth/signup" className="text-primary hover:underline">
            3 分钟注册拿 API Key
          </Link>{" "}
          · 免费 200 Credits
        </p>
      </footer>
    </main>
  );
}
