/** Auth service API client (Story 1.1a + 1.1b).
 *
 * Calls auth-service via fetch; surfaces RFC 7807 errors with errors[] preserved.
 */

const AUTH_SERVICE_URL =
  process.env.NEXT_PUBLIC_AUTH_SERVICE_URL ?? "http://localhost:8001";

const SOLVER_SERVICE_URL =
  process.env.NEXT_PUBLIC_SOLVER_SERVICE_URL ?? "http://localhost:8002";

const BILLING_SERVICE_URL =
  process.env.NEXT_PUBLIC_BILLING_SERVICE_URL ?? "http://localhost:8003";

export interface SignupRequest {
  phone: string;
  email: string;
}

export interface SignupResponse {
  user_id: string;
  jwt_access: string;
  jwt_refresh: string;
  edu_tier: boolean;
}

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
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": "zh-CN",
      ...(init.headers ?? {}),
    },
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

  return (await response.json()) as T;
}

// ===== Auth =====

export async function signup(body: SignupRequest): Promise<SignupResponse> {
  return request<SignupResponse>("/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export interface APIKeyCreateRequest {
  label: string;
  description?: string;
  scope: string[];
  expires_at?: string;
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
}

export async function listAlgorithms(): Promise<Algorithm[]> {
  return request<Algorithm[]>("/v1/algorithms", {}, SOLVER_SERVICE_URL);
}

// ===== Optimizations (Story 3.1) =====

export interface LPRequest {
  task_type: "lp";
  minimize?: { c: number[] };
  maximize?: { c: number[] };
  st: { A: number[][]; b: number[]; x_lower?: number[]; x_upper?: number[] };
  options?: { max_solve_seconds?: number; reproducible?: boolean };
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
}

// ===== Billing (Story 5.A.1) =====

export interface BalanceResponse {
  user_id: string;
  balance: string;
  currency: string;
  last_transaction_at: string | null;
}

export interface ChargeResponse {
  charge_id: string;
  current_state: string;
  amount: string;
  currency: string;
  balance_before: string;
  balance_after: string;
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
