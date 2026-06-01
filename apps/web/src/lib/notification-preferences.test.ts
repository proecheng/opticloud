import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getNotificationPreferences,
  putNotificationPreferences,
} from "./api";

const preferences = {
  items: [
    {
      event_type: "billing.budget.alerted",
      email: true,
      webhook: false,
      in_app: true,
      webhook_url: null,
      webhook_url_configured: false,
      channels: ["email", "in_app"],
    },
    {
      event_type: "billing.budget.paused",
      email: true,
      webhook: true,
      in_app: false,
      webhook_url: "https://hooks.example.com/opticloud",
      webhook_url_configured: true,
      channels: ["email", "webhook"],
    },
  ],
};

describe("notification preferences API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("GETs preferences with bearer auth", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(preferences), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const result = await getNotificationPreferences("jwt-test");

    expect(result.items).toHaveLength(2);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/notification-preferences");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("zh-CN");
  });

  it("PUTs the exact full-replacement body shape", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(preferences), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const body = {
      items: [
        {
          event_type: "billing.budget.alerted" as const,
          email: false,
          webhook: false,
          in_app: true,
          webhook_url: null,
        },
        {
          event_type: "billing.budget.paused" as const,
          email: true,
          webhook: true,
          in_app: false,
          webhook_url: "https://hooks.example.com/opticloud",
        },
      ],
    };

    const result = await putNotificationPreferences("jwt-test", body);

    expect(result.items[1]?.channels).toEqual(["email", "webhook"]);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://localhost:8001/v1/auth/notification-preferences");
    expect(init?.method).toBe("PUT");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer jwt-test");
    expect(init?.body).toBe(JSON.stringify(body));
  });

  it("preserves RFC7807 validation errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          title: "Request failed",
          detail: "webhook_url must use https",
          errors: [
            {
              field_path: "body.items.0.webhook_url",
              value: "http://localhost/hook",
              constraint: "https_public_url",
              remediation_hint_key: "notification.webhook_url.invalid",
            },
          ],
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(
      putNotificationPreferences("jwt-test", {
        items: [
          {
            event_type: "billing.budget.alerted",
            email: true,
            webhook: true,
            in_app: true,
            webhook_url: "http://localhost/hook",
          },
          {
            event_type: "billing.budget.paused",
            email: true,
            webhook: false,
            in_app: true,
            webhook_url: null,
          },
        ],
      }),
    ).rejects.toMatchObject({
      status: 422,
      detail: "webhook_url must use https",
      errors: [
        expect.objectContaining({
          field_path: "body.items.0.webhook_url",
        }),
      ],
    });
  });
});
