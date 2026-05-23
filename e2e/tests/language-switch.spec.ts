import { expect, test } from "../fixtures";

test.describe("language switch", () => {
  test("switches Landing to English and persists locale cookie", async ({ page }) => {
    await page.context().clearCookies();
    await page.context().addCookies([
      {
        name: "opticloud-locale",
        value: "zh-CN",
        domain: "127.0.0.1",
        path: "/",
      },
    ]);
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "让算法走出实验室" })).toBeVisible();

    await page.getByTestId("language-switcher").getByRole("button", { name: "English" }).click();

    await expect(
      page.getByRole("heading", { name: "Optimization APIs for business engineers" }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/$/);

    const localeCookie = (await page.context().cookies()).find(
      (cookie) => cookie.name === "opticloud-locale",
    );
    expect(localeCookie?.value).toBe("en-US");
  });
});
