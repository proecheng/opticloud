import { afterEach, describe, expect, it, vi } from "vitest";

import { LOCALE_COOKIE_NAME } from "@/i18n/locales";

import { listAPIKeys, revokeAPIKey, signup } from "./api";

describe("signup API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("sends age fields and returns completed signup", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user_id: "98cf1268-30d3-4f25-9a1f-f167b441d000",
          jwt_access: "jwt-access",
          jwt_refresh: "jwt-refresh",
          edu_tier: false,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await signup({
      phone: "+8613800138000",
      email: "adult@example.com",
      age_years: 18,
    });

    expect("jwt_access" in result).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8001/v1/auth/signup",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchMock.mock.calls[0]!;
    expect(init?.body).toBe(
      JSON.stringify({
        phone: "+8613800138000",
        email: "adult@example.com",
        age_years: 18,
      }),
    );
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("zh-CN");
  });

  it("returns pending guardian consent response for 202", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          status: "guardian_consent_required",
          request_id: "b26a756e-2294-4cc3-a764-9ef289f4c100",
          expires_in_seconds: 86400,
          guardian_email: "parent@example.com",
          dev_guardian_consent_token: "dev-token",
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await signup({
      phone: "+8613800138001",
      email: "minor@example.com",
      age_years: 16,
      guardian_email: "parent@example.com",
    });

    expect(result).toEqual({
      status: "guardian_consent_required",
      request_id: "b26a756e-2294-4cc3-a764-9ef289f4c100",
      expires_in_seconds: 86400,
      guardian_email: "parent@example.com",
      dev_guardian_consent_token: "dev-token",
    });
  });

  it("sends saved locale preference as Accept-Language", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          user_id: "98cf1268-30d3-4f25-9a1f-f167b441d001",
          jwt_access: "jwt-access",
          jwt_refresh: "jwt-refresh",
          edu_tier: false,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("document", {
      cookie: `${LOCALE_COOKIE_NAME}=en-US`,
    });

    await signup({
      phone: "+8613800138002",
      email: "adult-en@example.com",
      age_years: 18,
    });

    const [, init] = fetchMock.mock.calls[0]!;
    expect(new Headers(init?.headers).get("Accept-Language")).toBe("en-US");
  });

  it("returns API key geo anomaly fields and handles 204 revoke", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            {
              id: "0e850493-eaa5-48a9-89a8-aae3e1c33c11",
              prefix: "sk-abc",
              label: "prod",
              description: null,
              scope: ["optimize:write"],
              expires_at: null,
              last_used_at: "2026-05-23T00:00:00Z",
              last_used_ip: "139.59.10.10",
              last_used_geo_bucket: "SG-SG",
              geo_risk_score: 0.35,
              geo_anomaly_at: "2026-05-23T00:01:00Z",
              geo_anomaly: {
                previous_geo_bucket: "CN-BJ",
                current_geo_bucket: "SG-SG",
                previous_geo_label_zh: "中国北京",
                current_geo_label_zh: "新加坡",
                previous_ip: "101.6.6.6",
                current_ip: "139.59.10.10",
                geo_risk_score: 0.35,
                detected_at: "2026-05-23T00:01:00Z",
                detector_version: "geo-risk-v1",
              },
              revoked_at: null,
              created_at: "2026-05-23T00:00:00Z",
            },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const keys = await listAPIKeys("jwt-access");
    expect(keys[0]?.geo_anomaly?.current_geo_bucket).toBe("SG-SG");

    await expect(revokeAPIKey("jwt-access", "0e850493-eaa5-48a9-89a8-aae3e1c33c11")).resolves.toBe(
      undefined,
    );
    expect(fetchMock).toHaveBeenLastCalledWith(
      "http://localhost:8001/v1/auth/api_keys/0e850493-eaa5-48a9-89a8-aae3e1c33c11",
      expect.objectContaining({ method: "DELETE" }),
    );
  });
});
