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
}

export class OptiCloudClientError extends Error {
  status: number;
  title: string;
  detail: string;
  errors: ApiError["errors"];
  next_action_url?: string;
  constructor(payload: ApiError) {
    super(`[${payload.status}] ${payload.title}: ${payload.detail}`);
    this.status = payload.status;
    this.title = payload.title;
    this.detail = payload.detail;
    this.errors = payload.errors;
    this.next_action_url = payload.next_action_url;
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
      const body = (await response.json()) as Partial<ApiError>;
      payload = {
        status: response.status,
        title: body.title ?? "Unknown Error",
        detail: body.detail ?? "Request failed",
        errors: body.errors,
        next_action_url: body.next_action_url,
      };
    } catch {
      payload = {
        status: response.status,
        title: "Network Error",
        detail: await response.text().catch(() => "无法解析错误响应"),
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
  options?: { max_solve_seconds?: number; reproducible?: boolean };
  /** Story 2.4 — FR C4 explicit solver enum. */
  solver?: string;
  /** Story 2.5 — FR C5 ordered fallback solvers (≤3); execution in Story 2.7. */
  fallback_chain?: string[];
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
}

export interface ReproductionRerunResponse extends OptimizationResponse {
  rerun_of_voucher_id: string;
  source_optimization_id: string;
  archive_restore?: {
    mode: "live_solver_image_reuse";
    status: "used";
    detail: string;
  };
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

export async function postOptimization(
  apiKey: string,
  body: LPRequest,
): Promise<OptimizationResponse> {
  const idempotencyKey =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return request<OptimizationResponse>(
    "/v1/optimizations",
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
