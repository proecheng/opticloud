import Link from "next/link";

import { StatusCard } from "@opticloud/ui";

import { AttributionBadge, attributionLine } from "@/components/AttributionBadge";
import type { Algorithm, Citation, IPAttribution } from "@/lib/api";

export const metadata = {
  title: "Academic Attribution Console — OptiCloud",
  description: "Read-only academic IP attribution tier review surface.",
};

export const dynamic = "force-dynamic";

function normalizeSolverBase(rawBase: string): string {
  try {
    const url = new URL(rawBase);
    if (url.hostname === "localhost") {
      url.hostname = "127.0.0.1";
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return rawBase.replace(/\/$/, "");
  }
}

const SOLVER_BASE = normalizeSolverBase(
  process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL ?? "http://localhost:8002",
);

async function getAlgorithms(): Promise<Algorithm[]> {
  const res = await fetch(`${SOLVER_BASE}/v1/algorithms`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`upstream ${res.status}`);
  return res.json() as Promise<Algorithm[]>;
}

function citationKey(citation: Citation | null): string {
  if (!citation?.bibtex) return "N/A";
  const firstLine = citation.bibtex.split("\n", 1)[0] ?? "";
  const match = /^@\w+\{([^,]+),/.exec(firstLine);
  return match?.[1] ?? "N/A";
}

function citationSource(citation: Citation | null): string {
  if (!citation) return "N/A";
  if (citation.doi) return `doi:${citation.doi}`;
  if (citation.url) return citation.url;
  return `${citation.venue} · ${citation.year}`;
}

function countByTier(algorithms: Algorithm[]): Record<IPAttribution["tier"], number> {
  return algorithms.reduce(
    (acc, algo) => {
      acc[algo.ip_attribution.tier] += 1;
      return acc;
    },
    { L1: 0, L2: 0, L3: 0 },
  );
}

function CountTile({
  tier,
  count,
}: {
  tier: IPAttribution["tier"];
  count: number;
}): JSX.Element {
  const labels: Record<IPAttribution["tier"], string> = {
    L1: "Full Visible",
    L2: "Standard BibTeX",
    L3: "License-Only",
  };
  return (
    <div
      className="rounded-lg border border-border bg-background p-4"
      data-testid={`attribution-count-${tier}`}
    >
      <div className="flex items-center justify-between gap-2">
        <AttributionBadge
          attribution={{
            tier,
            label_zh: labels[tier],
            display_name_zh: labels[tier],
            summary_zh: labels[tier],
            visibility:
              tier === "L1" ? "full_visible" : tier === "L2" ? "bibtex" : "license_only",
            contract_anchor: "",
          }}
        />
        <span className="font-mono text-2xl font-bold">{count}</span>
      </div>
      <div className="mt-2 text-sm text-muted-foreground">{labels[tier]}</div>
    </div>
  );
}

export default async function AcademicAttributionConsolePage(): Promise<JSX.Element> {
  let algorithms: Algorithm[] = [];
  let fetchError: string | null = null;
  try {
    algorithms = await getAlgorithms();
  } catch (err) {
    fetchError = (err as Error).message;
  }

  const counts = countByTier(algorithms);

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/academic" className="text-muted-foreground hover:text-foreground">
              学术合作
            </Link>
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              算法目录
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted py-8">
        <div className="mx-auto max-w-6xl px-6">
          <h1 className="text-2xl font-bold">Academic Attribution Review</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Catalog-controlled L1 / L2 / L3 attribution state for academic Provider and
            license review.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-8">
        {fetchError && (
          <StatusCard
            variant="error"
            title="Attribution catalog unavailable"
            description={fetchError}
            ariaLabel="console.academic_attribution.error"
          />
        )}

        {!fetchError && algorithms.length === 0 && (
          <StatusCard
            variant="warning"
            title="No attribution rows"
            description="Catalog returned no algorithms."
            ariaLabel="console.academic_attribution.empty"
          />
        )}

        {!fetchError && algorithms.length > 0 && (
          <>
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <CountTile tier="L1" count={counts.L1} />
              <CountTile tier="L2" count={counts.L2} />
              <CountTile tier="L3" count={counts.L3} />
            </div>

            <div className="mt-6 overflow-x-auto rounded-lg border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Algorithm</th>
                    <th className="px-4 py-3">Attribution</th>
                    <th className="px-4 py-3">Provider</th>
                    <th className="px-4 py-3">Citation</th>
                    <th className="px-4 py-3">Contract Anchor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-background">
                  {algorithms.map((algo) => (
                    <tr key={algo.k_algo} data-testid={`attribution-row-${algo.k_algo}`}>
                      <td className="px-4 py-3 align-top">
                        <Link
                          href={`/algorithms/${algo.k_algo}`}
                          className="font-mono font-semibold text-primary hover:underline"
                        >
                          {algo.k_algo}
                        </Link>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {algo.task_type} · {algo.tier}
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <div className="flex flex-col gap-2">
                          <AttributionBadge attribution={algo.ip_attribution} />
                          <span className="max-w-xs text-xs text-muted-foreground">
                            {attributionLine(algo.ip_attribution)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <code className="font-mono">{algo.model_version.provider_id}</code>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {algo.model_version.kind} · v{algo.model_version.version}
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <code className="font-mono text-xs">{citationKey(algo.citation)}</code>
                        <div className="mt-1 max-w-xs break-all text-xs text-muted-foreground">
                          {citationSource(algo.citation)}
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top">
                        <code className="font-mono text-xs">
                          {algo.ip_attribution.contract_anchor}
                        </code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
