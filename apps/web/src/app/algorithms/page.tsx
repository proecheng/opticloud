/** /algorithms — 公开免鉴权 catalog 浏览页 (Story 2.1 + FR C1, C2, C3).
 *
 * Story 2.3 (2026-05-19): 3-button optimization/prediction toggle replaced with
 * per-tier chip group (T1-T6 / P1-P5, multi-toggle); URL `?tier=T1,P2` syncs
 * for shareable filtered views; filter is now server-side via `?tier=` query.
 *
 * Uses `useSearchParams` → must be wrapped in <Suspense> per Next.js 15.
 */
"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import { PublicPageHeader, PublicShell } from "@/components/PublicShell";
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

const OPTIMIZATION_TIERS = ["T1", "T2", "T3", "T4", "T5", "T6"];
const PREDICTION_TIERS = ["P1", "P2", "P3", "P4", "P5"];

function TierChip({
  tier,
  selected,
  onToggle,
}: {
  tier: string;
  selected: boolean;
  onToggle: () => void;
}): JSX.Element {
  const baseColor = TIER_COLOR[tier] ?? "border-border";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      data-testid={`tier-chip-${tier}`}
      className={
        "min-h-touch rounded-md border px-3 py-1 text-sm font-medium transition " +
        baseColor +
        (selected
          ? " ring-2 ring-primary/60 ring-offset-1 ring-offset-background"
          : " opacity-70 hover:opacity-100")
      }
    >
      {tier}
    </button>
  );
}

function AlgorithmsContent(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Hydrate once from URL — empty dep array intentional.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const initialTiers = useMemo(
    () =>
      new Set(
        (searchParams.get("tier") ?? "")
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      ),
    [],
  );

  const [selectedTiers, setSelectedTiers] = useState<Set<string>>(() => new Set(initialTiers));
  const [algos, setAlgos] = useState<Algorithm[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setAlgos(null);
    setError(null);
    void (async () => {
      try {
        const data = await listAlgorithms({ tier: Array.from(selectedTiers) });
        if (!cancelled) setAlgos(data);
      } catch (err) {
        if (!cancelled) setError(String((err as Error).message));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedTiers]);

  useEffect(() => {
    const sorted = Array.from(selectedTiers).sort();
    const next = sorted.length > 0 ? `/algorithms?tier=${sorted.join(",")}` : "/algorithms";
    router.replace(next, { scroll: false });
  }, [selectedTiers, router]);

  const toggleTier = (tier: string): void => {
    setSelectedTiers((prev) => {
      const next = new Set(prev);
      if (next.has(tier)) next.delete(tier);
      else next.add(tier);
      return next;
    });
  };

  const clearTiers = (): void => setSelectedTiers(new Set());
  const loadedCount = algos?.length ?? 0;

  return (
    <PublicShell active="algorithms">
      <PublicPageHeader
        eyebrow="Public catalog"
        title="算法目录"
        description="公开免鉴权浏览当前已发布算法。每个条目保留 tier、任务类型、Provider、版本和外部 provider_url，便于采购、复现和教学评估。"
        actions={
          <>
            <Link
              href="/algorithms/benchmarks"
              className="inline-flex min-h-touch items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              浏览经典算例库
            </Link>
            <Link
              href="/docs/quickstart"
              className="inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600"
            >
              查看 Quickstart
            </Link>
          </>
        }
        meta={
          <>
            <span className="rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground">
              GET /v1/algorithms
            </span>
            <span className="rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground">
              Provider transparent
            </span>
            <span className="rounded-md border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground">
              {selectedTiers.size > 0 ? `${selectedTiers.size} 个 tier 已筛选` : "全部 tier"}
            </span>
          </>
        }
      />

      <section className="border-b border-border bg-background">
        <div className="mx-auto grid max-w-6xl gap-4 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0 space-y-3" aria-label="Tier filters">
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-12 text-xs font-semibold text-muted-foreground">优化</span>
              {OPTIMIZATION_TIERS.map((t) => (
                <TierChip
                  key={t}
                  tier={t}
                  selected={selectedTiers.has(t)}
                  onToggle={() => toggleTier(t)}
                />
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="w-12 text-xs font-semibold text-muted-foreground">预测</span>
              {PREDICTION_TIERS.map((t) => (
                <TierChip
                  key={t}
                  tier={t}
                  selected={selectedTiers.has(t)}
                  onToggle={() => toggleTier(t)}
                />
              ))}
            </div>
          </div>

          <div className="flex min-w-0 flex-wrap items-center gap-3 text-sm text-muted-foreground lg:justify-end">
            {algos && <span>{loadedCount} 个匹配算法</span>}
            {selectedTiers.size > 0 && (
              <button
                type="button"
                onClick={clearTiers}
                data-testid="tier-clear-button"
                className="text-primary hover:underline"
              >
                清除筛选 ({selectedTiers.size})
              </button>
            )}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
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

        {algos && algos.length === 0 && (
          <EmptyState
            ariaLabel="algorithms.empty"
            icon="📂"
            title="此筛选条件暂无算法"
            description="清除筛选看全部，或换一个 tier。"
          />
        )}

        {algos && algos.length > 0 && (
          <ul className="grid gap-4 lg:grid-cols-2">
            {algos.map((algo) => (
              <li
                key={algo.k_algo}
                className="min-w-0 rounded-lg border border-border bg-background p-5"
                data-testid="algorithm-card"
              >
                <Link
                  href={`/algorithms/${algo.k_algo}`}
                  aria-label={`查看 ${algo.k_algo} 详情`}
                  className="block rounded transition hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-primary/40"
                >
                  <div className="flex min-w-0 flex-col gap-4">
                    <div className="min-w-0">
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <code className="break-all font-mono font-semibold">{algo.k_algo}</code>
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
                      <p className="mt-2 text-sm leading-6">{algo.description_zh}</p>
                      <p className="mt-1 text-xs leading-5 text-muted-foreground">
                        {algo.description_en}
                      </p>
                    </div>
                    <div className="text-xs">
                      <span className="inline-flex max-w-full rounded bg-muted px-2 py-1 font-mono">
                        task_type: {algo.task_type}
                      </span>
                    </div>
                  </div>

                  <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 border-t border-border pt-3 text-xs text-muted-foreground">
                    <span className="font-medium">Provider:</span>
                    <code className="break-all font-mono">{algo.model_version.provider_id}</code>
                    <span>·</span>
                    <span>{algo.model_version.kind}</span>
                    <span>·</span>
                    <span>v{algo.model_version.version}</span>
                  </div>
                </Link>

                <div className="mt-2 min-w-0 text-xs">
                  <a
                    href={algo.model_version.provider_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="break-all text-primary hover:underline"
                  >
                    ↗ {algo.model_version.provider_url}
                  </a>
                </div>

                {algo.examples.length > 0 && (
                  <details className="mt-3 min-w-0 rounded bg-muted/50 p-3 text-xs">
                    <summary className="cursor-pointer font-medium">
                      📋 示例输入（{algo.examples[0]?.name}）
                    </summary>
                    <p className="mt-2 text-muted-foreground">
                      {algo.examples[0]?.description}
                    </p>
                    <pre className="mt-2 max-w-full overflow-x-auto rounded bg-background p-2 font-mono">
                      {JSON.stringify(algo.examples[0]?.input, null, 2)}
                    </pre>
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </PublicShell>
  );
}

export default function AlgorithmsPage(): JSX.Element {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background p-8">
          <LoadingShimmer variant="card" />
        </div>
      }
    >
      <AlgorithmsContent />
    </Suspense>
  );
}
