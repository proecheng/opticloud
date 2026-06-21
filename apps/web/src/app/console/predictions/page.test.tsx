// @vitest-environment happy-dom

import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test-utils/render-with-intl";

const mocks = vi.hoisted(() => ({
  postPrediction: vi.fn(),
  createJobTemplate: vi.fn(),
  createJobTemplateVersion: vi.fn(),
  listJobTemplateVersions: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    postPrediction: mocks.postPrediction,
    createJobTemplate: mocks.createJobTemplate,
    createJobTemplateVersion: mocks.createJobTemplateVersion,
    listJobTemplateVersions: mocks.listJobTemplateVersions,
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

const versionPredictionResponse = {
  ...successResponse,
  prediction_id: "7da41a49-e6e5-4f55-b591-143ccfbb6013",
  horizon: 6,
  prediction: {
    p10: [20, 21, 22, 23, 24, 25],
    p50: [22, 23, 24, 25, 26, 27],
    p90: [24, 25, 26, 27, 28, 29],
  },
};

const savedTemplate = {
  id: "2c4e9e2a-6bdf-49ef-bf03-12d8ee160bef",
  name: "月度销量模板",
  description: null,
  source_kind: "prediction",
  source_id: successResponse.prediction_id,
  task_type: "forecast",
  payload_schema_version: "prediction_request_v1",
  payload_json: { family: "chronos", data: [1, 2, 3], horizon: 3 },
  payload_sha256: "abc123",
  version: 1,
  root_template_id: "2c4e9e2a-6bdf-49ef-bf03-12d8ee160bef",
  parent_template_id: null,
  created_at: "2026-06-01T01:00:00Z",
  updated_at: "2026-06-01T01:00:00Z",
};

const versionTemplate = {
  ...savedTemplate,
  id: "8e10ea97-2ebb-42ec-a027-960d20fd1b89",
  payload_json: { family: "chronos", data: [1, 2, 3], horizon: 6 },
  payload_sha256: "def456",
  version: 2,
  parent_template_id: savedTemplate.id,
  updated_at: "2026-06-01T01:05:00Z",
};

describe("ConsolePredictionsPage", () => {
  beforeEach(() => {
    mocks.postPrediction.mockReset();
    mocks.createJobTemplate.mockReset();
    mocks.createJobTemplateVersion.mockReset();
    mocks.listJobTemplateVersions.mockReset();
    sessionStorage.clear();
    localStorage.clear();
  });

  it("opens recovery modal for row 847 and cancel does not submit", async () => {
    renderWithIntl(<ConsolePredictionsPage />);

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
    renderWithIntl(<ConsolePredictionsPage />);

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

  it("saves a completed prediction as a job template without resubmitting prediction or storing secrets", async () => {
    mocks.postPrediction.mockResolvedValue(successResponse);
    mocks.createJobTemplate.mockResolvedValue(savedTemplate);
    renderWithIntl(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));
    expect(await screen.findByTestId("prediction-result")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "月度销量模板" },
    });
    fireEvent.click(screen.getByTestId("save-template-button"));

    expect((await screen.findByTestId("template-save-success")).textContent).toContain(
      "月度销量模板",
    );
    expect(mocks.createJobTemplate).toHaveBeenCalledWith("sk-test", {
      name: "月度销量模板",
      description: undefined,
      source_kind: "prediction",
      source_id: successResponse.prediction_id,
    });
    expect(mocks.postPrediction).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem("api_key")).toBeNull();
    expect(JSON.stringify(sessionStorage)).not.toContain("sk-test");
    expect(mocks.createJobTemplateVersion).not.toHaveBeenCalled();
  });

  it("creates a template version, submits returned payload, and keeps original result visible", async () => {
    mocks.postPrediction
      .mockResolvedValueOnce(successResponse)
      .mockResolvedValueOnce(versionPredictionResponse);
    mocks.createJobTemplate.mockResolvedValue(savedTemplate);
    mocks.createJobTemplateVersion.mockResolvedValue(versionTemplate);
    mocks.listJobTemplateVersions.mockResolvedValue({
      items: [
        { ...savedTemplate, payload_json: undefined },
        { ...versionTemplate, payload_json: undefined },
      ],
    });
    renderWithIntl(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));
    expect(await screen.findByTestId("prediction-result")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "月度销量模板" },
    });
    fireEvent.click(screen.getByTestId("save-template-button"));
    expect(await screen.findByTestId("template-save-success")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("新版预测步长"), { target: { value: "6" } });
    fireEvent.click(screen.getByTestId("create-template-version-button"));

    expect((await screen.findByTestId("template-version-success")).textContent).toContain(
      "v2",
    );
    expect(screen.getByTestId("template-version-history").textContent).toContain("v1");
    expect(screen.getByTestId("template-version-history").textContent).toContain("v2");
    expect(screen.getAllByTestId("prediction-result")).toHaveLength(2);
    expect(mocks.createJobTemplateVersion).toHaveBeenCalledWith("sk-test", savedTemplate.id, {
      parameter_path: "horizon",
      value: 6,
    });
    expect(mocks.postPrediction).toHaveBeenNthCalledWith(
      2,
      "sk-test",
      { family: "chronos", data: [1, 2, 3], horizon: 6 },
      expect.any(String),
    );
    expect(mocks.listJobTemplateVersions).toHaveBeenCalledWith("sk-test", savedTemplate.id);
    expect(sessionStorage.getItem("api_key")).toBeNull();
    expect(localStorage.getItem("api_key")).toBeNull();
    expect(JSON.stringify(sessionStorage)).not.toContain("sk-test");
    expect(JSON.stringify(localStorage)).not.toContain("chronos");
  });

  it("shows template version errors without hiding the original prediction result or resubmitting", async () => {
    mocks.postPrediction.mockResolvedValue(successResponse);
    mocks.createJobTemplate.mockResolvedValue(savedTemplate);
    mocks.createJobTemplateVersion.mockRejectedValue(
      new OptiCloudClientError({
        status: 422,
        title: "Invalid Job Template",
        detail: "horizon must be between 1 and 90",
        errors: [
          {
            field_path: "horizon",
            value: 0,
            constraint: "horizon must be between 1 and 90",
            remediation_hint_key: "errors.422.invalid_job_template",
          },
        ],
      }),
    );
    renderWithIntl(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));
    expect(await screen.findByTestId("prediction-result")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "月度销量模板" },
    });
    fireEvent.click(screen.getByTestId("save-template-button"));
    expect(await screen.findByTestId("template-save-success")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("新版预测步长"), { target: { value: "6" } });
    fireEvent.click(screen.getByTestId("create-template-version-button"));

    expect((await screen.findByTestId("template-version-error")).textContent).toContain(
      "Invalid Job Template",
    );
    expect(screen.getByTestId("prediction-result")).toBeTruthy();
    expect(mocks.postPrediction).toHaveBeenCalledTimes(1);
    expect(mocks.listJobTemplateVersions).not.toHaveBeenCalled();
  });

  it("keeps created version metadata visible when the version prediction fails", async () => {
    mocks.postPrediction
      .mockResolvedValueOnce(successResponse)
      .mockRejectedValueOnce(
        new OptiCloudClientError({
          status: 422,
          title: "Invalid Prediction Data",
          detail: "version payload rejected",
          errors: [
            {
              field_path: "horizon",
              value: 6,
              constraint: "horizon rejected by provider",
              remediation_hint_key: "errors.422.invalid_prediction_data",
            },
          ],
        }),
      );
    mocks.createJobTemplate.mockResolvedValue(savedTemplate);
    mocks.createJobTemplateVersion.mockResolvedValue(versionTemplate);
    mocks.listJobTemplateVersions.mockResolvedValue({
      items: [
        { ...savedTemplate, payload_json: undefined },
        { ...versionTemplate, payload_json: undefined },
      ],
    });
    renderWithIntl(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));
    expect(await screen.findByTestId("prediction-result")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "月度销量模板" },
    });
    fireEvent.click(screen.getByTestId("save-template-button"));
    expect(await screen.findByTestId("template-save-success")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("新版预测步长"), { target: { value: "6" } });
    fireEvent.click(screen.getByTestId("create-template-version-button"));

    expect((await screen.findByTestId("template-version-prediction-error")).textContent).toContain(
      "v2",
    );
    expect(screen.getByTestId("template-version-prediction-error").textContent).toContain(
      "Invalid Prediction Data",
    );
    expect(screen.getByTestId("template-version-history").textContent).toContain("v1");
    expect(screen.getByTestId("template-version-history").textContent).toContain("v2");
    expect(screen.getByTestId("prediction-result")).toBeTruthy();
    expect(mocks.postPrediction).toHaveBeenCalledTimes(2);
    expect(mocks.postPrediction).toHaveBeenNthCalledWith(
      2,
      "sk-test",
      { family: "chronos", data: [1, 2, 3], horizon: 6 },
      expect.any(String),
    );
  });

  it("shows template save errors without hiding the prediction result", async () => {
    mocks.postPrediction.mockResolvedValue(successResponse);
    mocks.createJobTemplate.mockRejectedValue(
      new OptiCloudClientError({
        status: 422,
        title: "Source Task Not Completed",
        detail: "source task status is queued, expected completed",
        errors: [
          {
            field_path: "source_id",
            value: successResponse.prediction_id,
            constraint: "source task status must be completed",
            remediation_hint_key: "errors.422.source_task_not_completed",
          },
        ],
      }),
    );
    renderWithIntl(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));
    expect(await screen.findByTestId("prediction-result")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "月度销量模板" },
    });
    fireEvent.click(screen.getByTestId("save-template-button"));

    expect((await screen.findByTestId("template-save-error")).textContent).toContain(
      "Source Task Not Completed",
    );
    expect(screen.getByTestId("prediction-result")).toBeTruthy();
    expect(mocks.postPrediction).toHaveBeenCalledTimes(1);
  });

  it("shows an auth error when saving a template without the API key", async () => {
    mocks.postPrediction.mockResolvedValue(successResponse);
    renderWithIntl(<ConsolePredictionsPage />);

    uploadCsv(buildCsv(12));
    expect(await screen.findByTestId("csv-ready-card")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "sk-test" } });
    fireEvent.click(screen.getByTestId("prediction-submit"));
    expect(await screen.findByTestId("prediction-result")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("API key"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("模板名称"), {
      target: { value: "月度销量模板" },
    });
    fireEvent.click(screen.getByTestId("save-template-button"));

    expect((await screen.findByTestId("template-save-error")).textContent).toContain(
      "Missing API Key",
    );
    expect(mocks.createJobTemplate).not.toHaveBeenCalled();
    expect(mocks.postPrediction).toHaveBeenCalledTimes(1);
  });

  it("clears state when the user chooses full retry", async () => {
    renderWithIntl(<ConsolePredictionsPage />);

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
    renderWithIntl(<ConsolePredictionsPage />);

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
