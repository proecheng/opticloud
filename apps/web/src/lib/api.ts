/** Auth service API client (Story 1.1a + 1.1b).
 *
 * Calls auth-service via fetch; surfaces RFC 7807 errors with errors[] preserved.
 */

import { getClientLocale } from "@/i18n/locales";

const AUTH_SERVICE_URL =
  process.env.NEXT_PUBLIC_AUTH_SERVICE_URL ?? "http://localhost:8001";

const SOLVER_SERVICE_URL =
  process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL ?? "http://localhost:8002";

const BILLING_SERVICE_URL =
  process.env.NEXT_PUBLIC_BILLING_SERVICE_URL ?? "http://localhost:8003";

const CAPABILITY_REGISTRY_URL =
  process.env.NEXT_PUBLIC_CAPABILITY_REGISTRY_URL ?? "http://localhost:8006";

const FALLBACK_ERROR_MESSAGES = {
  requestFailed: {
    remediationHintKey: "errors.fallback.request_failed",
    title: "Request failed",
    detail: "Request failed",
  },
  networkError: {
    remediationHintKey: "errors.fallback.network_error",
    title: "Network Error",
    detail: "无法解析错误响应",
  },
} as const;

export interface SignupRequest {
  phone: string;
  email: string;
  age_years: number;
  guardian_email?: string;
  guardian_consent_request_id?: string;
  guardian_consent_token?: string;
}

export interface SignupResponse {
  user_id: string;
  jwt_access: string;
  jwt_refresh: string;
  edu_tier: boolean;
}

export interface GuardianConsentPendingResponse {
  status: "guardian_consent_required";
  request_id: string;
  expires_in_seconds: number;
  guardian_email: string;
  dev_guardian_consent_token: string | null;
}

export type SignupResult = SignupResponse | GuardianConsentPendingResponse;

export interface ApiError {
  status: number;
  title: string;
  detail: string;
  errors?: Array<{
    field_path: string;
    value: unknown;
    constraint: string;
    remediation_hint_key: string;
  }>;
  next_action_url?: string;
  request_id?: string;
  trace_id?: string;
}

function extractErrorDetail(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) {
    const first = value[0];
    if (first && typeof first === "object" && "msg" in first && typeof first.msg === "string") {
      return first.msg;
    }
    return JSON.stringify(value);
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return FALLBACK_ERROR_MESSAGES.requestFailed.detail;
}

function normalizeErrorPayload(status: number, body: unknown): ApiError {
  const payload = body && typeof body === "object" ? (body as Record<string, unknown>) : {};
  return {
    status,
    title:
      typeof payload.title === "string"
        ? payload.title
        : FALLBACK_ERROR_MESSAGES.requestFailed.title,
    detail: extractErrorDetail(payload.detail),
    errors: Array.isArray(payload.errors)
      ? (payload.errors as ApiError["errors"])
      : undefined,
    next_action_url:
      typeof payload.next_action_url === "string" ? payload.next_action_url : undefined,
    request_id: typeof payload.request_id === "string" ? payload.request_id : undefined,
    trace_id: typeof payload.trace_id === "string" ? payload.trace_id : undefined,
  };
}

export class OptiCloudClientError extends Error {
  status: number;
  title: string;
  detail: string;
  errors: ApiError["errors"];
  next_action_url?: string;
  request_id?: string;
  trace_id?: string;
  constructor(payload: ApiError) {
    super(`[${payload.status}] ${payload.title}: ${payload.detail}`);
    this.status = payload.status;
    this.title = payload.title;
    this.detail = payload.detail;
    this.errors = payload.errors;
    this.next_action_url = payload.next_action_url;
    this.request_id = payload.request_id;
    this.trace_id = payload.trace_id;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  baseUrl: string = AUTH_SERVICE_URL,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept-Language")) {
    headers.set("Accept-Language", getClientLocale());
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    let payload: ApiError;
    try {
      const body = (await response.json()) as unknown;
      payload = normalizeErrorPayload(response.status, body);
    } catch {
      payload = {
        status: response.status,
        title: FALLBACK_ERROR_MESSAGES.networkError.title,
        detail: await response.text().catch(() => FALLBACK_ERROR_MESSAGES.networkError.detail),
        errors: [
          {
            field_path: "response.body",
            value: null,
            constraint: "error response body must be parseable JSON or text",
            remediation_hint_key: FALLBACK_ERROR_MESSAGES.networkError.remediationHintKey,
          },
        ],
      };
    }
    throw new OptiCloudClientError(payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

// ===== Auth =====

export async function signup(body: SignupRequest): Promise<SignupResult> {
  return request<SignupResult>("/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface APIKeyCreateRequest {
  label: string;
  description?: string;
  scope: string[];
  expires_at?: string;
  expires_in_days?: number; // Story 1.3 — convenience; mutually exclusive with expires_at
}

export interface APIKeyCreateResponse {
  id: string;
  api_key: string;
  prefix: string;
  hash_preview: string;
  label: string;
  scope: string[];
  expires_at?: string;
  created_at: string;
}

export async function createApiKey(
  jwtAccess: string,
  body: APIKeyCreateRequest,
): Promise<APIKeyCreateResponse> {
  return request<APIKeyCreateResponse>("/v1/auth/api_keys", {
    method: "POST",
    headers: { Authorization: `Bearer ${jwtAccess}` },
    body: JSON.stringify(body),
  });
}

// ===== Catalog (Story 2.1 — public, no auth) =====

export interface ModelVersion {
  provider_id: string;
  kind: "self" | "open_source" | "external" | "commercial";
  version: string;
  provider_url: string;
}

/** Story 6.A.1 — FR R5 academic citation (BibTeX + UI hints). */
export interface Citation {
  bibtex: string;
  authors_label_zh: string;
  year: number;
  venue: string;
  doi: string | null;
  url: string | null;
}

/** Story 6.A.5 — scholar / license IP attribution tier. */
export interface IPAttribution {
  tier: "L1" | "L2" | "L3";
  label_zh: string;
  display_name_zh: string;
  summary_zh: string;
  visibility: "full_visible" | "bibtex" | "license_only";
  contract_anchor: string;
}

/** Story 6.B.1 — opt-in reproducibility handoff for voucher minting. */
export interface Reproducibility {
  requested: true;
  request_fingerprint: string;
  locked_model_version: ModelVersion;
  locked_solver: string;
  seed_locked: boolean;
  seed: number | null;
  /** Present only when `options.anonymous: true` for blind review. */
  anonymous?: true;
  /** Present only for authenticated persisted reproducible runs. */
  voucher_id?: string;
}

export interface Algorithm {
  k_algo: string;
  task_type: string;
  tier: string;
  status: string;
  model_version: ModelVersion;
  description_zh: string;
  description_en: string;
  examples: Array<{
    name: string;
    input: Record<string, unknown>;
    description: string;
  }>;
  /** Story 2.4 — FR C4 solver enum names valid for this algorithm. */
  supported_solvers: string[];
  /** Story 6.A.1 — FR R5 academic citation; null reserved for commercial-only SKUs. */
  citation: Citation | null;
  /** Story 6.A.5 — L1/L2/L3 IP attribution display metadata. */
  ip_attribution: IPAttribution;
}

export interface ListAlgorithmsOptions {
  taskType?: string;
  /** Story 2.3 — comma-joined server-side; FR C3 OR semantics across tiers. */
  tier?: string[];
}

export async function listAlgorithms(
  options: ListAlgorithmsOptions = {},
): Promise<Algorithm[]> {
  const params = new URLSearchParams();
  if (options.taskType) params.set("task_type", options.taskType);
  if (options.tier && options.tier.length > 0) {
    params.set("tier", options.tier.join(","));
  }
  const qs = params.toString();
  const path = qs ? `/v1/algorithms?${qs}` : "/v1/algorithms";
  return request<Algorithm[]>(path, {}, SOLVER_SERVICE_URL);
}

export async function getAlgorithm(kAlgo: string): Promise<Algorithm> {
  return request<Algorithm>(
    `/v1/algorithms/${encodeURIComponent(kAlgo)}`,
    {},
    SOLVER_SERVICE_URL,
  );
}

// ===== Optimizations (Story 3.1) =====

export interface LPRequest {
  task_type: "lp";
  minimize?: { c: number[] };
  maximize?: { c: number[] };
  st: { A: number[][]; b: number[]; x_lower?: number[]; x_upper?: number[] };
  options?: {
    max_solve_seconds?: number;
    reproducible?: boolean;
    anonymous?: boolean;
    backtest?: boolean;
  };
  /** Story 2.4 — FR C4 explicit solver enum. */
  solver?: string;
  /** Story 2.5 — FR C5 ordered fallback solvers (≤3); execution in Story 2.7. */
  fallback_chain?: string[];
}

export interface TeachingMetadata {
  mode: "teaching";
  principle_explanation: {
    title_zh: string;
    summary_zh: string;
    modeling_steps_zh: string[];
    limitations_zh: string[];
  };
  credits_discount: {
    kind: "teaching";
    label_zh: "50% Credits 折扣";
    discount_multiplier: 0.5;
  };
  notebook: {
    label_zh: string;
    repo_path: string;
    colab_url: string;
  };
}

export interface RoutingHistoryRoute {
  task_type: string;
  requested_solver: string | null;
  selected_solver: string;
  provider_id: string;
  provider_kind: string;
  provider_url: string;
  routing_reason: string;
}

export interface RoutingHistoryAttempt {
  attempt: number;
  role: "primary" | "fallback";
  requested_solver: string | null;
  selected_solver: string;
  provider_id: string;
  provider_kind: string;
  provider_url: string;
  routing_reason: string;
  status: string;
  retryable: boolean;
  solve_seconds: number;
}

export interface RoutingHistory {
  primary_route: RoutingHistoryRoute | null;
  executed_route: RoutingHistoryRoute | null;
  summary: {
    attempt_count: number;
    fallback_used: boolean;
    terminal_status: string | null;
    terminal_attempt: number | null;
    exhausted: boolean;
    solve_seconds: number;
  };
  attempts: RoutingHistoryAttempt[];
}

export interface OptimizationResponse {
  optimization_id: string;
  status: "completed" | "failed" | "timeout";
  solution: { x: number[] } | null;
  objective: number | null;
  model_version: ModelVersion;
  solve_seconds: number;
  created_at: string;
  completed_at: string;
  citation: Citation | null;
  ip_attribution: IPAttribution | null;
  /** Present only when `options.reproducible: true`; omitted otherwise. */
  reproducibility?: Reproducibility;
  /** Present only for `POST /v1/optimizations?mode=teaching`. */
  teaching?: TeachingMetadata;
  /** Present when provider routing metadata exists for this persisted optimization. */
  routing_history?: RoutingHistory;
}

export interface OptimizationStatusResponse {
  optimization_id: string;
  status: "queued" | "in_progress" | "failed" | "timeout" | "cancelled";
  model_version: ModelVersion | null;
  created_at: string;
  completed_at: string | null;
  progress_pct: number | null;
  eta_seconds: number | null;
  mode?: string;
  message?: string;
  error?: Record<string, unknown> | null;
  solve_seconds?: number;
  best_solution_available?: boolean;
  best_solution?: { x: number[] };
  objective?: number;
  refund_status?: string;
  routing_history?: RoutingHistory;
  teaching?: TeachingMetadata;
}

export type GetOptimizationResponse = OptimizationResponse | OptimizationStatusResponse;

export interface ReproductionRerunResponse extends OptimizationResponse {
  rerun_of_voucher_id: string;
  source_optimization_id: string;
  archive_restore?: {
    mode: "live_solver_image_reuse";
    status: "used";
    detail: string;
  };
}

export type PredictionFamily = "arima" | "chronos";

export interface PredictionRequest {
  family: PredictionFamily;
  data: number[];
  horizon: number;
}

export interface PredictionQuantiles {
  p10: number[];
  p50: number[];
  p90: number[];
}

export interface PredictionDisclaimer {
  zh: "本预测仅供参考";
  en: "This forecast is for reference only";
  bilingual: "本预测仅供参考 / This forecast is for reference only";
}

export interface PredictionResponse {
  prediction_id: string;
  status: "completed";
  family: string;
  horizon: number;
  prediction: PredictionQuantiles;
  drift_score: number;
  disclaimer: PredictionDisclaimer;
  model_version: ModelVersion;
  predict_seconds: number;
  created_at: string;
  completed_at: string;
}

// ===== Job templates (Story 5.D.3) =====

export type JobTemplateSourceKind = "optimization" | "prediction";
export type JobTemplatePayloadSchemaVersion =
  | "optimization_request_v1"
  | "prediction_request_v1";

export interface JobTemplateCreateRequest {
  name: string;
  description?: string;
  source_kind: JobTemplateSourceKind;
  source_id: string;
}

export interface JobTemplateSummary {
  id: string;
  name: string;
  description: string | null;
  source_kind: JobTemplateSourceKind;
  source_id: string;
  task_type: string;
  payload_schema_version: JobTemplatePayloadSchemaVersion;
  payload_sha256: string;
  version: number;
  root_template_id: string;
  parent_template_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobTemplateDetail extends JobTemplateSummary {
  payload_json: Record<string, unknown>;
}

export interface JobTemplateListResponse {
  items: JobTemplateSummary[];
}

export interface JobTemplateVersionCreateRequest {
  parameter_path: string;
  value: unknown;
  description?: string;
}

export interface JobTemplateVersionsResponse {
  items: JobTemplateSummary[];
}

export async function createJobTemplate(
  apiKey: string,
  body: JobTemplateCreateRequest,
): Promise<JobTemplateDetail> {
  return request<JobTemplateDetail>(
    "/v1/job-templates",
    {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify(body),
    },
    SOLVER_SERVICE_URL,
  );
}

export async function listJobTemplates(apiKey: string): Promise<JobTemplateListResponse> {
  return request<JobTemplateListResponse>(
    "/v1/job-templates",
    { headers: { Authorization: `Bearer ${apiKey}` } },
    SOLVER_SERVICE_URL,
  );
}

export async function getJobTemplate(
  apiKey: string,
  templateId: string,
): Promise<JobTemplateDetail> {
  return request<JobTemplateDetail>(
    `/v1/job-templates/${encodeURIComponent(templateId)}`,
    { headers: { Authorization: `Bearer ${apiKey}` } },
    SOLVER_SERVICE_URL,
  );
}

export async function deleteJobTemplate(apiKey: string, templateId: string): Promise<void> {
  await request<unknown>(
    `/v1/job-templates/${encodeURIComponent(templateId)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${apiKey}` },
    },
    SOLVER_SERVICE_URL,
  );
}

export async function createJobTemplateVersion(
  apiKey: string,
  templateId: string,
  body: JobTemplateVersionCreateRequest,
): Promise<JobTemplateDetail> {
  return request<JobTemplateDetail>(
    `/v1/job-templates/${encodeURIComponent(templateId)}/versions`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify(body),
    },
    SOLVER_SERVICE_URL,
  );
}

export async function listJobTemplateVersions(
  apiKey: string,
  templateId: string,
): Promise<JobTemplateVersionsResponse> {
  return request<JobTemplateVersionsResponse>(
    `/v1/job-templates/${encodeURIComponent(templateId)}/versions`,
    { headers: { Authorization: `Bearer ${apiKey}` } },
    SOLVER_SERVICE_URL,
  );
}

// ===== Login (Story 1.2 — OTP 2FA) =====

export interface OTPRequestBody {
  phone: string;
  email: string;
}

export interface OTPRequestResponse {
  expires_in_seconds: number;
  factors: ("phone" | "email")[];
  dev_phone_otp: string | null;
  dev_email_otp: string | null;
}

export interface LoginRequest extends OTPRequestBody {
  phone_otp: string;
  email_otp: string;
}

export interface FrozenAppealStartRequest extends OTPRequestBody {}

export interface FrozenAppealRiskSummary {
  total_flag_count: number;
  latest_rule_codes: string[];
  latest_flag_at: string | null;
  risk_score: number;
}

export interface FrozenAppealProposalRequest {
  tracking_token: string;
  duplicate_user_ids: string[];
  reason: string;
  contact_email: string;
  supporting_note?: string | null;
  team_size?: number | null;
}

export type FrozenAppealNextAction =
  | "submit_proposal"
  | "await_review"
  | "accept_merge"
  | "completed"
  | "contact_support";

export interface FrozenAppealStartResponse {
  appeal_id: string;
  status: "started" | "proposal_submitted" | "accepted" | "expired";
  user_id: string;
  tracking_token: string;
  tracking_url: string;
  expires_at: string;
  risk_summary: FrozenAppealRiskSummary;
  proposal: AccountMergeProposalResponse | null;
  next_action: FrozenAppealNextAction;
}

export interface FrozenAppealStatusResponse {
  appeal_id: string;
  status: "started" | "proposal_submitted" | "accepted" | "expired";
  expires_at: string;
  last_viewed_at: string | null;
  risk_summary: FrozenAppealRiskSummary;
  proposal: AccountMergeProposalResponse | null;
  next_action: FrozenAppealNextAction;
}

export interface FrozenAppealAcceptRequest {
  tracking_token: string;
}

export interface FrozenAppealAcceptResponse extends FrozenAppealStatusResponse {}

export async function requestOTP(body: OTPRequestBody): Promise<OTPRequestResponse> {
  return request<OTPRequestResponse>(
    "/v1/auth/otp/request",
    { method: "POST", body: JSON.stringify(body) },
    AUTH_SERVICE_URL,
  );
}

export async function login(body: LoginRequest): Promise<SignupResponse> {
  return request<SignupResponse>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify(body) },
    AUTH_SERVICE_URL,
  );
}

export async function startFrozenAppeal(
  body: FrozenAppealStartRequest,
): Promise<FrozenAppealStartResponse> {
  return request<FrozenAppealStartResponse>(
    "/v1/auth/frozen-appeals/start",
    { method: "POST", body: JSON.stringify(body) },
    AUTH_SERVICE_URL,
  );
}

export async function getFrozenAppeal(
  appealId: string,
  trackingToken: string,
): Promise<FrozenAppealStatusResponse> {
  const params = new URLSearchParams({ tracking_token: trackingToken });
  return request<FrozenAppealStatusResponse>(
    `/v1/auth/frozen-appeals/${encodeURIComponent(appealId)}?${params.toString()}`,
    {},
    AUTH_SERVICE_URL,
  );
}

export async function submitFrozenAppealProposal(
  appealId: string,
  body: FrozenAppealProposalRequest,
): Promise<FrozenAppealStatusResponse> {
  return request<FrozenAppealStatusResponse>(
    `/v1/auth/frozen-appeals/${encodeURIComponent(appealId)}/proposal`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    AUTH_SERVICE_URL,
  );
}

export async function acceptFrozenAppeal(
  appealId: string,
  body: FrozenAppealAcceptRequest,
): Promise<FrozenAppealAcceptResponse> {
  return request<FrozenAppealAcceptResponse>(
    `/v1/auth/frozen-appeals/${encodeURIComponent(appealId)}/accept`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    AUTH_SERVICE_URL,
  );
}

// ===== Account deletion (Story 1.6 — PIPL) =====

export interface AccountDeletionStatusResponse {
  status: "none" | "scheduled" | "completed";
  user_id_snapshot: string | null;
  requested_at: string | null;
  hard_delete_at: string | null;
  completed_at: string | null;
  grace_period_days: number;
}

export async function getAccountDeletionStatus(
  jwtAccess: string,
): Promise<AccountDeletionStatusResponse> {
  return request<AccountDeletionStatusResponse>(
    "/v1/auth/account-deletion",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    AUTH_SERVICE_URL,
  );
}

export async function requestAccountDeletion(
  jwtAccess: string,
): Promise<AccountDeletionStatusResponse> {
  return request<AccountDeletionStatusResponse>(
    "/v1/auth/account-deletion",
    {
      method: "POST",
      headers: { Authorization: `Bearer ${jwtAccess}` },
    },
    AUTH_SERVICE_URL,
  );
}

// ===== Notification preferences (Story 5.D.6) =====

export type NotificationPreferenceEventType =
  | "billing.budget.alerted"
  | "billing.budget.paused"
  | "status.incident.published";

export type NotificationPreferenceChannel = "email" | "webhook" | "in_app";

export interface NotificationPreferenceItem {
  event_type: NotificationPreferenceEventType;
  email: boolean;
  webhook: boolean;
  in_app: boolean;
  webhook_url: string | null;
  webhook_url_configured: boolean;
  channels: NotificationPreferenceChannel[];
}

export interface NotificationPreferencesResponse {
  items: NotificationPreferenceItem[];
}

export interface NotificationPreferenceUpdateItem {
  event_type: NotificationPreferenceEventType;
  email: boolean;
  webhook: boolean;
  in_app: boolean;
  webhook_url?: string | null;
}

export interface NotificationPreferencesUpdateRequest {
  items: NotificationPreferenceUpdateItem[];
}

export async function getNotificationPreferences(
  jwtAccess: string,
): Promise<NotificationPreferencesResponse> {
  return request<NotificationPreferencesResponse>(
    "/v1/auth/notification-preferences",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    AUTH_SERVICE_URL,
  );
}

export async function putNotificationPreferences(
  jwtAccess: string,
  body: NotificationPreferencesUpdateRequest,
): Promise<NotificationPreferencesResponse> {
  return request<NotificationPreferencesResponse>(
    "/v1/auth/notification-preferences",
    {
      method: "PUT",
      headers: { Authorization: `Bearer ${jwtAccess}` },
      body: JSON.stringify(body),
    },
    AUTH_SERVICE_URL,
  );
}

// ===== User audit logs (Story 8.A.5) =====

export interface UserAuditLogItem {
  id: string;
  actor: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  created_at: string;
}

export interface UserAuditLogsResponse {
  items: UserAuditLogItem[];
  next_cursor: string | null;
  limit: number;
  from: string;
  to: string;
}

export interface UserAuditLogFilters {
  from?: string | null;
  to?: string | null;
  limit?: number | null;
  cursor?: string | null;
}

function appendNonEmpty(params: URLSearchParams, key: string, value: string | null | undefined): void {
  const trimmed = value?.trim();
  if (trimmed) params.set(key, trimmed);
}

export async function listMyAuditLogs(
  jwtAccess: string,
  filters: UserAuditLogFilters = {},
): Promise<UserAuditLogsResponse> {
  const params = new URLSearchParams();
  appendNonEmpty(params, "from", filters.from);
  appendNonEmpty(params, "to", filters.to);
  if (filters.limit !== undefined && filters.limit !== null) {
    params.set("limit", String(filters.limit));
  }
  appendNonEmpty(params, "cursor", filters.cursor);
  const qs = params.toString();
  return request<UserAuditLogsResponse>(
    qs ? `/v1/me/audit-logs?${qs}` : "/v1/me/audit-logs",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    AUTH_SERVICE_URL,
  );
}

// ===== Data exports (Story 5.C.5 — PIPL self-service portal) =====

export type DataExportFormat = "json" | "csv";
export type DataExportStatus = "queued" | "processing" | "completed" | "failed" | "expired";

export interface DataExportStatusResponse {
  id: string;
  status: DataExportStatus;
  format: DataExportFormat;
  requested_at: string;
  sla_deadline_at: string;
  completed_at: string | null;
  expires_at: string | null;
  download_url: string | null;
  package_sha256: string | null;
  package_bytes: number | null;
  last_error: string | null;
}

export interface DataExportDownload {
  blob: Blob;
  filename: string;
  mediaType: string;
}

export async function requestDataExport(
  jwtAccess: string,
  format: DataExportFormat = "json",
): Promise<DataExportStatusResponse> {
  return request<DataExportStatusResponse>(
    "/v1/auth/data-exports",
    {
      method: "POST",
      headers: { Authorization: `Bearer ${jwtAccess}` },
      body: JSON.stringify({ format }),
    },
    AUTH_SERVICE_URL,
  );
}

export async function getDataExportStatus(
  jwtAccess: string,
  exportId: string,
): Promise<DataExportStatusResponse> {
  return request<DataExportStatusResponse>(
    `/v1/auth/data-exports/${encodeURIComponent(exportId)}`,
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    AUTH_SERVICE_URL,
  );
}

export async function downloadDataExport(
  jwtAccess: string,
  exportStatus: Pick<DataExportStatusResponse, "id" | "format">,
): Promise<DataExportDownload> {
  const response = await fetch(
    `${AUTH_SERVICE_URL}/v1/auth/data-exports/${encodeURIComponent(exportStatus.id)}/download`,
    {
      headers: {
        Authorization: `Bearer ${jwtAccess}`,
        "Accept-Language": getClientLocale(),
      },
    },
  );

  if (!response.ok) {
    let payload: ApiError;
    try {
      payload = normalizeErrorPayload(response.status, (await response.json()) as unknown);
    } catch {
      payload = {
        status: response.status,
        title: "Download unavailable",
        detail:
          response.status === 409
            ? "data export is not completed"
            : response.status === 410
              ? "data export expired"
              : "data export package unavailable",
      };
    }
    throw new OptiCloudClientError(payload);
  }

  const blob = await response.blob();
  const extension = exportStatus.format === "csv" ? "zip" : "json";
  const fallbackType =
    exportStatus.format === "csv" ? "application/zip" : "application/json";
  return {
    blob,
    filename: `opticloud-pipl-data-export-${exportStatus.id}.${extension}`,
    mediaType: response.headers.get("Content-Type") ?? fallbackType,
  };
}

// ===== Account merge (Story 1.7 — FR A7/A8) =====

export interface AccountMergeEvidence {
  reason: string;
  contact_email: string;
  supporting_note?: string | null;
  team_size?: number | null;
}

export interface AccountMergeProposalCreateRequest {
  primary_user_id: string;
  duplicate_user_ids: string[];
  evidence: AccountMergeEvidence;
}

export interface AccountMergeProposalResponse {
  id: string;
  requester_user_id: string;
  primary_user_id: string;
  duplicate_user_ids: string[];
  evidence: Record<string, unknown>;
  status:
    | "pending_review"
    | "approved"
    | "rejected"
    | "auto_approved"
    | "accepted"
    | "cancelled";
  review_mode: "human" | "auto";
  auto_score: number | null;
  review_due_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  decision_reason: string | null;
  accepted_at: string | null;
  created_at: string;
  updated_at: string;
  next_action: string;
}

export async function createAccountMergeProposal(
  jwtAccess: string,
  body: AccountMergeProposalCreateRequest,
): Promise<AccountMergeProposalResponse> {
  return request<AccountMergeProposalResponse>(
    "/v1/auth/account-merge-proposals",
    {
      method: "POST",
      headers: { Authorization: `Bearer ${jwtAccess}` },
      body: JSON.stringify(body),
    },
    AUTH_SERVICE_URL,
  );
}

export async function listAccountMergeProposals(
  jwtAccess: string,
): Promise<AccountMergeProposalResponse[]> {
  return request<AccountMergeProposalResponse[]>(
    "/v1/auth/account-merge-proposals",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    AUTH_SERVICE_URL,
  );
}

export async function acceptAccountMergeProposal(
  jwtAccess: string,
  proposalId: string,
): Promise<AccountMergeProposalResponse> {
  return request<AccountMergeProposalResponse>(
    `/v1/auth/account-merge-proposals/${encodeURIComponent(proposalId)}/accept`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${jwtAccess}` },
    },
    AUTH_SERVICE_URL,
  );
}

// ===== API Keys list + revoke (Story 1.3) =====

export interface APIKeyListItem {
  id: string;
  prefix: string;
  label: string;
  description: string | null;
  scope: string[];
  expires_at: string | null;
  last_used_at: string | null;
  last_used_ip: string | null;
  last_used_geo_bucket: string | null;
  geo_risk_score: number;
  geo_anomaly_at: string | null;
  geo_anomaly: {
    previous_geo_bucket: string | null;
    current_geo_bucket: string | null;
    previous_geo_label_zh: string | null;
    current_geo_label_zh: string | null;
    previous_ip: string | null;
    current_ip: string | null;
    geo_risk_score: number;
    detected_at: string;
    detector_version: string | null;
  } | null;
  revoked_at: string | null;
  created_at: string;
}

export async function listAPIKeys(jwtAccess: string): Promise<APIKeyListItem[]> {
  return request<APIKeyListItem[]>(
    "/v1/auth/api_keys",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    AUTH_SERVICE_URL,
  );
}

export async function revokeAPIKey(jwtAccess: string, keyId: string): Promise<void> {
  await request<unknown>(
    `/v1/auth/api_keys/${encodeURIComponent(keyId)}`,
    {
      method: "DELETE",
      headers: { Authorization: `Bearer ${jwtAccess}` },
    },
    AUTH_SERVICE_URL,
  );
}

// ===== Billing (Story 5.A.1) =====

export interface BucketBalance {
  name: "monthly" | "signup" | "edu" | "topup";
  label_zh: string;
  balance: string;
  expires_hint: string | null;
}

export interface BalanceResponse {
  user_id: string;
  balance: string;
  currency: string;
  last_transaction_at: string | null;
  buckets: BucketBalance[];
}

export interface ChargeResponse {
  charge_id: string;
  current_state: string;
  amount: string;
  currency: string;
  balance_before: string;
  balance_after: string;
}

// Story 5.A.5 — pre-charge guard preview
export interface WarningResponse {
  kind: "balance_low" | "p5_call" | "p5_call_and_balance_low";
  message: string;
  remediation_hint_key: string;
}

export interface EstimateResponse {
  estimated_amount: string;
  currency: string;
  balance: string;
  warnings: WarningResponse[];
  requires_explicit_confirm: boolean;
}

export async function estimateCharge(
  jwtAccess: string,
  body: { purpose: "solve" | "predict" | "chat" | "demo"; max_solve_seconds: number },
): Promise<EstimateResponse> {
  return request<EstimateResponse>(
    "/v1/billing/charges/estimate",
    {
      method: "POST",
      headers: { Authorization: `Bearer ${jwtAccess}` },
      body: JSON.stringify(body),
    },
    BILLING_SERVICE_URL,
  );
}

export async function getBalance(jwtAccess: string): Promise<BalanceResponse> {
  return request<BalanceResponse>(
    "/v1/billing/balance",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    BILLING_SERVICE_URL,
  );
}

export async function createCharge(
  jwtAccess: string,
  body: {
    amount: string;
    purpose: "solve" | "predict" | "chat" | "demo";
    reference_id: string;
    confirmed?: boolean; // 5.A.5 — required true when /estimate had requires_explicit_confirm=true
  },
  idempotencyKey: string,
): Promise<ChargeResponse> {
  return request<ChargeResponse>(
    "/v1/billing/charges",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwtAccess}`,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify({ ...body, currency: "CNY" }),
    },
    BILLING_SERVICE_URL,
  );
}

export async function confirmCharge(
  jwtAccess: string,
  chargeId: string,
): Promise<ChargeResponse> {
  return request<ChargeResponse>(
    `/v1/billing/charges/${chargeId}/confirm`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${jwtAccess}` },
    },
    BILLING_SERVICE_URL,
  );
}

// ===== Legal inquiry (Story 8.C.3 — Team+ legal SLA) =====

export type LegalInquiryCategory =
  | "pipl"
  | "gdpr"
  | "graded_protection"
  | "data_export"
  | "dpa"
  | "license"
  | "security"
  | "other";

export type LegalInquiryUrgency = "normal" | "urgent";

export interface LegalInquiryRequest {
  category: LegalInquiryCategory;
  contact_email: string;
  subject: string;
  message: string;
  company_name?: string | null;
  urgency?: LegalInquiryUrgency;
}

export interface LegalTicketResponse {
  provider: "linear";
  status: "pending";
  reference: string;
}

export interface LegalInquiryResponse {
  inquiry_id: string;
  status: "submitted";
  submitted_at: string;
  sla_due_at: string;
  sla_hours: 24;
  linear_ticket: LegalTicketResponse;
}

function uuidIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  const template = "10000000-1000-4000-8000-100000000000";
  return template.replace(/[018]/g, (char) => {
    const random = Math.floor(Math.random() * 16);
    return (Number(char) ^ (random & (15 >> (Number(char) / 4)))).toString(16);
  });
}

export async function submitLegalInquiry(
  jwtAccess: string,
  body: LegalInquiryRequest,
  idempotencyKey: string = uuidIdempotencyKey(),
): Promise<LegalInquiryResponse> {
  return request<LegalInquiryResponse>(
    "/v1/legal/inquiry",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwtAccess}`,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
    BILLING_SERVICE_URL,
  );
}

// ===== Billing budget (Story 5.D.5) =====

export interface BillingBudgetEventSummary {
  id: string;
  event_type:
    | "billing.budget.configured"
    | "billing.budget.disabled"
    | "billing.budget.alerted"
    | "billing.budget.paused";
  period_start: string;
  period_end: string;
  occurred_at: string;
  budget_amount: string;
  actual_spend: string;
  percent_used: string;
  channels: Array<"email" | "webhook" | "in_app">;
}

export interface BillingBudgetStatusResponse {
  budget_control_id: string | null;
  enabled: boolean;
  status: "not_configured" | "disabled" | "active" | "paused";
  monthly_budget_amount: string | null;
  alert_threshold_ratio: string;
  period_start: string;
  period_end: string;
  actual_spend: string;
  percent_used: string;
  currency: "CNY";
  alert_threshold_reached: boolean;
  paused: boolean;
  paused_at: string | null;
  pause_period_start: string | null;
  recent_events: BillingBudgetEventSummary[];
}

export interface BillingBudgetUpdateRequest {
  monthly_budget_amount?: string;
  enabled?: boolean;
}

export async function getBillingBudget(
  jwtAccess: string,
): Promise<BillingBudgetStatusResponse> {
  return request<BillingBudgetStatusResponse>(
    "/v1/billing/budget",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    BILLING_SERVICE_URL,
  );
}

export async function putBillingBudget(
  jwtAccess: string,
  body: BillingBudgetUpdateRequest,
): Promise<BillingBudgetStatusResponse> {
  return request<BillingBudgetStatusResponse>(
    "/v1/billing/budget",
    {
      method: "PUT",
      headers: { Authorization: `Bearer ${jwtAccess}` },
      body: JSON.stringify(body),
    },
    BILLING_SERVICE_URL,
  );
}

// ===== Billing invoices (Story 5.D.1) =====

export interface BilingualText {
  zh: string;
  en: string;
}

export interface BillingInvoiceSubscription {
  plan_code: string;
  plan_label: string;
  plan_label_zh: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
}

export interface BillingInvoiceLineItem {
  id: string;
  created_at: string;
  kind: string;
  bucket: string;
  label: BilingualText;
  direction: "credit" | "debit";
  direction_label: BilingualText;
  amount: string;
  source_amount: string;
  currency: string;
  details: Record<string, string>;
}

export interface BillingInvoiceUsageSummary {
  window_days: 7 | 30;
  actual_spend: string;
  currency: string;
  label: BilingualText;
}

export interface BillingInvoiceSummary {
  period: string;
  period_start: string;
  period_end: string;
  status: "final" | "provisional";
  status_label: BilingualText;
  net_credit_movement: string;
  actual_spend: string;
  currency: string;
  line_item_count: number;
}

export interface BillingInvoiceListResponse {
  items: BillingInvoiceSummary[];
}

export interface BillingInvoiceResponse extends BillingInvoiceSummary {
  title: BilingualText;
  tax_disclaimer: BilingualText;
  owner_user_id_suffix: string;
  subscription: BillingInvoiceSubscription;
  credit_subtotal: string;
  debit_subtotal: string;
  trend_contract: "invoice_summary";
  usage_summary: BillingInvoiceUsageSummary[];
  line_items: BillingInvoiceLineItem[];
}

export interface BillingInvoiceDownload {
  blob: Blob;
  filename: string;
  mediaType: string;
}

export async function listBillingInvoices(jwtAccess: string): Promise<BillingInvoiceListResponse> {
  return request<BillingInvoiceListResponse>(
    "/v1/billing/invoices",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    BILLING_SERVICE_URL,
  );
}

export async function getBillingInvoice(
  jwtAccess: string,
  period: string,
): Promise<BillingInvoiceResponse> {
  return request<BillingInvoiceResponse>(
    `/v1/billing/invoices/${encodeURIComponent(period)}`,
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    BILLING_SERVICE_URL,
  );
}

export async function downloadBillingInvoicePdf(
  jwtAccess: string,
  period: string,
): Promise<BillingInvoiceDownload> {
  const response = await fetch(
    `${BILLING_SERVICE_URL}/v1/billing/invoices/${encodeURIComponent(period)}/download`,
    {
      headers: {
        Authorization: `Bearer ${jwtAccess}`,
        "Accept-Language": getClientLocale(),
      },
    },
  );

  if (!response.ok) {
    let payload: ApiError;
    try {
      payload = normalizeErrorPayload(response.status, (await response.json()) as unknown);
    } catch {
      payload = {
        status: response.status,
        title: "Invoice download unavailable",
        detail:
          response.status === 404
            ? "invoice is not available"
            : "billing invoice PDF unavailable",
      };
    }
    throw new OptiCloudClientError(payload);
  }

  return {
    blob: await response.blob(),
    filename: `opticloud-invoice-${period}.pdf`,
    mediaType: response.headers.get("Content-Type") ?? "application/pdf",
  };
}

// ===== Billing usage trends (Story 5.D.2) =====

export interface BillingUsageTrendPoint {
  date: string;
  actual_spend: string;
  currency: string;
}

export interface BillingUsageTrendWindow {
  window_days: 7 | 30;
  window_start: string;
  window_end: string;
  label: BilingualText;
  currency: string;
  total_actual_spend: string;
  average_daily_spend: string;
  points: BillingUsageTrendPoint[];
}

export interface BillingUsageTrendsResponse {
  trend_contract: "billing_usage_trends_v1";
  generated_at: string;
  windows: BillingUsageTrendWindow[];
}

export async function getBillingUsageTrends(
  jwtAccess: string,
): Promise<BillingUsageTrendsResponse> {
  return request<BillingUsageTrendsResponse>(
    "/v1/billing/usage-trends",
    { headers: { Authorization: `Bearer ${jwtAccess}` } },
    BILLING_SERVICE_URL,
  );
}

// ===== Optimizations demo (Story 3.E.3 — no auth) =====

export interface DemoOptimizationResponse {
  status: "completed";
  solution: { x: number[] } | null;
  objective: number | null;
  model_version: ModelVersion;
  solve_seconds: number;
  demo: true;
  citation: Citation | null;
  ip_attribution: IPAttribution | null;
  /** Present only when `options.reproducible: true`; omitted otherwise. */
  reproducibility?: Reproducibility;
}

export async function submitOptimizationDemo<TBody extends { task_type: string }>(
  body: TBody,
): Promise<DemoOptimizationResponse> {
  return request<DemoOptimizationResponse>(
    "/v1/optimizations/demo",
    { method: "POST", body: JSON.stringify(body) },
    SOLVER_SERVICE_URL,
  );
}

// ===== Optimizations (Story 3.1) =====

export interface PostOptimizationOptions {
  mode?: "sync" | "teaching";
  idempotencyKey?: string;
}

export async function postOptimization(
  apiKey: string,
  body: LPRequest,
  options: PostOptimizationOptions = {},
): Promise<OptimizationResponse> {
  const idempotencyKey =
    options.idempotencyKey ??
    (typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const params = new URLSearchParams();
  if (options.mode) {
    params.set("mode", options.mode);
  }
  const path = params.size > 0 ? `/v1/optimizations?${params.toString()}` : "/v1/optimizations";
  return request<OptimizationResponse>(
    path,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(body),
    },
    SOLVER_SERVICE_URL,
  );
}

export async function getOptimization(
  apiKey: string,
  optimizationId: string,
): Promise<GetOptimizationResponse> {
  const headers = new Headers({ Authorization: `Bearer ${apiKey}` });
  headers.set("Accept-Language", getClientLocale());
  const response = await fetch(
    `${SOLVER_SERVICE_URL}/v1/optimizations/${encodeURIComponent(optimizationId)}`,
    {
      method: "GET",
      headers,
    },
  );

  if (!response.ok) {
    let payload: ApiError;
    try {
      const body = (await response.json()) as unknown;
      payload = normalizeErrorPayload(response.status, body);
    } catch {
      payload = {
        status: response.status,
        title: FALLBACK_ERROR_MESSAGES.networkError.title,
        detail: await response.text().catch(() => FALLBACK_ERROR_MESSAGES.networkError.detail),
        errors: [
          {
            field_path: "response.body",
            value: null,
            constraint: "error response body must be parseable JSON or text",
            remediation_hint_key: FALLBACK_ERROR_MESSAGES.networkError.remediationHintKey,
          },
        ],
      };
    }
    throw new OptiCloudClientError(payload);
  }

  return (await response.json()) as GetOptimizationResponse;
}

export async function postPrediction(
  apiKey: string,
  body: PredictionRequest,
  idempotencyKey?: string,
): Promise<PredictionResponse> {
  const replayKey =
    idempotencyKey ??
    (typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
  return request<PredictionResponse>(
    "/v1/predictions",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Idempotency-Key": replayKey,
      },
      body: JSON.stringify(body),
    },
    SOLVER_SERVICE_URL,
  );
}

export async function rerunReproductionVoucher(
  apiKey: string,
  voucherId: string,
  idempotencyKey?: string,
): Promise<ReproductionRerunResponse> {
  const replayKey =
    idempotencyKey ??
    (typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`);
  return request<ReproductionRerunResponse>(
    `/v1/reproduce/${encodeURIComponent(voucherId)}/rerun`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Idempotency-Key": replayKey,
      },
    },
    SOLVER_SERVICE_URL,
  );
}

// ===== Provider Console (Story 7.B.9 — read-only aggregate) =====

export type ProviderDashboardScopeSource = "global" | "tenant";
export type ProviderApplicationScopeSource = ProviderDashboardScopeSource | "global_fallback";

export type ProviderApplicationStatus = "draft" | "submitted" | "under_review" | "accepted" | "rejected";
export type ProviderApplicationKind = "self" | "academic" | "partner" | "commercial";

export interface ProviderApplicationResponse {
  id: string;
  tenant_id: string | null;
  application_id: string;
  requested_provider_id: string;
  provider_kind: ProviderApplicationKind;
  display_name: string;
  organization_name: string;
  contact_email: string;
  homepage_url: string | null;
  openapi_url: string;
  openapi_sha256: string;
  image_digest: string;
  cosign_bundle: Record<string, unknown>;
  evaluation_profile: Record<string, unknown>;
  status: ProviderApplicationStatus;
  submitted_at: string | null;
  metadata: Record<string, unknown>;
  scope_source: ProviderApplicationScopeSource;
  created_at: string;
  updated_at: string;
}

export type ProviderRolloutStatus = "draft" | "active" | "paused" | "completed" | "cancelled";
export type ProviderRolloutStage = 0 | 5 | 50 | 100;

export interface ProviderRouteShareStatusCounts {
  draft: number;
  active: number;
  paused: number;
  completed: number;
  cancelled: number;
}

export interface ProviderRouteShareCurrentRollout {
  application_id: string;
  evaluation_id: string;
  run_id: string;
  rollout_id: string;
  status: ProviderRolloutStatus;
  current_stage_percent: ProviderRolloutStage;
  started_at: string | null;
  completed_at: string | null;
  paused_at: string | null;
  cancelled_at: string | null;
  updated_at: string;
  scope_source: ProviderDashboardScopeSource;
}

export interface ProviderRouteShareTimelinePoint {
  application_id: string;
  evaluation_id: string;
  run_id: string;
  rollout_id: string;
  provider_id: string;
  baseline_provider_id: string;
  benchmark_suite: string;
  action: "created" | "advance" | "pause" | "cancel";
  stage_percent: ProviderRolloutStage;
  from_status: ProviderRolloutStatus | null;
  to_status: ProviderRolloutStatus;
  observed_at: string;
  scope_source: ProviderDashboardScopeSource;
}

export interface ProviderRouteShareDashboardResponse {
  provider_id: string;
  tenant_id: string | null;
  from_at: string | null;
  to_at: string | null;
  status_counts: ProviderRouteShareStatusCounts;
  total_rollouts: number;
  highest_current_stage_percent: ProviderRolloutStage;
  current_rollouts: ProviderRouteShareCurrentRollout[];
  timeline: ProviderRouteShareTimelinePoint[];
}

export type ProviderShadowRunStatus = "draft" | "running" | "passed" | "failed" | "cancelled";

export interface ProviderKpiRunStatusCounts {
  draft: number;
  running: number;
  passed: number;
  failed: number;
  cancelled: number;
}

export interface ProviderKpiAggregateMetrics {
  sample_count: number;
  success_count: number;
  failed_count: number;
  timeout_count: number;
  provider_error_count: number;
  success_rate: string;
  average_deviation_ratio: string;
  provider_p95_latency_ms: number;
  baseline_p95_latency_ms: number;
  p95_latency_ratio: string;
}

export interface ProviderKpiRunMetric {
  application_id: string;
  evaluation_id: string;
  run_id: string;
  provider_id: string;
  baseline_provider_id: string;
  benchmark_suite: string;
  status: ProviderShadowRunStatus;
  started_at: string | null;
  ended_at: string | null;
  updated_at: string;
  observed_from: string | null;
  observed_to: string | null;
  coverage_classes: string[];
  coverage_class_counts: Record<string, number>;
  threshold_violations: string[];
  metrics: ProviderKpiAggregateMetrics;
  scope_source: ProviderDashboardScopeSource;
}

export interface ProviderKpiTimelinePoint {
  application_id: string;
  evaluation_id: string;
  run_id: string;
  provider_id: string;
  benchmark_suite: string;
  bucket_start: string;
  metrics: ProviderKpiAggregateMetrics;
  scope_source: ProviderDashboardScopeSource;
}

export interface ProviderKpiDashboardResponse {
  provider_id: string;
  tenant_id: string | null;
  from_at: string | null;
  to_at: string | null;
  run_status_counts: ProviderKpiRunStatusCounts;
  total_runs: number;
  aggregate: ProviderKpiAggregateMetrics;
  rollout_summary: {
    total_rollouts: number;
    highest_current_stage_percent: ProviderRolloutStage;
    status_counts: ProviderRouteShareStatusCounts;
  };
  run_metrics: ProviderKpiRunMetric[];
  timeline: ProviderKpiTimelinePoint[];
}

export type ProviderRevenuePayoutStatus = "pending" | "held" | "paid" | "voided";

export interface ProviderRevenuePayoutStatusCounts {
  pending: number;
  held: number;
  paid: number;
  voided: number;
}

export interface ProviderRevenuePayoutCurrencyTotal {
  currency: string;
  entry_count: number;
  gross_amount: string;
  provider_revenue_amount: string;
  platform_revenue_amount: string;
  pending_payout_amount: string;
  held_payout_amount: string;
  paid_amount: string;
  voided_gross_amount: string;
}

export interface ProviderRevenuePayoutPeriodSummary extends ProviderRevenuePayoutCurrencyTotal {
  period_month: string;
}

export interface ProviderRevenuePayoutEntryRow {
  entry_id: string;
  hook_id: string;
  provider_id: string;
  k_algo: string;
  policy_id: string;
  source_service: string;
  source_event_id: string;
  period_month: string;
  currency: string;
  gross_amount: string;
  provider_share_ratio: string;
  platform_share_ratio: string;
  provider_revenue_amount: string;
  platform_revenue_amount: string;
  status: ProviderRevenuePayoutStatus;
  recognized_at: string;
  scope_source: ProviderDashboardScopeSource;
}

export interface ProviderRevenuePayoutDashboardResponse {
  provider_id: string;
  tenant_id: string | null;
  from_at: string | null;
  to_at: string | null;
  period_month: string | null;
  status: ProviderRevenuePayoutStatus | null;
  k_algo: string | null;
  currency: string | null;
  status_counts: ProviderRevenuePayoutStatusCounts;
  total_entries: number;
  currency_totals: ProviderRevenuePayoutCurrencyTotal[];
  period_summaries: ProviderRevenuePayoutPeriodSummary[];
  entries: ProviderRevenuePayoutEntryRow[];
}

export type ProviderVersionChangeKind = "patch" | "minor" | "major";
export type ProviderVersionUpdateStatus =
  | "draft"
  | "submitted"
  | "under_review"
  | "approved"
  | "rejected"
  | "cancelled";

export interface ProviderVersionUpdateResponse {
  id: string;
  tenant_id: string | null;
  application_id: string;
  version_update_id: string;
  requested_provider_id: string;
  current_version: string;
  proposed_version: string;
  change_kind: ProviderVersionChangeKind;
  openapi_url: string;
  openapi_sha256: string;
  image_digest: string;
  cosign_bundle: Record<string, unknown>;
  sbom_ref: string | null;
  release_notes_ref: string | null;
  status: ProviderVersionUpdateStatus;
  review_notes_ref: string | null;
  submitted_at: string | null;
  reviewed_at: string | null;
  record_version: number;
  metadata: Record<string, unknown>;
  scope_source: ProviderDashboardScopeSource;
  created_at: string;
  updated_at: string;
}

export type ProviderMonthlyRevenueShareBatchStatus =
  | "draft"
  | "reviewed"
  | "approved"
  | "exported"
  | "cancelled";

export interface ProviderMonthlyRevenueShareCurrencyTotal {
  currency: string;
  entry_count: number;
  provider_count: number;
  gross_amount: string;
  provider_revenue_amount: string;
  platform_revenue_amount: string;
  pending_payout_amount: string;
  held_payout_amount: string;
}

export interface ProviderMonthlyRevenueShareBatchResponse {
  id: string;
  tenant_id: string | null;
  batch_id: string;
  period_month: string;
  status: ProviderMonthlyRevenueShareBatchStatus;
  calculated_at: string;
  entry_count: number;
  provider_count: number;
  currency_totals: ProviderMonthlyRevenueShareCurrencyTotal[];
  provider_summaries: Array<Record<string, unknown>>;
  policy_ratio_summaries: Array<Record<string, unknown>>;
  excluded_entries: Array<Record<string, unknown>>;
  source_entry_ids: string[];
  calculation_checksum: string;
  notes_ref: string | null;
  approved_by_ref: string | null;
  record_version: number;
  scope_source: ProviderDashboardScopeSource;
  created_at: string;
  updated_at: string;
}

export interface ProviderConsoleBaseFilters {
  tenantId?: string;
  from?: string;
  to?: string;
}

export interface ProviderApplicationListFilters {
  tenantId?: string;
  requestedProviderId?: string;
  status?: ProviderApplicationStatus;
}

export interface ProviderRevenuePayoutDashboardFilters extends ProviderConsoleBaseFilters {
  periodMonth?: string;
  status?: ProviderRevenuePayoutStatus;
  kAlgo?: string;
  currency?: string;
}

export interface ProviderVersionUpdateListFilters {
  tenantId?: string;
  requestedProviderId?: string;
  status?: ProviderVersionUpdateStatus;
  changeKind?: ProviderVersionChangeKind;
}

export interface ProviderMonthlyBatchListFilters {
  tenantId?: string;
  periodMonth?: string;
  status?: ProviderMonthlyRevenueShareBatchStatus;
  currency?: string;
}

function appendOptional(params: URLSearchParams, key: string, value: string | undefined): void {
  if (value && value.trim() !== "") {
    params.set(key, value.trim());
  }
}

function providerConsolePath(path: string, params: URLSearchParams): string {
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

function providerConsoleHeaders(jwtAccess: string): HeadersInit {
  return { Authorization: `Bearer ${jwtAccess}` };
}

export async function listProviderApplications(
  jwtAccess: string,
  filters: ProviderApplicationListFilters = {},
): Promise<ProviderApplicationResponse[]> {
  const params = new URLSearchParams();
  appendOptional(params, "tenant_id", filters.tenantId);
  appendOptional(params, "requested_provider_id", filters.requestedProviderId);
  appendOptional(params, "status", filters.status);
  return request<ProviderApplicationResponse[]>(
    providerConsolePath("/v1/provider-applications", params),
    { headers: providerConsoleHeaders(jwtAccess) },
    CAPABILITY_REGISTRY_URL,
  );
}

export async function getProviderRouteShareDashboard(
  jwtAccess: string,
  providerId: string,
  filters: ProviderConsoleBaseFilters = {},
): Promise<ProviderRouteShareDashboardResponse> {
  const params = new URLSearchParams();
  appendOptional(params, "tenant_id", filters.tenantId);
  appendOptional(params, "from", filters.from);
  appendOptional(params, "to", filters.to);
  return request<ProviderRouteShareDashboardResponse>(
    providerConsolePath(
      `/v1/providers/${encodeURIComponent(providerId)}/route-share-dashboard`,
      params,
    ),
    { headers: providerConsoleHeaders(jwtAccess) },
    CAPABILITY_REGISTRY_URL,
  );
}

export async function getProviderKpiDashboard(
  jwtAccess: string,
  providerId: string,
  filters: ProviderConsoleBaseFilters = {},
): Promise<ProviderKpiDashboardResponse> {
  const params = new URLSearchParams();
  appendOptional(params, "tenant_id", filters.tenantId);
  appendOptional(params, "from", filters.from);
  appendOptional(params, "to", filters.to);
  return request<ProviderKpiDashboardResponse>(
    providerConsolePath(
      `/v1/providers/${encodeURIComponent(providerId)}/kpi-dashboard`,
      params,
    ),
    { headers: providerConsoleHeaders(jwtAccess) },
    CAPABILITY_REGISTRY_URL,
  );
}

export async function getProviderRevenuePayoutDashboard(
  jwtAccess: string,
  providerId: string,
  filters: ProviderRevenuePayoutDashboardFilters = {},
): Promise<ProviderRevenuePayoutDashboardResponse> {
  const params = new URLSearchParams();
  appendOptional(params, "tenant_id", filters.tenantId);
  appendOptional(params, "from", filters.from);
  appendOptional(params, "to", filters.to);
  appendOptional(params, "period_month", filters.periodMonth);
  appendOptional(params, "status", filters.status);
  appendOptional(params, "k_algo", filters.kAlgo);
  appendOptional(params, "currency", filters.currency);
  return request<ProviderRevenuePayoutDashboardResponse>(
    providerConsolePath(
      `/v1/providers/${encodeURIComponent(providerId)}/revenue-payout-dashboard`,
      params,
    ),
    { headers: providerConsoleHeaders(jwtAccess) },
    CAPABILITY_REGISTRY_URL,
  );
}

export async function listProviderVersionUpdates(
  jwtAccess: string,
  applicationId: string,
  filters: ProviderVersionUpdateListFilters = {},
): Promise<ProviderVersionUpdateResponse[]> {
  const params = new URLSearchParams();
  appendOptional(params, "tenant_id", filters.tenantId);
  appendOptional(params, "requested_provider_id", filters.requestedProviderId);
  appendOptional(params, "status", filters.status);
  appendOptional(params, "change_kind", filters.changeKind);
  return request<ProviderVersionUpdateResponse[]>(
    providerConsolePath(
      `/v1/provider-applications/${encodeURIComponent(applicationId)}/version-updates`,
      params,
    ),
    { headers: providerConsoleHeaders(jwtAccess) },
    CAPABILITY_REGISTRY_URL,
  );
}

export async function listProviderMonthlyRevenueShareBatches(
  jwtAccess: string,
  filters: ProviderMonthlyBatchListFilters = {},
): Promise<ProviderMonthlyRevenueShareBatchResponse[]> {
  const params = new URLSearchParams();
  appendOptional(params, "tenant_id", filters.tenantId);
  appendOptional(params, "period_month", filters.periodMonth);
  appendOptional(params, "status", filters.status);
  appendOptional(params, "currency", filters.currency);
  return request<ProviderMonthlyRevenueShareBatchResponse[]>(
    providerConsolePath("/v1/revenue-share/monthly-batches", params),
    { headers: providerConsoleHeaders(jwtAccess) },
    CAPABILITY_REGISTRY_URL,
  );
}
