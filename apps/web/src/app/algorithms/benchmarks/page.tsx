/** /algorithms/benchmarks — public classic benchmark library browse page.
 *
 * Story 8.C.4: static App Router page beside /algorithms, not under [k_algo].
 */
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { CapabilityCard, EmptyState, LoadingShimmer, StatusCard } from "@opticloud/ui";

import {
  type BenchmarkImportResponse,
  type BenchmarkLibraryItem,
  importBenchmarkLibraryItem,
  listBenchmarkLibrary,
} from "@/lib/api";

const SUITES = ["", "ieee", "cvrplib", "or-lib", "m5", "uci", "nab"] as const;
const DOMAINS = ["", "power", "routing", "linear-programming", "forecast"] as const;
const TASK_TYPES = ["", "lp", "forecast"] as const;

const SUITE_LABEL: Record<string, string> = {
  ieee: "IEEE",
  cvrplib: "CVRPLIB",
  "or-lib": "OR-Lib",
  m5: "M5",
  uci: "UCI",
  nab: "NAB",
};

function benchmarkJson(payload: BenchmarkImportResponse | null): string {
  return payload ? JSON.stringify(payload.request_payload, null, 2) : "";
}

function FilterSelect({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label htmlFor={id} className="grid gap-1 text-sm">
      <span className="font-medium text-muted-foreground">{label}</span>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="min-h-touch rounded-md border border-border bg-background px-3 py-2 text-sm"
      >
        {options.map((option) => (
          <option key={option || "all"} value={option}>
            {option ? (SUITE_LABEL[option] ?? option) : "全部"}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function BenchmarkLibraryPage(): JSX.Element {
  const [suite, setSuite] = useState("");
  const [domain, setDomain] = useState("");
  const [taskType, setTaskType] = useState("");
  const [items, setItems] = useState<BenchmarkLibraryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importPayload, setImportPayload] = useState<BenchmarkImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importingId, setImportingId] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      suite: suite || undefined,
      domain: domain || undefined,
      taskType: taskType || undefined,
    }),
    [suite, domain, taskType],
  );

  useEffect(() => {
    let cancelled = false;
    setItems(null);
    setError(null);
    void (async () => {
      try {
        const data = await listBenchmarkLibrary(filters);
        if (!cancelled) setItems(data);
      } catch (err) {
        if (!cancelled) setError(String((err as Error).message));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filters]);

  const handleImport = async (benchmarkId: string): Promise<void> => {
    setImportingId(benchmarkId);
    setImportError(null);
    try {
      const payload = await importBenchmarkLibraryItem(benchmarkId);
      setImportPayload(payload);
    } catch (err) {
      setImportError(String((err as Error).message));
    } finally {
      setImportingId(null);
    }
  };

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              算法目录
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

      <section className="bg-muted py-10">
        <div className="mx-auto max-w-6xl px-6">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold">经典算例库</h1>
              <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
                IEEE/CVRPLIB/OR-Lib/M5/UCI/NAB 公开 benchmark 模板，import payload
                为最小模板；50% Credits 为资格展示，实际账单以后端 finalize 为准。
              </p>
            </div>
            <Link
              href="/algorithms"
              className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-background"
            >
              返回算法目录
            </Link>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-3">
            <FilterSelect
              id="suite-filter"
              label="Suite"
              value={suite}
              options={SUITES}
              onChange={setSuite}
            />
            <FilterSelect
              id="domain-filter"
              label="Domain"
              value={domain}
              options={DOMAINS}
              onChange={setDomain}
            />
            <FilterSelect
              id="task-filter"
              label="Task"
              value={taskType}
              options={TASK_TYPES}
              onChange={setTaskType}
            />
          </div>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_420px]">
        <div>
          {error && (
            <StatusCard
              variant="error"
              title="加载经典算例库失败"
              description={error}
              ariaLabel="benchmark-library.error"
            />
          )}

          {items === null && !error && (
            <div className="space-y-3">
              <LoadingShimmer variant="card" />
              <LoadingShimmer variant="card" />
              <LoadingShimmer variant="card" />
            </div>
          )}

          {items && items.length === 0 && (
            <EmptyState
              ariaLabel="benchmark-library.empty"
              icon=""
              title="暂无匹配 benchmark"
              description="调整 suite、domain 或 task 筛选。"
            />
          )}

          {items && items.length > 0 && (
            <ul className="grid gap-3" data-testid="benchmark-card-list">
              {items.map((item) => (
                <li key={item.benchmark_id} data-testid="benchmark-card">
                  <CapabilityCard
                    capability={item}
                    isImporting={importingId === item.benchmark_id}
                    onImport={handleImport}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <aside className="lg:sticky lg:top-4 lg:self-start">
          <section
            aria-label="import payload"
            className="rounded-lg border border-border bg-background p-5"
          >
            <h2 className="text-lg font-semibold">Import Payload</h2>
            {importError && (
              <p className="mt-3 rounded-md border border-danger/30 bg-danger/10 p-3 text-sm text-danger">
                {importError}
              </p>
            )}
            {!importPayload && !importError && (
              <p className="mt-3 text-sm text-muted-foreground">
                选择任一 benchmark 后显示目标 endpoint 和 JSON payload。
              </p>
            )}
            {importPayload && (
              <div className="mt-4 space-y-3" data-testid="benchmark-import-panel">
                <div className="rounded-md bg-muted p-3 text-sm">
                  <div className="text-xs font-medium text-muted-foreground">Target Endpoint</div>
                  <code>{importPayload.target_endpoint}</code>
                </div>
                <div className="rounded-md bg-muted p-3 text-sm">
                  <div className="text-xs font-medium text-muted-foreground">Discount</div>
                  <p>
                    {importPayload.discount.label_zh} · multiplier=
                    {importPayload.discount.discount_multiplier}
                  </p>
                  {!importPayload.discount.billing_supported && (
                    <p className="mt-1 text-warning">
                      预测模板可导入；本 story 未实现 prediction billing discount。
                    </p>
                  )}
                </div>
                <pre className="max-h-[520px] overflow-auto rounded-md border border-border bg-muted/40 p-3 font-mono text-xs">
                  {benchmarkJson(importPayload)}
                </pre>
                <p className="text-xs text-muted-foreground">{importPayload.disclaimer_zh}</p>
              </div>
            )}
          </section>
        </aside>
      </section>
    </main>
  );
}
