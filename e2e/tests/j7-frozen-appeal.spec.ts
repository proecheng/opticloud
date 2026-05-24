/**
 * J7 frozen appeal E2E — Story 1.12 AC7.
 *
 * Route-mocked browser flow only: start appeal -> submit proposal -> accept merge.
 */

import { expect, test } from "../fixtures";

const appealId = "a5d3d7f6-0000-4000-8000-000000000001";
const userId = "98cf1268-30d3-4f25-9a1f-f167b441d000";
const duplicateUserId = "b26a756e-2294-4cc3-a764-9ef289f4c100";
const proposalId = "b5d3d7f6-0000-4000-8000-000000000001";
const trackingToken = "tracking-token-j7";

const riskSummary = {
  total_flag_count: 2,
  latest_rule_codes: ["ip_24_share", "geo_anomaly"],
  latest_flag_at: "2026-05-24T09:00:00Z",
  risk_score: 0.72,
};

const proposalBase = {
  id: proposalId,
  requester_user_id: userId,
  primary_user_id: userId,
  duplicate_user_ids: [duplicateUserId],
  evidence: {
    reason: "同一团队误建重复账户",
    contact_email: "review@example.com",
    team_size: 2,
  },
  review_mode: "auto",
  auto_score: 0.86,
  review_due_at: "2026-05-24T12:00:00Z",
  reviewed_at: null,
  reviewed_by: null,
  decision_reason: null,
  created_at: "2026-05-24T09:00:00Z",
  updated_at: "2026-05-24T09:00:00Z",
};

test.describe("J7 — frozen account appeal", () => {
  test("用户可以开始申诉、提交合并提案并接受合并", async ({ page }) => {
    await page.route("**/v1/auth/frozen-appeals/start", async (route) => {
      const request = route.request();
      expect(request.method()).toBe("POST");
      expect(await request.postDataJSON()).toMatchObject({
        phone: "+8613800138000",
        email: "frozen@example.com",
      });
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          appeal_id: appealId,
          status: "started",
          user_id: userId,
          tracking_token: trackingToken,
          tracking_url: `/auth/frozen-appeal?appeal_id=${appealId}&tracking_token=${trackingToken}`,
          expires_at: "2026-05-25T09:00:00Z",
          risk_summary: riskSummary,
          proposal: null,
          next_action: "submit_proposal",
        }),
      });
    });

    await page.route(`**/v1/auth/frozen-appeals/${appealId}/proposal`, async (route) => {
      const request = route.request();
      expect(request.method()).toBe("POST");
      expect(await request.postDataJSON()).toMatchObject({
        tracking_token: trackingToken,
        duplicate_user_ids: [duplicateUserId],
        reason: "同一团队误建重复账户",
        contact_email: "review@example.com",
        team_size: 2,
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          appeal_id: appealId,
          status: "proposal_submitted",
          expires_at: "2026-05-25T09:00:00Z",
          last_viewed_at: null,
          risk_summary: riskSummary,
          proposal: {
            ...proposalBase,
            status: "auto_approved",
            accepted_at: null,
            next_action: "accept_merge",
          },
          next_action: "accept_merge",
        }),
      });
    });

    await page.route(`**/v1/auth/frozen-appeals/${appealId}/accept`, async (route) => {
      const request = route.request();
      expect(request.method()).toBe("POST");
      expect(await request.postDataJSON()).toMatchObject({
        tracking_token: trackingToken,
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          appeal_id: appealId,
          status: "accepted",
          expires_at: "2026-05-25T09:00:00Z",
          last_viewed_at: null,
          risk_summary: riskSummary,
          proposal: {
            ...proposalBase,
            status: "accepted",
            accepted_at: "2026-05-24T09:30:00Z",
            next_action: "completed",
          },
          next_action: "completed",
        }),
      });
    });

    await page.goto("/auth/frozen-appeal?phone=%2B8613800138000&email=frozen%40example.com");
    await expect(page.getByRole("heading", { name: "账户已触发风控冻结" })).toBeVisible();
    await expect(page.getByText("提交后可用此页面查看复审状态。")).toBeVisible();

    await page.getByRole("button", { name: "开始申诉" }).click();
    await expect(page.getByTestId("appeal-submit-form")).toBeVisible();
    await expect(page.getByText(/风险分数 0.72/)).toBeVisible();
    await expect(page.getByText(/geo_anomaly/)).toBeVisible();

    await page.getByLabel("重复账户 ID").fill(duplicateUserId);
    await page.getByLabel("联系邮箱").fill("review@example.com");
    await page.getByLabel("团队人数").fill("2");
    await page.getByLabel("申诉说明").fill("同一团队误建重复账户");
    await page.getByLabel("补充说明").fill("请按主账户保留历史记录");
    await page.getByRole("button", { name: "提交提案" }).click();

    await expect(page.getByTestId("appeal-status-panel")).toBeVisible();
    await expect(page.getByText("复审模式：auto")).toBeVisible();
    await expect(page.getByText("得分：0.86")).toBeVisible();
    await expect(page.getByTestId("accept-merge-button")).toBeVisible();

    await page.getByTestId("accept-merge-button").click();
    await expect(page.getByText("下一步").locator("..")).toContainText("已完成");
    await expect(
      page.getByText("接受后保留主账户，重复账户会保持冻结，审计与账单记录保留。"),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "返回登录" })).toHaveAttribute(
      "href",
      "/auth/login",
    );
  });
});
