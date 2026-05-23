// @vitest-environment happy-dom
/** Story 1.11 — API Keys geo-anomaly warning UI tests. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  listAPIKeys: vi.fn(),
  revokeAPIKey: vi.fn(),
  createApiKey: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

vi.mock("@/lib/api", () => ({
  OptiCloudClientError: class OptiCloudClientError extends Error {
    status = 400;
    title = "Bad Request";
    detail = "Request failed";
  },
  createApiKey: mocks.createApiKey,
  listAPIKeys: mocks.listAPIKeys,
  revokeAPIKey: mocks.revokeAPIKey,
}));

import APIKeysPage from "./page";

const flaggedKey = {
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
};

describe("APIKeysPage geo anomaly warning", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.listAPIKeys.mockReset();
    mocks.revokeAPIKey.mockReset();
    mocks.createApiKey.mockReset();
    sessionStorage.clear();
    sessionStorage.setItem("jwt_access", "jwt-access");
  });

  it("renders, dismisses, reopens, and revokes a geo-anomaly key", async () => {
    mocks.listAPIKeys.mockResolvedValue([flaggedKey]);
    mocks.revokeAPIKey.mockResolvedValue(undefined);

    render(<APIKeysPage />);

    expect(await screen.findByTestId("geo-anomaly-modal")).toBeTruthy();
    expect(screen.getByText(/API Key 出现异常地理使用/)).toBeTruthy();

    fireEvent.click(screen.getByTestId("geo-anomaly-dismiss"));
    await waitFor(() => {
      expect(screen.queryByTestId("geo-anomaly-modal")).toBeNull();
    });

    fireEvent.click(screen.getByTestId(`geo-anomaly-open-${flaggedKey.id}`));
    expect(await screen.findByTestId("geo-anomaly-modal")).toBeTruthy();

    fireEvent.click(screen.getByTestId("geo-anomaly-revoke"));
    await waitFor(() => {
      expect(mocks.revokeAPIKey).toHaveBeenCalledWith("jwt-access", flaggedKey.id);
    });
  });
});
