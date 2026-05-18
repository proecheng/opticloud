# @opticloud/ui

Tier 1 12 v1 Component stubs — **Story 0.9 / 0.10 / 0.11 / 0.12 (Sprint 0 N3 unlock)**.

## What's here

**Hooks**:
- `useA11y` — Standard a11y Hook Wrapper (UX-DR5 / AA6 / AA12)

**Tier 1 12 v1 Components** (Architecture P72 — packages/ui 单源):

| Component | UX Spec ref | Owner Story |
|---|---|---|
| `APIKeyManager` | Step 11 | Story 1.1b (J1 + FR A2 + CRG12 mask/reveal) |
| `ConfidenceLabel` | Step 11 + EP4 | Story 4.B.4 (FR N12 + CRG14 visual brackets) |
| `ConfirmationModal` | Step 11 + Modal Discipline | Story 1.1b / 5.A.3 (5 P5 警示 variants) |
| `CreditsBalanceBucket` | Step 11 | Story 5.A.1 (FR B1 4 桶) |
| `ErrorBoundary` + `RFC7807Panel` | Step 12 Error Display | Story 3.7 (FG1.3 errors[] + next_action_url) |
| `ExcelDropZone` | Step 11 + 老张 sub-persona | Story 3.E.1 (FR E11 + 共用 FilePicker S3 fix) |
| `SparklineKPI` | Step 11 | Story 5.D.1-2 (FR B7 7d/30d trends) |
| `StatusCard` | Step 12 Status Communication | Story 8.A.1-2 (FR O1) |
| `Toast` | Step 12 Toast Notification | Cross-cutting |
| `FilePicker` | Cross-cutting | Story 3.E.1 + 4.C.3 (S3 单源) |
| `LoadingShimmer` | Step 12 Loading & Skeleton | Cross-cutting |
| `EmptyState` | Step 12 Empty State | Cross-cutting |

## Quickstart

```bash
# Install (from repo root)
pnpm install

# Storybook (Tier 1 12 components visible)
cd packages/ui
pnpm storybook
# → http://localhost:6006

# Run tests (Vitest + jest-axe)
pnpm test

# Run a11y-specific tests only
pnpm test:a11y

# Chromatic visual regression (P74)
CHROMATIC_PROJECT_TOKEN=xxx pnpm chromatic
```

## a11y Compliance (Story 0.12 + UX-DR5)

Every component **must** pass:
- ✅ `useA11y` Hook applied (or equivalent ARIA attrs)
- ✅ aria-label required (i18n key, never hard-coded text)
- ✅ Focus visible (Tailwind `focus-visible:` ring or `useA11y`)
- ✅ Min touch target 44×44 px (Tailwind `min-h-touch` / `min-w-touch`)
- ✅ Disabled state contrast ≥ 3:1
- ✅ axe-core 0 violations (`src/components/Tier1.a11y.test.tsx`)
- ✅ Storybook a11y addon 0 violations
- ✅ Chromatic visual regression snapshot

## Brand & Visual Tokens (Story 0.10 + UX-DR4)

- **Primary**: `#2D5BA8` (Olympics Winner)
- **Dark Mode**: `#0D1117` background (GitHub-aligned) + `#4A77BB` primary
- **Confidence brackets** (CRG14): `confidence.high` / `mid` / `low`
- **Typography**: Inter Variable + 思源黑体 + Sarasa Gothic Mono
- **Tokens**: `src/tokens.css` CSS variables + Tailwind extension

## Architecture references

- **P72** UI Component Single-Source Discipline
- **P74** Cross-Service Storybook Visual Regression
- **C22** Tailwind v3 locked v1; v4 evaluation v1.5+ (FR3 Forward Ref)
- **NFR-A5** WCAG 2.1 AA v1 → 2.2 AA v1.5+
- **CRG12** API Key mask + Reveal toggle + Modal warning
- **CRG13** ExcelDropZone actionable hint when reject
- **CRG14** ConfidenceLabel visual brackets (≥0.85 绿 / 0.6-0.85 黄 / <0.6 红)

## Component PR-gate (S-S1 + W3 fix)

When using a Tier 1 component in business Epic stories, AC must include:
- packages/ui Component PR-gate test passes (focus trap / ESC / aria-label / heading lint / contrast)
- Storybook story exists demonstrating real Epic scenario
- axe-core a11y test no violations
- Mock-real divergence test (Q-T1) when applicable
