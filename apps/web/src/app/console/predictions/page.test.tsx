// @vitest-environment happy-dom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  postPrediction: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    postPrediction: mocks.postPrediction,
  };
});

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children?: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

import ConsolePredictionsPage from "./page";
import { OptiCloudClientError } from "@/lib/api";

function buildCsv(rows = 1000, invalidDataRow?: number): string {
  const lines = ["商品编号,月份,销量"];
  for (let i = 1; i <= rows; i++) {
    const sku = `SKU-${String((i % 30) + 1).padStart(2, "0")}`;
    const month = `2026-${String((i % 12) + 1).padStart(2, "0")}`;
    const value = invalidDataRow === i ? "BAD_VALUE" : String(100 + i);
    lines.push(`${sku},${month},${value}`);
  }
  return lines.join("\n");
}

function uploadCsv(content: string, name = "lina.csv"): void {
  const file = new File([content], name, { type: "text/csv" });
  fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, {
    target: { files: [file] },
  });
}

const successResponse = {
  prediction_id: "1b5205ef-3baa-49c4-b31c-9b1e11e9ef7c",
  status: "completed",
  family: "chronos",
  horizon: 3,
  prediction: {
    p10: [10, 11, 12],
    p50: [12, 13, 14],
    p90: [14, 15, 16],
  },
  drift_score: 0.12,
  disclaimer: {
    zh: "本预测仅供参考",
    en: "This forecast is for reference only",
    bilingual: "本预测仅供参考 / This forecast is for reference only",
  },
  model_version: {
    provider_id: "chronos",
    kind: "open_source",
    version: "mock-v1",
    provider_url: "https://example.com/chronos",
  },
  predict_seconds: 0.03,
  created_at: "2026-05-28T01:00:00Z",
  completed_at: "2026-05-28T01:00:01Z",
};

describe("ConsolePredictionsPage", () => {
  beforeEach(() => {
    mocks.postPrediction.mockReset();
    sessionStorage.clear();
  });

  it("opens recovery modal for row 847 and cancel does not submit", async () => {
    render(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(1000, 847));

    expect((await screen.findByTestId("csv-invalid-card")).textContent).toContain(
      "rows[847].value",
    );
    expect(screen.getByTestId("confirmation-modal")).toBeTruthy();
    expect(screen.getByText("仅替换失败行")).toBeTruthy();
    expect(screen.getByText("全部重试")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "取消" }));

    await waitFor(() => {
      expect(screen.queryByTestId("confirmation-modal")).toBeNull();
    });
    expect(mocks.postPrediction).not.toHaveBeenCalled();
    expect(screen.queryByTestId("prediction-submit")).toBeNull();
  });

  it("replaces only the invalid row, revalidates, and submits without file bytes", async () => {
    mocks.postPrediction.mockResolvedValue(successResponse);
    render(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(1000, 847));
    expect(await screen.findByTestId("confirmation-modal")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("替换行 CSV"), {
      target: { value: "SKU-08,2026-08,8470" },
    });
    fireEvent.click(screen.getByRole("button", { name: "仅替换失败行" }));

    expect((await screen.findByTestId("csv-ready-card")).textContent).toContain("1,000");
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));

    expect((await screen.findByTestId("prediction-result")).textContent).toContain("P10");
    expect(mocks.postPrediction).toHaveBeenCalledWith(
      "sk-test",
      expect.objectContaining({
        family: "chronos",
        horizon: 3,
        data: expect.any(Array),
      }),
      expect.any(String),
    );
    const body = mocks.postPrediction.mock.calls[0]?.[1];
    expect(JSON.stringify(body)).not.toContain("BAD_VALUE");
    expect(JSON.stringify(body)).not.toContain("商品编号");
    expect(sessionStorage.getItem("api_key")).toBeNull();
  });

  it("clears state when the user chooses full retry", async () => {
    render(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(1000, 847));
    expect(await screen.findByTestId("confirmation-modal")).toBeTruthy();

    fireEvent.click(screen.getByTestId("csv-retry-all"));

    expect(await screen.findByTestId("csv-idle-panel")).toBeTruthy();
    expect(screen.queryByTestId("csv-invalid-card")).toBeNull();
  });

  it("renders RFC7807 API errors with field_path preserved", async () => {
    mocks.postPrediction.mockRejectedValue(
      new OptiCloudClientError({
        status: 422,
        title: "Invalid Prediction Data",
        detail: "horizon must be between 1 and 90",
        errors: [
          {
            field_path: "horizon",
            value: 91,
            constraint: "horizon must be between 1 and 90",
            remediation_hint_key: "errors.422.invalid_prediction_data",
          },
        ],
        next_action_url: "https://api.opticloud.cn/docs/errors/prediction-data",
        request_id: "req-abc",
        trace_id: "trace-def",
      }),
    );
    render(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));

    expect((await screen.findByTestId("rfc7807-panel")).textContent).toContain("horizon");
    expect(screen.getByTestId("rfc7807-panel").textContent).toContain(
      "horizon must be between 1 and 90",
    );
  });
});
