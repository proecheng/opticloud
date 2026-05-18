/**
 * Playwright config — Story 0.13.
 *
 * Local dev: `webServer` array auto-spawns 3 services if not running.
 *            `reuseExistingServer: !process.env.CI` → if already running, reuse.
 * CI:        services started externally by .github/workflows/e2e.yml,
 *            Playwright reuses them via `reuseExistingServer: true`.
 *
 * baseURL: env var `PLAYWRIGHT_BASE_URL` (default http://localhost:3000).
 */

import { defineConfig, devices } from "@playwright/test";

const isCI = !!process.env.CI;
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const AUTH_URL = process.env.PLAYWRIGHT_AUTH_URL ?? "http://localhost:8001";
const SOLVER_URL = process.env.PLAYWRIGHT_SOLVER_URL ?? "http://localhost:8002";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  workers: isCI ? 1 : undefined,
  timeout: 60_000,
  expect: { timeout: 5_000 },

  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report" }],
    isCI ? ["github"] : ["null"],
  ],

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
    extraHTTPHeaders: {
      "Accept-Language": "zh-CN",
    },
  },

  // Cross-browser policy (Q1 fix from Round 2):
  //   - PR / CI default: chromium only (speed).
  //   - Nightly cron + main branch: enable firefox + webkit (see .github/workflows/e2e-cross-browser.yml).
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    // Enabled in CI nightly only — gated by env var
    ...(process.env.PLAYWRIGHT_CROSS_BROWSER
      ? [
          { name: "firefox", use: { ...devices["Desktop Firefox"] } },
          { name: "webkit", use: { ...devices["Desktop Safari"] } },
        ]
      : []),
  ],

  // webServer config (A2 fix from Round 2):
  // Local: auto-spawn services. CI: reuse externally started.
  webServer: isCI
    ? undefined
    : [
        {
          command:
            'PYTHONPATH="..\\packages\\shared-py;..\\apps\\auth-service\\src;..\\packages\\python-sdk\\src" ..\\.venv\\Scripts\\python.exe -m uvicorn auth_service.main:app --port 8001',
          url: `${AUTH_URL}/healthz`,
          reuseExistingServer: true,
          timeout: 90_000,
          cwd: "..",
        },
        {
          command:
            'PYTHONPATH="..\\packages\\shared-py;..\\apps\\solver-orchestrator\\src;..\\packages\\python-sdk\\src" ..\\.venv\\Scripts\\python.exe -m uvicorn solver_orchestrator.main:app --port 8002',
          url: `${SOLVER_URL}/healthz`,
          reuseExistingServer: true,
          timeout: 90_000,
          cwd: "..",
        },
        {
          command: "pnpm -C ..\\apps\\web dev",
          url: BASE_URL,
          reuseExistingServer: true,
          timeout: 90_000,
          cwd: "..",
        },
      ],
});
