// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider } from "@/components/LocaleProvider";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listAPIKeys: vi.fn(),
  revokeAPIKey: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    listAPIKeys: mocks.listAPIKeys,
    revokeAPIKey: mocks.revokeAPIKey,
    createApiKey: vi.fn(),
  };
});

import APIKeysPage from "./page";

const warnedKey = {
  id: "00000000-0000-4000-8000-000000000001",
  prefix: "sk-abc",
  label: "prod",
  description: null,
  scope: ["optimize:write"],
  expires_at: null,
  last_used_at: "2026-05-25T00:00:00Z",
  revoked_at: null,
  created_at: "2026-05-24T00:00:00Z",
  risk_warning: {
    risk_score: 0.7,
    detected_at: "2026-05-25T00:00:00Z",
    previous_geo: { code: "CN-BJ", label_zh: "中国北京" },
    current_geo: { code: "SG", label_zh: "新加坡" },
    previous_ip: "101.6.10.1",
    current_ip: "13.250.1.1",
    reason: "api_key_geo_changed:CN-BJ->SG",
  },
};

describe("APIKeysPage geo risk warning", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listAPIKeys.mockReset();
    mocks.revokeAPIKey.mockReset();
    sessionStorage.clear();
    sessionStorage.setItem("jwt_access", "jwt-test");
  });

  it("shows geo risk modal and revokes the warned key", async () => {
    mocks.listAPIKeys.mockResolvedValue([warnedKey]);
    mocks.revokeAPIKey.mockResolvedValue(undefined);

    render(<APIKeysPage />);

    await waitFor(() => expect(screen.getByText("地理风险")).toBeTruthy());
    fireEvent.click(screen.getByText("地理风险"));

    expect(screen.getByText("检测到 API Key 异常地理调用")).toBeTruthy();
    expect(screen.getByText(/101\.6\.10\.1/)).toBeTruthy();
    expect(screen.getByText(/13\.250\.1\.1/)).toBeTruthy();

    fireEvent.click(screen.getByText("吊销这个 key"));

    await waitFor(() =>
      expect(mocks.revokeAPIKey).toHaveBeenCalledWith("jwt-test", warnedKey.id),
    );
  });

  it("uses English risk copy when locale is en-US", async () => {
    mocks.listAPIKeys.mockResolvedValue([warnedKey]);

    render(
      <LocaleProvider initialLocale="en-US">
        <APIKeysPage />
      </LocaleProvider>,
    );

    await waitFor(() => expect(screen.getByText("Geo risk")).toBeTruthy());
    fireEvent.click(screen.getByText("Geo risk"));

    expect(
      screen.getByText("Unusual API key geography detected"),
    ).toBeTruthy();
    expect(screen.getByText(/This key moved from/)).toBeTruthy();
  });
});
