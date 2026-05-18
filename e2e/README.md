# OptiCloud E2E (Playwright)

> Story 0.13 — End-to-end test suite covering the 5 critical journeys (J1 cURL, J2 CSV, 老张 Excel, J7 风控, J9 白帽).

## Quickstart

### Prerequisites

1. Docker Desktop running + `docker-compose -p opticloud up -d` (postgres + redis + vault + minio + localstack)
2. Python deps installed: `uv sync --all-packages --extra dev`
3. Node deps installed: `pnpm install`
4. Playwright browsers: `pnpm -C e2e exec playwright install chromium`

### Run all tests (local — auto-spawns services if not running)

```bash
pnpm -C e2e exec playwright test --project=chromium
```

The `webServer` block in `playwright.config.ts` will:
- Detect if `localhost:8001` (auth), `localhost:8002` (solver), `localhost:3000` (web) are up
- If not — spawn them and wait up to 90 seconds for `/healthz` readiness
- If yes — reuse them (no double-spawn)

### Interactive UI mode (recommended for debugging)

```bash
pnpm -C e2e exec playwright test --ui
```

### View last HTML report

```bash
pnpm -C e2e report
# opens playwright-report/index.html in browser
```

### Cleanup E2E test data

Each test creates a random user prefixed `e2e-<runId>-...@example.com`. Run cleanup periodically (or after CI):

```bash
pnpm -C e2e cleanup
```

## Adding a new journey test

Template (~10 lines):

```ts
import { test, expect } from "@/fixtures";

test.describe("J3 — your-journey-name", () => {
  test("scenario description", async ({ page, randomUser }) => {
    await test.step("step 1", async () => {
      await page.goto("/some-page");
      await expect(page.getByRole("heading", { name: /.../ })).toBeVisible();
    });
    // ... more steps
  });
});
```

Key conventions:
- **Selector priority**: `getByRole()` > `getByLabel()` > `getByTestId()` > CSS class
- **Use `test.step()`** — readable hierarchy in HTML report
- **Use `randomUser` fixture** — auto-signs up a fresh user per test
- **Email prefix `e2e-`** — guaranteed by `randomEmail()`; cleanup script relies on this

## Debugging failures

When a test fails (locally or in CI):

1. **Playwright report**: `pnpm -C e2e report` opens HTML with screenshots + videos + traces
2. **Trace viewer**: `pnpm -C e2e exec playwright show-trace test-results/<test>/trace.zip` — time-travel through every action
3. **Reproduce CI failure locally**:
   - Download CI artifact `playwright-report` from GitHub Actions
   - Unzip + open `index.html`
   - Match Playwright + Chromium versions: `pnpm -C e2e exec playwright --version`

## VS Code recommended setup

Install **"Playwright Test for VSCode"** extension (`ms-playwright.playwright`):
- Run/debug tests inline (gutter ▶️ icons)
- Set breakpoints in test code
- Inspect Playwright traces from VSCode panel

## CI runs

- **PRs / main branch** (`.github/workflows/e2e.yml`): chromium only, ~5 min
- **Nightly cron + scheduled** (planned future workflow): adds firefox + webkit
- Artifacts retained 7 days (S3 fix — short retention for safety)

## Architecture references

- **Story 0.13**: This E2E framework — `_bmad-output/stories/0-13-playwright-e2e.md`
- **Story 0.11 + P74**: Storybook + Chromatic (Component-level visual regression — complementary)
- **Story 0.5b + M3.2**: Hypothesis + Schemathesis (API contract — complementary)
- **UX-DR7**: 5 Critical Mermaid Flows (target journeys for E2E)
