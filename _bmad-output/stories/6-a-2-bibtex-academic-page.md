---
story_key: 6-a-2-bibtex-academic-page
epic_num: 6.A
epic_name: Reproducibility — BibTeX Academic v1 必上 (M3)
story_num: 6.A.2
status: review
priority: 🟢 High (Innovation #3 学界变现飞轮第二根支柱; 6.A.1 citation field now needs a surface that scholars actually find; pure FE)
sizing: S–M (~2-3 hours; new SSR-friendly route + 1 component extraction + reuse 6.A.1 catalog API + 1 Playwright spec; no backend / no schema / no migration)
type: implementation
created_by: bmad-create-story
created_at: 2026-05-20
sources:
  - _bmad-output/planning/epics.md L1741-1743 (Story 6.A.2 spec — Landing 页 + Innovation #3 学界飞轮介绍)
  - _bmad-output/planning/epics.md L480-485 (Epic 6.A goal — Innovation #3 学界变现飞轮基础)
  - _bmad-output/planning/architecture.md L3115 (Innovation #3 学界变现 strengths summary)
  - _bmad-output/planning/architecture.md L3036 (academic-provider-handbook.md placeholder note)
  - _bmad-output/stories/6-a-1-citation-bibtex.md (PR #29 just-shipped citation field — this story consumes its output)
  - apps/web/src/app/page.tsx (Landing page pattern — Header + Hero + sections + Footer; SSR-friendly)
  - apps/web/src/app/algorithms/[k_algo]/page.tsx L50-89 (private CodeBlock component — extract to shared)
  - apps/web/src/app/algorithms/[k_algo]/page.tsx L260-302 (citation block JSX pattern to mirror)
  - apps/web/src/lib/api.ts L60-180 (listAlgorithms + Citation TS interface — already in place from 6.A.1)
  - apps/web/src/app/algorithms/page.tsx (per-tier chip filter — pattern for algorithm-grid layout)
  - _bmad-output/stories/1-4-edu-tier-email-whitelist.md (FR A4 — .edu/.ac.cn = ¥2000 Starter; CTA wording must align with what signup actually does)
  - e2e/tests/algorithm-citation.spec.ts (6.A.1 just-shipped Playwright pattern to mirror)
dependencies:
  upstream:
    - 6-a-1-citation-bibtex (done, PR #29) — Citation TS interface + Citation field on all 8 catalog rows + DOI link pattern
    - 2-1-j1-algorithms-public-list (done) — `GET /v1/algorithms` exists and is auth-free
    - 1-4-edu-tier-email-whitelist (done) — the .edu / .ac.cn → edu_tier=true flow this page advertises
  downstream:
    - 6-a-3-citation-tracking — TT6 Semantic Scholar / Google Scholar scrape; consumes the same bibtex keys this page renders
    - 6-a-4-academic-onboarding-toolkit (RE2-2) — Provider Onboarding Tier 1 toolkit may embed an `<iframe>` of /academic or copy sections
    - 6-a-5-ip-attribution-tiers (E5) — Tier 1/2/3 IP attribution badges live on this same surface in v2
    - 8-c-8-algorithm-provenance-page (E10) — per-SKU provenance page references /academic from its footer
non-goals:
  - Citation tracking dashboard (Story 6.A.3 owns the Semantic Scholar / Linear ticket flow)
  - /academic 学者招商 toolkit content (Story 6.A.4 owns; this story is the marketing-milestone Landing 页 only)
  - IP-attribution Tier 1/2/3 badges per scholar (Story 6.A.5 v2)
  - Multi-language switch (Story 1.10 owns zh/en across the site)
  - SSO / scholar identity verification — out of scope; v1 trusts the .edu/.ac.cn email TLD check that 1.4 already enforces
  - PDF / printable poster export of the citation list — defer; M3 marketing may want it
  - A/B variant or feature-flag gating — single static page v1
  - SEO meta tags (Open Graph, Twitter Card, sitemap.xml entry) — basic title/description only; full SEO sweep is M3 marketing story
  - Analytics tag / page-view counter — out of scope; M3 will add a sitewide telemetry story
  - i18n of citation labels themselves (year, venue) — stays zh-only v1 (matches 6.A.1)
---

# Story 6.A.2 — BibTeX 营销 milestone Landing 页 (Epic 6.A.2)

## User Story

**As** a 学者 / researcher arriving at OptiCloud after seeing the platform mentioned in a colleague's preprint,
**I want** a single page (`/academic`) that explains *why* OptiCloud cares about academic citations (Innovation #3 学界变现飞轮) and shows every algorithm's actual BibTeX entry ready for me to paste into my `.bib` file — plus a clear signup hook that mentions the edu-tier ¥2K Starter,
**so that** I can decide in under 60 seconds whether OptiCloud is worth my time, copy the citation I'll need for my paper, and start the free tier with a single `.edu` / `.ac.cn` signup.

## Why this story

6.A.1 (PR #29, 2026-05-20) shipped the citation **data**. But the only place a scholar can currently *find* these citations is the algorithm-detail page (`/algorithms/[k_algo]`) — one citation at a time, only when they already know which algorithm they want, and only as a side-quest below the "Try it now" CTA. That doesn't activate Innovation #3.

The PRD §2.3.4 and epics.md L482 frame this as the *学界变现飞轮 (academic monetization flywheel)*:
1. We give scholars free use (Story 1.4 edu-tier auto-activation = ¥2000 Starter)
2. Scholars cite OptiCloud algorithms in their papers (Story 6.A.1 BibTeX)
3. Those citations bring more scholars (this story's surface)
4. Story 6.A.3 (next) tracks the citations back to source

Without step 3 — a *page where a scholar can land, see all the citations, and signup* — the flywheel doesn't spin. Story 6.A.3 is downstream-blocked on having something to track to. Story 6.A.4 (招商 toolkit, RE2-2) and 6.A.5 (IP attribution tiers, E5) both reference /academic as the marketing surface they extend.

**Why now (vs after 1.12 or 3.E.8)**:
- 6.A.1 shipped 5 hours ago. Citation rendering pattern is fresh; reuse is trivial.
- This story is the smallest possible thing that completes Epic 6.A's marketing arc — 2-3 hours of pure FE, no backend, no schema.
- 3.E.8 is even smaller (1-2h copy polish) but doesn't open anything new. /academic opens a route + a referral surface for Innovation #3 downstream stories.
- 1.12 J7 vertical slice is heavier (~3-5h, requires risk-control FE) and not in the critical path right now.

**Why pure SSR**:
- The data (8 catalog rows + citations) is static at request time. No user-specific personalization.
- Crawlers (Semantic Scholar, Google Scholar, paper-bot lite indices) need the BibTeX text in the initial HTML so the 6.A.3 tracker (and external citation graph crawlers) can attribute citations back to the keys without executing JS.
- Faster TTI on Chinese-network egress (no client-side fetch round-trip).
- One server-side fetch happens at request time and is cacheable; Next 15's RSC default fits perfectly.

## Out of scope

- **6.A.3 citation tracking** — that's the next story; this one just renders the citations
- **6.A.4 学界招商 toolkit content (Provider Onboarding handbook)** — separate downstream story
- **6.A.5 IP attribution Tier 1/2/3 badges** — v2 feature on this same page
- **zh/en language switch** — Story 1.10 owns; v1 ships zh-only
- **SSO / scholar identity verification beyond email TLD** — out of scope; 1.4 already does what it does
- **PDF / printable poster of citations** — M3 marketing story (no enterprise ask for this yet)
- **A/B testing / feature flags** — single canonical static page
- **Full SEO sweep** — basic `<title>` + meta description only; full Open Graph / Twitter Card / sitemap.xml is a separate marketing story
- **Page-view analytics / heatmap** — sitewide telemetry is its own story
- **Linking from Epic 4 chat or Epic 3 console surfaces** — current 6.A.2 only adds one nav-bar link from the landing page Header; deeper cross-linking is downstream
- **API endpoint changes** — `GET /v1/algorithms` already returns citations as of 6.A.1; this story is a pure consumer

## Acceptance Criteria

### AC1: New `/academic` Next.js route — server component, SSR-friendly

Create `apps/web/src/app/academic/page.tsx` as a **server component** (no `"use client"` at the top). Layout:

```
<main>
  <header> ... shared header (Logo + nav + signup CTA) ... </header>

  <section className="hero">
    <h1>开放优化与预测，让学术研究可复现、可引用、可被发现</h1>
    <p>OptiCloud 把每一个算法的引用文献 (BibTeX) 当成一等公民。</p>
    <CTAs />
  </section>

  <section className="flywheel">
    <h2>学界变现飞轮 (Innovation #3)</h2>
    <FlywheelDiagram />  {/* 4-step text card */}
  </section>

  <section className="citations">
    <h2>引用 8 个算法</h2>
    <CitationsGrid /> {/* one card per algorithm */}
  </section>

  <section className="edu-cta">
    <h2>用 .edu / .ac.cn 邮箱注册，永久免费 ¥2,000 Starter / 月</h2>
    <SignupCTA />
  </section>

  <footer> ... </footer>
</main>
```

Data fetch:

```typescript
// Server-side fetch at request time. No "use client" needed.
async function getAlgorithms(): Promise<Algorithm[]> {
  const solverBase = process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL ?? "http://localhost:8002";
  const res = await fetch(`${solverBase}/v1/algorithms`, { next: { revalidate: 300 } });
  if (!res.ok) throw new Error(`upstream ${res.status}`);
  return res.json();
}

export default async function AcademicPage() {
  let algorithms: Algorithm[] = [];
  try {
    algorithms = await getAlgorithms();
  } catch {
    // Graceful degrade: render page without citation grid; CTAs still work
  }
  return <main>...</main>;
}
```

**Caching**: 5-minute revalidate (`next: { revalidate: 300 }`). Catalog is in-memory in solver-orchestrator, so the upstream cost is ~5ms; this just prevents a thundering-herd if a Tier-3 link from a paper goes viral.

**Graceful degrade**: if the solver-orchestrator is down or returns non-200, the page still renders the hero / flywheel / edu-CTA — only the citations grid is replaced by a `<StatusCard variant="warning">引用列表暂时不可用，请稍后重试或访问 <Link href="/algorithms">/algorithms</Link></StatusCard>`. No 500 page.

### AC2: Extract `CodeBlock` to a shared component

The `CodeBlock` component currently lives privately inside `apps/web/src/app/algorithms/[k_algo]/page.tsx` (L50-89, ~40 LOC). With this story, it becomes the third consumer (6.A.1 detail page Python/cURL/BibTeX, 6.A.2 academic page BibTeX). Per `simplify` rule-of-three: extract now.

Move to `apps/web/src/components/CodeBlock.tsx`. Export shape unchanged — the existing call sites in `[k_algo]/page.tsx` keep working with a single import-line change. New consumer in `/academic/page.tsx` imports from the same path.

`CodeBlock` props remain:

```typescript
interface CodeBlockProps {
  lang: "python" | "bash";
  code: string;
  testId: string;
  label?: string;      // optional override; default = lang-based
  ariaLabel?: string;  // optional override; default = "复制 {label} 代码"
}
```

**Critical**: do NOT change the component's behavior or props. Just move the file. The 6.A.1 review fixed this component (added `label` + `ariaLabel` props); regressing those is unacceptable.

### AC3: Hero section — copy

```html
<h1 class="text-4xl font-bold leading-tight md:text-5xl">
  开放优化与预测，让学术研究可复现、可引用、可被发现
</h1>
<p class="mt-3 text-xl text-muted-foreground md:text-2xl">
  每个算法都自带 BibTeX 引用 — 8 个 SKU、3 个学派、1976 → 2025 的学术血统全公开
</p>
<p class="mx-auto mt-6 max-w-2xl text-muted-foreground">
  Apache 2.0 自研 + 顶刊算法 + 商用产品的混合栈，提交一次任务 = 拿到结果 +
  当下最新的 citation.bibtex。学生 / 博士 / 教师永久免费 ¥2,000 Starter / 月。
</p>
```

Two CTAs side by side:
- Primary: `🎓 用 .edu / .ac.cn 邮箱注册` → `/auth/signup`
- Secondary: `↓ 跳到引用列表` → anchor link `#citations`

### AC4: Flywheel section — Innovation #3 diagram (text-based, no SVG)

Avoid heavyweight graphics; use a 4-card grid with arrow connectors:

```
┌───────────────────┐    ┌───────────────────┐
│ 1. 学者免费       │ →  │ 2. 学者发论文     │
│ .edu/.ac.cn 邮箱  │    │ paste citation.   │
│ → ¥2,000 / 月     │    │ bibtex            │
│ (Story 1.4)       │    │ (Story 6.A.1)     │
└───────────────────┘    └───────────────────┘
        ↑                          ↓
┌───────────────────┐    ┌───────────────────┐
│ 4. 更多学者上车   │ ←  │ 3. 论文带来新学者 │
│ flywheel spins    │    │ (Story 6.A.3 自动追踪) │
└───────────────────┘    └───────────────────┘
```

Use CSS `grid-cols-2` + simple borders + arrow characters; no JS / no images. Each card has `data-testid="flywheel-step-{1-4}"` for Playwright.

Below the diagram, one paragraph:

> Innovation #3 的关键不是"我们最快"，而是"用了 OptiCloud 的研究天然会传播"。
> 学者每次发论文 paste 一行 `@software{aqgs2025opticloud, ...}`，就等于在 ArXiv /
> Semantic Scholar 的引用图谱上多一个指向我们的节点。Story 6.A.3 在引用追踪上线
> 后，每条新引用都会自动转成一张 Linear 卡片提醒平台团队。

### AC5: Citations grid — one card per algorithm

For each of the 8 algorithms in `algorithms[]`:

```tsx
<article data-testid={`citation-card-${algo.k_algo}`}>
  <header className="flex items-center gap-2">
    <h3 className="font-mono">{algo.k_algo}</h3>
    <TierBadge tier={algo.tier} />  {/* reuse pattern from /algorithms list page */}
    <span className="text-xs text-muted-foreground">{algo.description_zh}</span>
  </header>

  {algo.citation && (
    <>
      <p data-testid="citation-authors-line">
        {algo.citation.authors_label_zh} · {algo.citation.venue} · {algo.citation.year}
      </p>
      {algo.citation.doi && (
        <a href={encodeURI(`https://doi.org/${algo.citation.doi}`)}
           target="_blank" rel="noopener noreferrer"
           data-testid={`doi-${algo.k_algo}`}>
          DOI: {algo.citation.doi}
        </a>
      )}
      {!algo.citation.doi && algo.citation.url && (
        <a href={encodeURI(algo.citation.url)}
           target="_blank" rel="noopener noreferrer"
           data-testid={`url-${algo.k_algo}`}>
          ↗ {algo.citation.url}
        </a>
      )}
      <CodeBlock
        lang="bash"
        code={algo.citation.bibtex}
        label="BibTeX"
        ariaLabel={`复制 ${algo.k_algo} 的 BibTeX 代码`}
        testId={`bibtex-${algo.k_algo}`}
      />
    </>
  )}

  {!algo.citation && (
    <p className="text-sm text-muted-foreground">该 SKU 暂无引用 (commercial-only)</p>
  )}

  <Link href={`/algorithms/${algo.k_algo}`} className="text-sm text-primary hover:underline">
    → 查看算法详情
  </Link>
</article>
```

Layout: `<div className="grid grid-cols-1 md:grid-cols-2 gap-6">` — 2-column responsive grid. The 8 cards fit in 4 rows on desktop, 8 rows on mobile.

Tier badge can be a local component (copy the 4-line color logic from `algorithms/[k_algo]/page.tsx` L22-34) OR — better — extract `TierBadge` similarly to CodeBlock in this same story since the pattern will keep duplicating. **Decision: defer TierBadge extraction**; the 4-line constant + JSX is too small to be worth the refactor friction this story. 6.A.5 (IP attribution tiers) will extract it naturally when it adds Tier 1/2/3 *scholar* badges next to the existing T1-T6 / P1-P5 tier badges.

### AC6: Edu-tier CTA section

```tsx
<section id="edu-tier-cta" className="bg-primary/5 border-t border-border py-16">
  <div className="mx-auto max-w-2xl px-6 text-center">
    <h2 className="text-3xl font-bold">用 .edu / .ac.cn 邮箱注册，永久免费 ¥2,000 Starter / 月</h2>
    <p className="mt-4 text-muted-foreground">
      Story 1.4 自动检测后缀；签到立即激活 edu_tier=true。
      不需要发邮件，不需要审核，不需要绑卡。
    </p>
    <Link href="/auth/signup" data-testid="edu-cta-signup"
          className="mt-8 inline-block min-h-touch rounded-md bg-primary px-6 py-3
                     font-semibold text-primary-foreground hover:bg-primary-600">
      🎓 立即注册 →
    </Link>
    <p className="mt-4 text-sm text-muted-foreground">
      非学界邮箱也欢迎用免费层 (¥6/月起)；学界优惠仅是首选。
    </p>
  </div>
</section>
```

**Truth check**: must match Story 1.4's actual behavior. Per Story 1.4 (PR #15): signup with `.edu` / `.ac.cn` TLD → `edu_tier=true` + ¥2000 seeded to `bucket="edu"`. The page MUST NOT promise anything 1.4 doesn't deliver. If FR A4 changes, this copy needs to change with it.

### AC7: Navigation — add "学术合作" link to landing-page header

In `apps/web/src/app/page.tsx` Header `<nav>` (currently has 算法目录 / 文档 / 定价 / 立即注册), insert a new link **before 文档**:

```tsx
<Link href="/academic" className="text-muted-foreground hover:text-foreground">
  学术合作
</Link>
```

This is the only cross-link added in v1. Algorithm detail page footer + /algorithms list footer cross-links can come in 6.A.4 / 6.A.5.

### AC8: Accessibility (NFR-A11Y / UX-DR5 Standard profile)

- Proper landmarks: `<main>` + `<header>` + `<footer>` + `<nav>` + section `aria-labelledby` patterns
- Heading hierarchy: H1 (page title) → H2 (each section: 飞轮 / 引用 / edu-CTA) → H3 (per citation card)
- All copy buttons keep their existing `aria-label="复制 {algo} 的 BibTeX 代码"` (per AC5)
- DOI / URL links carry `rel="noopener noreferrer"` (MUST) and `target="_blank"` (MUST) + visible text content (not just an icon)
- Anchor `#citations` is reachable via keyboard (Tab → Enter)
- The flywheel cards have `aria-describedby` pointing to the explanatory paragraph below, so screen readers don't get confused by the 4 "step N" cards out of context
- `aria-current="page"` on the header link (`学术合作` ↔ /academic) when active — Next.js `usePathname` can drive this; or skip in v1 since /academic is a leaf

### AC9: Tests — Playwright E2E only (no Vitest per 6.A.1 precedent)

`apps/web/vitest.config.ts` is `environment: "node"` for lib-logic only (no jsdom). Same justification as 6.A.1: skip Vitest component tests for this story; Playwright is the FE-rendering gate.

New file `e2e/tests/academic-page.spec.ts` — 5 cases:

1. `学者访问 /academic 看到 hero + 8 个引用卡 + edu CTA` — assert page title, all 8 `citation-card-{k_algo}` testids visible, `edu-cta-signup` link href = `/auth/signup`
2. `highs-lp citation card 内 BibTeX + DOI 链接均渲染` — narrow to `citation-card-highs-lp`, assert `bibtex-highs-lp` contains `huangfu2018parallelizing`, `doi-highs-lp` href = `https://doi.org/10.1007/s12532-017-0130-5`
3. `aqgs-acopf 自研引用使用 url 而非 doi 链接` — narrow to `citation-card-aqgs-acopf`, assert `url-aqgs-acopf` visible, `doi-aqgs-acopf` count = 0
4. `flywheel 4 卡 都可见 + 学者免费 / 学者发论文 / 论文带来新学者 / flywheel 文案存在` — assert 4 testids `flywheel-step-1..4` visible + key phrases
5. `Landing page header "学术合作" 链接跳到 /academic` — visit `/`, click 学术合作, assert URL matches /academic and page title

**Smoke** (manual, not gated): `pnpm -C apps/web dev` → http://localhost:3000/academic → visual check of layout + dark mode + mobile responsive (Tailwind breakpoints).

### AC10: NFR alignment + bundle / build

- No new packages; no new env vars; no new infra
- `pnpm -C apps/web typecheck` clean
- `pnpm -C apps/web build` — `/academic` is added as a new route; expected ≤ 5 KB First Load JS over baseline. The CodeBlock extraction may shave a kilobyte off `/algorithms/[k_algo]` since the component is no longer duplicated in client bundles. **Decision: do NOT track bundle delta tightly** — this is a static SSR page; First Load JS measures hydration cost, not the page itself.
- Pre-commit hooks all green (ruff / format / yaml / secrets / eol)
- Backend unchanged → no Python test impact

## Tasks

### T1 — Extract CodeBlock to shared location (0.3h)
1. Create `apps/web/src/components/CodeBlock.tsx` with the exact 50-line implementation moved from `apps/web/src/app/algorithms/[k_algo]/page.tsx`
2. Update `apps/web/src/app/algorithms/[k_algo]/page.tsx` to `import { CodeBlock } from "@/components/CodeBlock"` and remove the inline definition
3. `pnpm -C apps/web typecheck` green
4. Existing Playwright `algorithm-citation.spec.ts` (2 cases) still passes — no behavior change

### T2 — `/academic` route (1.0h)
1. Create `apps/web/src/app/academic/page.tsx` as a server component
2. Implement the SSR `getAlgorithms()` helper inline (or `apps/web/src/app/academic/lib/fetch-algorithms.ts` if it grows past 20 lines)
3. Hero section per AC3 copy
4. Flywheel 4-card grid per AC4
5. Citations grid mapping `algorithms.map(...)` per AC5
6. Edu-tier CTA section per AC6
7. Reuse landing-page Header pattern (copy-paste; consider extracting later)
8. Footer (link to /algorithms + small print)
9. Add basic `<title>` + meta description via Next.js `metadata` export

### T3 — Landing page nav link (0.05h)
1. Add `<Link href="/academic">学术合作</Link>` between 算法目录 and 文档 in `apps/web/src/app/page.tsx` Header `<nav>`

### T4 — Playwright tests (0.5h)
1. Create `e2e/tests/academic-page.spec.ts` with the 5 cases per AC9
2. `pnpm -C e2e exec playwright test --list e2e/tests/academic-page.spec.ts` discovers all 5

### T5 — Manual smoke + quality gates (0.3h)
1. `pnpm -C apps/web dev` → visual check at http://localhost:3000/academic (desktop + mobile)
2. `pnpm -C apps/web typecheck` + `pnpm -C apps/web build`
3. `uv tool run pre-commit run --files <changed>`

### T6 — Sprint-status bundled commit + PR + CI watch + merge (0.4h)
1. Bundle sprint-status flip (`6-a-2-bibtex-academic-page: backlog → review`, then `→ done` after code review) into the same commit
2. Push, open PR with structured body, watch CI green, merge

**Total**: ~2.6h

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **SSR fetch fails in CI Playwright run** because solver-orchestrator isn't running on `http://localhost:8002` when Playwright launches Next dev | The graceful-degrade path (AC1) means the page still renders without citations. Playwright assertions for citation cards (Test #2-#3) will fail in that scenario — but the existing e2e.yml job DOES spin up solver-orchestrator (`services: postgres` + the manual app boots; see e2e.yml). Verify before merge. Failing path: if CI's e2e harness doesn't include solver-orchestrator boot, this story's tests will hit the fallback path. Mitigation 2: tests #1, #4, #5 don't depend on citations — they only fail if hero/flywheel/landing-link breaks. Tests #2/#3 are skippable on graceful-degrade detection (assert that EITHER citation cards exist OR the fallback StatusCard is visible). |
| **`process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL` mismatch between dev / CI / prod** | Same env var that `apps/web/src/lib/api.ts` already uses (default `http://localhost:8002`). No new env var; consistent fallback. Documented. |
| **5-min revalidate could leak stale citations after a catalog hotfix** | Acceptable v1 — catalog edits are rare and propagate within 5 min. If urgent, redeploy invalidates. M3 may add a manual revalidate trigger. |
| **CodeBlock extraction breaks `algorithms/[k_algo]/page.tsx`** | T1 step 4 verifies via existing 2 Playwright cases. Component is moved verbatim — same props, same DOM, same testid. The risk is "import path typo" caught by typecheck. |
| **flywheel ASCII-art arrows render badly on Chinese-installed Windows font fallback** | Use CSS-based arrows (`→` / `↑` / `↓` Unicode chars) not ASCII (`->`). Unicode renders cleanly in modern fonts. Tested visually in T5. |
| **Edu-tier CTA copy outpaces Story 1.4's actual behavior** | AC6 explicitly anchors to 1.4. If 1.4's TLD list ever changes (e.g. add `.cas.cn` to whitelist), this page must update. Documented in `_bmad-output/deferred-work.md` as a cross-story sync point. **Decision: do not add a deferred-work entry** — Story 1.4 freezing the TLD list is not blocking; if 1.4 expands later, ripgrep for `.edu / .ac.cn` to find the 3 places that need updating (signup form, /academic page, edu-tier policy doc). |
| **`/academic` becomes outdated as catalog grows past 8** | Page renders all algorithms returned by `GET /v1/algorithms` — no hardcoded count. Adding a 9th catalog row → automatically renders without /academic code change. Only the H2 ("引用 8 个算法") has a hardcoded "8"; mitigation: use dynamic `algorithms.length`. |
| **Crawlers see only the static HTML (no client-side hydration of citations)** | Per AC1 SSR design: citations ARE in the initial HTML. Crawlers see them. JS-disabled scholars also see them. |
| **CSS arrow connectors don't show up correctly in mobile portrait** | Use a different layout below md breakpoint: stack the 4 cards vertically with `↓` arrows between (not `→` / `←`). Tailwind `flex-col md:grid md:grid-cols-2`. |
| **DOI / URL `target="_blank"` opens too many tabs if a scholar Tab-clicks through all 8** | Acceptable; this is the same UX as `/algorithms/[k_algo]`. `rel="noopener"` prevents window.opener leak. |
| **Page is loud / cringe** (Chinese marketing pages often over-emoji + over-color) | Brand voice is "实证克制" (per PRD §1.4 + landing page); flywheel emoji ↑↓ + 1 each for 🎓 / 📚 is the maximum density. No animated GIFs, no gradients, no glow effects. Match the existing landing page tone exactly. |
| **Citation cards crash on a row where `citation === null`** | Story 6.A.1 currently sets `citation` on all 8 rows. If a future commercial-only SKU is added with `citation: null`, the page renders "该 SKU 暂无引用" (AC5 conditional). Tested in unit not E2E. |
| **The 5-min cache means after a catalog edit (e.g. typo fix), users see stale until revalidate** | The catalog is in-memory in the Python service. A redeploy of solver-orchestrator restarts the process → new catalog state. The Next.js 5-min revalidate is on TOP of that — worst case 5 min stale. Acceptable for marketing page. |

## Definition of Ready

- ✅ Story 6.A.1 (citation field) is in main (PR #29 merged 2026-05-20)
- ✅ `Algorithm` + `Citation` TypeScript interfaces exist in `apps/web/src/lib/api.ts`
- ✅ `GET /v1/algorithms` is auth-free + returns citation field for all 8 rows
- ✅ Landing page pattern + Tailwind tokens established (Story 0.10)
- ✅ Playwright fixtures pattern established (multiple precedents incl. 6.A.1)
- ✅ Story 1.4 edu-tier whitelist behavior documented and shipped

## Definition of Done

- 10 ACs pass
- New route `apps/web/src/app/academic/page.tsx` + new component `apps/web/src/components/CodeBlock.tsx`
- Landing page header gains 学术合作 link
- e2e/tests/academic-page.spec.ts +5 cases (Playwright)
- Existing `algorithm-citation.spec.ts` still passes (CodeBlock extraction didn't break it)
- Manual smoke: visit `/academic` on `pnpm dev` → see hero + 4 flywheel cards + 8 citation cards (or graceful-degrade card) + edu CTA + 学术合作 link in landing page header
- CI: 13/13 jobs green
- Sprint-status updated **and bundled into the PR commit**

## Sign-off

| Role | Owner | Signed | Date |
|---|---|:-:|:-:|
| FE Lead | TBA | ☐ | — |
| Marketing / 学界 PoC | TBA | ☐ | — |

> Owner committee deferred per M0 skip; story is technically self-contained.

---

## Round 1: BMad Checklist Review

| # | Item | Status | Note |
|---|---|:-:|---|
| 1 | User story has As/I want/so that | ✅ | Scholar persona + 60-second-decision narrative |
| 2 | ACs testable & BDD-shaped | ✅ | 10 ACs; AC9 enumerates 5 Playwright cases |
| 3 | Scope explicit (in/out) | ✅ | 10-item Out of scope list |
| 4 | Dependencies declared | ✅ | upstream 6.A.1 + 2.1 + 1.4; downstream 6.A.3 + 6.A.4 + 6.A.5 + 8.C.8 |
| 5 | Sizing estimate | ✅ | S–M (~2-3h); tasks sum to ~2.6h |
| 6 | Risks identified with mitigations | ✅ | 14 risks documented |
| 7 | Quality gates listed | ✅ | AC10 |
| 8 | Test plan | ✅ | 5 Playwright cases |
| 9 | Backwards compat | ✅ | CodeBlock extraction is verbatim move; existing tests guard |
| 10 | Sources cited | ✅ | 11 source files with line numbers |

Round 1: **PASS**

---

## Round 2: 5-Perspective Review

### 🏗️ Architect

- ✅ Server component / SSR is correct for a scholar-marketing page (crawlers, fast TTI, no client-fetch round-trip)
- ✅ 5-min revalidate matches the catalog's update cadence (rare hotfixes; redeploys cycle naturally)
- ✅ CodeBlock extraction follows rule-of-three — third consumer (after 6.A.1's Python/cURL/BibTeX uses) justifies the move
- ✅ Graceful-degrade path keeps the page useful even when upstream is down
- ⚠️ Cross-app `process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL` — server component can also use `process.env.SOLVER_SERVICE_URL` (server-only). Decision: stay with the existing `NEXT_PUBLIC_*` pattern for consistency (single source of truth). Documented.

### 👨‍💻 Dev

- ✅ Pattern is fully copy-paste-able from landing page (apps/web/src/app/page.tsx) + 6.A.1 detail page
- ✅ No new dependencies; no schema; no migrations
- ✅ Reuse of Citation TS interface from 6.A.1 means zero type duplication
- ⚠️ The graceful-degrade path needs a try/catch around `getAlgorithms()`. Verified in AC1 example.
- ⚠️ Next 15 `metadata` export requires top-level `export const metadata = {...}` in the file. Won't conflict with the server component default export.

### 🧪 QA

- ✅ 5 Playwright cases cover the critical surface (page renders, key sections present, DOI vs URL conditional, header link)
- ⚠️ Test #2/#3 require solver-orchestrator running in CI. The existing e2e.yml job DOES boot solver-orchestrator (it has services: postgres + manual app starts via dev-deps step). Verified by looking at e2e.yml from prior 6.A.1 CI runs.
- ⚠️ Add an assertion that the page is reachable via SSR (server-side rendered HTML contains "Innovation #3" text). Curl-style check could be done in Playwright via `page.content()` before any JS executes. **Decision: SKIP** — Playwright's headless Chromium always executes JS; the SSR-vs-CSR distinction would need a separate node-fetch test. The 5-min revalidate is implementation-detail; what matters is that the page works.

### 🔐 Security

- ✅ No user input on this page; no API keys; no secrets
- ✅ DOI / URL links carry `rel="noopener noreferrer"` (MUST per AC8)
- ✅ Bibtex string is platform-curated; React `<pre>` escaping handles any malicious-looking input
- ✅ `getAlgorithms()` fetches from internal solver-orchestrator URL; no user-supplied URL in fetch
- ✅ Page is public; no auth gating needed

### 🛠️ SRE

- ✅ Zero infra changes
- ✅ Zero new env vars
- ✅ Pre-commit hooks (ruff / yaml / secrets / eol) all apply
- ✅ Rollback: revert the 2 new files + 1 line in landing page header
- ⚠️ Production deploy: `NEXT_PUBLIC_SOLVER_SERVICE_URL` must point to the right backend. Matches existing FE convention.

Round 2: **PASS** with no AC changes needed.

---

## Round 3: Dev-Readiness

- ✅ All file paths absolute (`apps/web/src/app/academic/page.tsx`, `apps/web/src/components/CodeBlock.tsx`, etc.)
- ✅ Component / route structure fully specified
- ✅ Test names enumerated (5 Playwright cases)
- ✅ Reference patterns: landing page header + 6.A.1 citation block + algorithms list grid
- ✅ Sizing realistic — ~2.6h per Tasks summation; matches `epics.md` "营销 Landing 页" sizing
- ✅ Sprint-status bundling lesson applied (T6)
- ✅ Branch name: `feature/6-a-2-bibtex-academic-page`
- ✅ CI watch: direct `gh pr checks N --watch` + run_in_background, ~15s after PR open

Round 3: **PASS — READY FOR DEV**

---

## Implementation Notes

- For T1: when moving CodeBlock, keep the `"use client"` directive in the **new file** `apps/web/src/components/CodeBlock.tsx` — it uses `useState`. The /academic page imports it; even though /academic itself is a server component, importing a client component from a server component is legal in Next.js App Router (client component becomes its own bundle chunk).
- For T2: Next 15 metadata syntax:
  ```typescript
  export const metadata = {
    title: "学术合作 — OptiCloud",
    description: "每个算法自带 BibTeX 引用 ...",
  };
  ```
- For T2 step 7: the landing-page Header is currently inlined inside `apps/web/src/app/page.tsx`. **Do NOT extract it to a shared component this story** — that's premature abstraction with only 2 consumers; 6.A.4 may add a 3rd academic-specific header variant. Document as DR-6.A.2-1.
- For T4: Playwright tests should use `await page.goto("/academic", { waitUntil: "networkidle" })` to give the SSR fetch time to complete (in dev mode, the first request kicks off the upstream fetch).
- For T6 step 1: per `feedback_strict_bmad_cycle` + `feedback_full_quality_gates`, sprint-status flip MUST be bundled into the implementation commit (not a follow-up PR). Pattern from PR #29: `git add _bmad-output/stories/sprint-status.yaml` together with all code files BEFORE `git commit`.

Completion note: "Ultimate context engine analysis complete — Story 6.A.2 ships /academic Landing 页 as the second pillar of Epic 6.A's Innovation #3 学界变现飞轮 marketing arc. Pure FE (SSR + 1 component extraction); reuses 6.A.1 catalog API + Citation TS interface. 5 Playwright cases cover page render + citation conditionals + nav cross-link. DR-6.A.2-1 defers landing-page Header extraction."

---

## Dev Agent Record

### Agent Model Used

claude-opus-4-7 (1M context)

### Implementation Plan

Executed T1–T6 in story-spec order. One refinement beyond spec during T5: `/academic` gained `export const dynamic = "force-dynamic"`.

**Why**: AC1 specified `next: { revalidate: 300 }` (a 5-min ISR cache). But the e2e.yml job sequence is: start solver-orchestrator (backgrounded `&`) → immediately `pnpm -C apps/web build` → `pnpm start`. Next.js statically prerenders `○ (Static)` routes at build time; if `pnpm build` reaches the `/academic` prerender before the backgrounded solver-orchestrator is listening, the build bakes the graceful-degrade fallback into the static page — and the 5-min `revalidate` then serves that stale fallback through the entire e2e window, failing the citation-card tests (Risk #1 in the spec). `force-dynamic` makes the route `ƒ` (server-rendered per request), so it always fetches fresh against the readiness-gated solver-orchestrator (the e2e job waits for `:8002/healthz`). The page is still SSR — crawler-friendly per the AC1 design intent — just not build-time-frozen. The `next: { revalidate: 300 }` on the `fetch()` call is kept as a data cache for thundering-herd protection.

### Debug Log References

- 2026-05-20 — first `pnpm build` showed `○ /academic (Static)` with 5m revalidate. Recognized the build-time-prerender race against the e2e job's backgrounded solver-orchestrator boot; added `export const dynamic = "force-dynamic"`; rebuild confirmed `ƒ /academic`.

### Completion Notes

- All 10 ACs satisfied:
  - AC1 ✅ — `/academic` server component; SSR fetch with try/catch graceful-degrade; `force-dynamic` (see Implementation Plan)
  - AC2 ✅ — `CodeBlock` extracted to `apps/web/src/components/CodeBlock.tsx` (verbatim move + `"use client"`); `[k_algo]/page.tsx` imports it; props unchanged
  - AC3 ✅ — Hero copy per spec
  - AC4 ✅ — 4-card flywheel grid; `flywheel-step-{1..4}` testids; explainer paragraph with `aria-describedby` wiring
  - AC5 ✅ — citations grid (2-col responsive); per-card 学者信息 line + DOI/URL conditional + BibTeX CodeBlock; commercial-only-null branch handled
  - AC6 ✅ — edu-tier CTA section anchored to Story 1.4 behavior
  - AC7 ✅ — 学术合作 nav link added to landing page header between 算法目录 and 文档
  - AC8 ✅ — landmarks + heading hierarchy (H1→H2→H3) + `aria-labelledby` per section + `rel="noopener noreferrer"` on all external links
  - AC9 ✅ — 5 Playwright cases in `e2e/tests/academic-page.spec.ts`; Vitest skipped per 6.A.1 precedent (no jsdom infra)
  - AC10 ✅ — typecheck + build green; pre-commit all hooks pass; no new deps / env vars; `/academic` First Load JS 131 kB / route size 818 B
- `H2` "引用 N 个算法" uses dynamic `algorithms.length` (no hardcoded 8) per Risk-table mitigation
- DR-6.A.2-1 documented: landing-page Header not extracted to a shared component (only 2 consumers; premature)

### File List

**Created:**
- `apps/web/src/components/CodeBlock.tsx` (extracted from `[k_algo]/page.tsx`; verbatim + `"use client"`)
- `apps/web/src/app/academic/page.tsx` (server component — `/academic` route)
- `e2e/tests/academic-page.spec.ts` (5 Playwright cases)

**Modified:**
- `apps/web/src/app/algorithms/[k_algo]/page.tsx` (removed inline CodeBlock; added `import { CodeBlock } from "@/components/CodeBlock"`)
- `apps/web/src/app/page.tsx` (added 学术合作 → /academic nav link)
- `_bmad-output/stories/sprint-status.yaml` (6-a-2-bibtex-academic-page backlog → review)
- `_bmad-output/stories/6-a-2-bibtex-academic-page.md` (this file; status → review; Dev Agent Record + File List + Change Log added)

### Change Log

- 2026-05-20 — Story 6.A.2 implementation: /academic SSR Landing 页 (hero + 学界变现飞轮 4-card diagram + 8-citation grid + edu-tier CTA) + CodeBlock extraction to shared component + landing-page 学术合作 nav link + 5 Playwright tests. Second pillar of Epic 6.A Innovation #3 arc.
