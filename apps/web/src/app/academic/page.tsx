/** /academic — BibTeX 营销 milestone Landing 页 (Story 6.A.2, Epic 6.A).
 *
 * Server component (SSR): fetches the algorithm catalog at request time so
 * crawlers + JS-disabled scholars see every citation.bibtex in the initial
 * HTML. Innovation #3 学界变现飞轮 marketing surface — consumes the citation
 * field shipped by Story 6.A.1.
 */
import Link from "next/link";

import { StatusCard } from "@opticloud/ui";

import { AttributionBadge, attributionLine } from "@/components/AttributionBadge";
import { CodeBlock } from "@/components/CodeBlock";
import type { Algorithm } from "@/lib/api";

export const metadata = {
  title: "学术合作 — OptiCloud",
  description:
    "已发布算法自带 BibTeX 引用 — 公开 SKU、3 个学派、1976→2025 的学术血统全公开。学者用 .edu / .ac.cn 邮箱注册永久免费 ¥2,000 Starter / 月。",
};

// Render per-request (still SSR — crawler-friendly) rather than freezing a
// build-time prerender: the build runs before solver-orchestrator is
// guaranteed up, which would otherwise bake the graceful-degrade fallback
// into a static page. The fetch below keeps a 5-min data cache for
// thundering-herd protection.
export const dynamic = "force-dynamic";

// This fetch runs server-side (Node.js), where `localhost` resolves to ::1
// (IPv6) first. The backend services bind 0.0.0.0 (IPv4 only), so a Node
// `fetch("http://localhost:...")` is refused. Normalize to 127.0.0.1 — the
// same IPv4-explicit workaround e2e.yml documents for its readiness probes.
// (The browser-side client in lib/api.ts keeps `localhost`: the browser/OS
// resolver handles it fine; only Node's resolver has the ::1 preference.)
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

async function getAlgorithms(): Promise<Algorithm[]> {
  const res = await fetch(`${SOLVER_BASE}/v1/algorithms`, {
    next: { revalidate: 300 },
  });
  if (!res.ok) throw new Error(`upstream ${res.status}`);
  return res.json() as Promise<Algorithm[]>;
}

function FlywheelCard({
  step,
  title,
  body,
  source,
  className = "",
}: {
  step: number;
  title: string;
  body: string;
  source: string;
  className?: string;
}): JSX.Element {
  return (
    <div
      data-testid={`flywheel-step-${step}`}
      aria-describedby="flywheel-explainer"
      className={`rounded-lg border border-border bg-background p-5 ${className}`}
    >
      <div className="text-xs font-semibold text-primary">第 {step} 步</div>
      <div className="mt-1 font-semibold">{title}</div>
      <p className="mt-2 text-sm text-muted-foreground">{body}</p>
      <p className="mt-2 text-xs text-muted-foreground">{source}</p>
    </div>
  );
}

function CitationCard({ algo }: { algo: Algorithm }): JSX.Element {
  const { citation } = algo;
  const attribution = algo.ip_attribution;
  return (
    <article
      data-testid={`citation-card-${algo.k_algo}`}
      className="rounded-lg border border-border bg-background p-5"
    >
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="font-mono text-base font-bold">{algo.k_algo}</h3>
        <span
          className={
            "rounded-md border px-2 py-0.5 text-xs font-medium " +
            (TIER_COLOR[algo.tier] ?? "border-border")
          }
        >
          {algo.tier}
        </span>
        <AttributionBadge attribution={attribution} />
      </header>
      <p className="mt-1 text-sm text-muted-foreground">{algo.description_zh}</p>
      <p
        className="mt-2 text-sm text-muted-foreground"
        data-testid={`attribution-line-${algo.k_algo}`}
      >
        {attributionLine(attribution)}
      </p>

      {citation ? (
        <>
          <p className="mt-3 text-sm" data-testid="citation-authors-line">
            <span>{citation.authors_label_zh}</span>
            <span className="px-1">·</span>
            <span>{citation.venue}</span>
            <span className="px-1">·</span>
            <span>{citation.year}</span>
          </p>
          {citation.doi && (
            <p className="mt-1 text-sm">
              DOI:{" "}
              <a
                href={encodeURI(`https://doi.org/${citation.doi}`)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
                data-testid={`doi-${algo.k_algo}`}
              >
                {citation.doi}
              </a>
            </p>
          )}
          {!citation.doi && citation.url && (
            <p className="mt-1 text-sm">
              <a
                href={encodeURI(citation.url)}
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary hover:underline"
                data-testid={`url-${algo.k_algo}`}
              >
                ↗ {citation.url}
              </a>
            </p>
          )}
          <div className="mt-3">
            <CodeBlock
              lang="bash"
              code={citation.bibtex}
              label="BibTeX"
              ariaLabel={`复制 ${algo.k_algo} 的 BibTeX 代码`}
              testId={`bibtex-${algo.k_algo}`}
            />
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          该 SKU 暂无引用 (commercial-only)
        </p>
      )}

      <Link
        href={`/algorithms/${algo.k_algo}`}
        className="mt-3 inline-block text-sm text-primary hover:underline"
      >
        → 查看算法详情
      </Link>
    </article>
  );
}

export default async function AcademicPage(): Promise<JSX.Element> {
  let algorithms: Algorithm[] = [];
  let fetchFailed = false;
  try {
    algorithms = await getAlgorithms();
  } catch {
    fetchFailed = true;
  }

  return (
    <main className="flex min-h-screen flex-col">
      {/* Header — mirrors landing page */}
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-primary" />
            <span className="text-lg font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/algorithms"
              className="text-muted-foreground hover:text-foreground"
            >
              算法目录
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              立即注册
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="bg-background py-20" aria-labelledby="academic-hero-heading">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <h1
            id="academic-hero-heading"
            className="text-balance text-4xl font-bold leading-tight md:text-5xl"
          >
            开放优化与预测，让学术研究可复现、可引用、可被发现
          </h1>
          <p className="mt-3 text-balance text-xl text-muted-foreground md:text-2xl">
            已发布算法都自带 BibTeX 引用 — 公开 SKU、3 个学派、1976 → 2025 的学术血统全公开
          </p>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-muted-foreground">
            Apache 2.0 自研 + 顶刊算法 + 商用产品的混合栈，提交一次任务 = 拿到结果 +
            当下最新的 <code className="font-mono text-sm">citation.bibtex</code>。
            学生 / 博士 / 教师永久免费 ¥2,000 Starter / 月。
          </p>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 md:flex-row">
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-6 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600"
            >
              🎓 用 .edu / .ac.cn 邮箱注册
            </Link>
            <Link
              href="#citations"
              className="min-h-touch rounded-md border border-border px-6 py-3 font-medium hover:bg-muted"
            >
              ↓ 跳到引用列表
            </Link>
          </div>
        </div>
      </section>

      {/* Flywheel */}
      <section
        className="border-t border-border bg-muted py-16"
        aria-labelledby="flywheel-heading"
      >
        <div className="mx-auto max-w-4xl px-6">
          <h2 id="flywheel-heading" className="text-balance text-2xl font-semibold">
            学界变现飞轮 (Innovation #3)
          </h2>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            <FlywheelCard
              step={1}
              title="学者免费"
              body=".edu / .ac.cn 邮箱注册自动激活教育版，永久 ¥2,000 Starter / 月。"
              source="Story 1.4"
            />
            <FlywheelCard
              step={2}
              title="学者发论文"
              body="提交任务即拿到 citation.bibtex，一行 paste 进论文 References。"
              source="Story 6.A.1"
            />

            <div
              aria-hidden="true"
              className="hidden text-center text-2xl font-semibold text-primary md:col-span-2 md:flex md:items-center md:justify-between md:px-8"
            >
              <span>↑</span>
              <span>↓</span>
            </div>

            <FlywheelCard
              step={3}
              title="论文带来新学者"
              body="引用图谱上每多一个指向我们的节点，就有更多学者看见 OptiCloud。"
              source="Story 6.A.3 自动追踪"
              className="md:col-start-2 md:row-start-3"
            />
            <FlywheelCard
              step={4}
              title="飞轮转起来"
              body="更多学者上车 → 更多论文 → 更多引用，自我强化。"
              source="Innovation #3"
              className="md:col-start-1 md:row-start-3"
            />
          </div>
          <p
            id="flywheel-explainer"
            className="mt-6 text-balance text-sm text-muted-foreground"
          >
            Innovation #3 的关键不是"我们最快"，而是"用了 OptiCloud 的研究天然会传播"。
            学者每次发论文 paste 一行{" "}
            <code className="font-mono">@software&#123;aqgs2025opticloud, ...&#125;</code>
            ，就等于在 ArXiv / Semantic Scholar 的引用图谱上多一个指向我们的节点。
            Story 6.A.3 在引用追踪上线后，每条新引用都会自动转成一张 Linear 卡片提醒平台团队。
          </p>
        </div>
      </section>

      {/* Citations */}
      <section
        id="citations"
        className="scroll-mt-8 bg-background py-16"
        aria-labelledby="citations-heading"
      >
        <div className="mx-auto max-w-5xl px-6">
          <h2 id="citations-heading" className="text-balance text-2xl font-semibold">
            引用 {algorithms.length > 0 ? algorithms.length : ""} 个算法
          </h2>
          {fetchFailed ? (
            <div className="mt-6">
              <StatusCard
                variant="warning"
                title="引用列表暂时不可用"
                description="请稍后重试，或直接访问算法目录浏览全部算法。"
                ariaLabel="academic.citations.unavailable"
              />
              <Link
                href="/algorithms"
                className="mt-3 inline-block text-sm text-primary hover:underline"
              >
                → 前往 /algorithms
              </Link>
            </div>
          ) : (
            <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
              {algorithms.map((algo) => (
                <CitationCard key={algo.k_algo} algo={algo} />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Edu-tier CTA */}
      <section
        id="edu-tier-cta"
        className="border-t border-border bg-primary/5 py-16"
        aria-labelledby="edu-cta-heading"
      >
        <div className="mx-auto max-w-2xl px-6 text-center">
          <h2 id="edu-cta-heading" className="text-balance text-3xl font-bold">
            用 .edu / .ac.cn 邮箱注册，永久免费 ¥2,000 Starter / 月
          </h2>
          <p className="mt-4 text-balance text-muted-foreground">
            注册时自动检测邮箱后缀，立即激活 edu_tier。不需要发邮件，不需要审核，不需要绑卡。
          </p>
          <Link
            href="/auth/signup"
            data-testid="edu-cta-signup"
            className="mt-8 inline-block min-h-touch rounded-md bg-primary px-6 py-3 font-semibold text-primary-foreground hover:bg-primary-600"
          >
            🎓 立即注册 →
          </Link>
          <p className="mt-4 text-sm text-muted-foreground">
            非学界邮箱也欢迎用免费层 (¥6 / 月起)；学界优惠仅是首选。
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-border bg-background py-6 text-center text-sm text-muted-foreground">
        <p>
          OptiCloud · Epic 6.A BibTeX Academic ·{" "}
          <Link href="/algorithms" className="text-primary hover:underline">
            浏览全部算法
          </Link>
        </p>
      </footer>
    </main>
  );
}
