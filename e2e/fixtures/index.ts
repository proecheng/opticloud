/** Extended Playwright test fixture — auto-creates random user for tests that need auth. */

import { test as base } from "@playwright/test";

import type { RandomUser } from "./auth";
import { signupRandomUser } from "./auth";

export interface OptiCloudFixtures {
  randomUser: RandomUser;
}

export const test = base.extend<OptiCloudFixtures>({
  randomUser: async ({}, use) => {
    const user = await signupRandomUser();
    await use(user);
    // No cleanup here — bulk cleanup runs after suite via `pnpm cleanup`
  },
});

export { expect } from "@playwright/test";
