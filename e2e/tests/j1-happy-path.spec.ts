/**
 * J1 Happy Path E2E — Story 0.13 AC2.
 *
 * Full vertical slice: 访客 → 注册 → 拿 API Key → 试跑 LP → 看求解结果
 */

import { expect, test } from "../fixtures";

import { randomEmail, randomPhone } from "../fixtures/auth";

test.describe("J1 — 李工 cURL Hello World vertical slice", () => {
  test("访客可以完成注册并跑通第一个 LP 求解", async ({ page }) => {
    const phone = randomPhone();
    const email = randomEmail();

    await test.step("a. 访问 Landing 页", async () => {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "让算法走出实验室" })).toBeVisible();
    });

    await test.step("b. 点击立即注册跳转到 /auth/signup", async () => {
      // Use nav landmark to avoid ambiguity with hero CTA (CR3 fix)
      await page.getByRole("navigation").getByRole("link", { name: "立即注册" }).click();
      await expect(page).toHaveURL(/\/auth\/signup$/);
      await expect(page.getByRole("heading", { name: "注册 OptiCloud" })).toBeVisible();
      await expect(page.getByTestId("signup-wizard")).toBeVisible();
      await expect(page.getByText("5 步跑通 Hello World")).toBeVisible();
    });

    await test.step("c. 填手机+邮箱并提交", async () => {
      await page.getByLabel("手机号").fill(phone);
      await page.getByLabel("邮箱").fill(email);
      await page.getByLabel("年龄").fill("18");
      await page.getByRole("button", { name: /立即注册/ }).click();
    });

    await test.step("d. 自动跳转 /welcome 看到 API Key Modal", async () => {
      await page.waitForURL(/\/welcome/, { timeout: 15_000 });
      // Wait for createApiKey() fetch to complete + Modal to render
      // (Modal renders conditionally after useEffect API call)
      await expect(page.getByText(/注册成功 — Hello World 立即开跑/)).toBeVisible({
        timeout: 15_000,
      });
      await expect(page.getByTestId("signup-wizard")).toBeVisible();
      await expect(page.getByText("拿 API Key")).toBeVisible();
    });

    await test.step("e. 关 Modal 看到 APIKeyManager + masked prefix", async () => {
      // Press ESC to close modal (useA11y trap focus + ESC handler)
      await page.keyboard.press("Escape");
      // CR5 fix: assert modal actually closed before continuing
      await expect(page.getByTestId("confirmation-modal")).toBeHidden({ timeout: 3_000 });
      const manager = page.getByTestId("api-key-manager");
      await expect(manager).toBeVisible();
      // Masked prefix shown
      await expect(manager).toContainText(/sk-[A-Za-z0-9_-]{3}/);
    });

    await test.step("f. 点 '试跑 LP 求解' 等结果", async () => {
      await page.getByRole("button", { name: /试跑 LP 求解/ }).click();
      // Wait for result panel to appear (within solver budget)
      await expect(page.getByText(/求解完成/)).toBeVisible({ timeout: 30_000 });
      await expect(page.getByTestId("signup-wizard")).toContainText("Hello World 跑通");
      await expect(page.getByTestId("signup-wizard")).toContainText("已完成");
    });

    await test.step("g. 验证 objective + solution + provider_url (Q2 fix: 范围 assert)", async () => {
      // Objective should appear (案例 1 题，最优 = 15.0)
      const resultPanel = page.locator("div", { hasText: "最低总成本" }).first();
      await expect(resultPanel).toBeVisible();

      // Provider transparency (A-S1)
      const providerInfo = page.locator("text=/求解器信息/").first();
      await providerInfo.click(); // expand details
      await expect(page.getByText(/highs/)).toBeVisible();
      await expect(page.getByText(/https:\/\/highs\.dev/)).toBeVisible();
    });
  });
});
