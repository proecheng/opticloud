/** API helpers — direct service calls without going through browser. */

const AUTH_URL = process.env.PLAYWRIGHT_AUTH_URL ?? "http://localhost:8001";
const SOLVER_URL = process.env.PLAYWRIGHT_SOLVER_URL ?? "http://localhost:8002";

export interface SignupResult {
  user_id: string;
  jwt_access: string;
  jwt_refresh: string;
  edu_tier: boolean;
}

export interface ApiKeyResult {
  id: string;
  api_key: string;
  prefix: string;
  label: string;
  scope: string[];
}

export async function postSignup(phone: string, email: string): Promise<SignupResult> {
  const res = await fetch(`${AUTH_URL}/v1/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone, email }),
  });
  if (!res.ok) throw new Error(`signup failed: ${res.status} ${await res.text()}`);
  return (await res.json()) as SignupResult;
}

export async function postCreateApiKey(
  jwt: string,
  label: string,
  scope: string[],
): Promise<ApiKeyResult> {
  const res = await fetch(`${AUTH_URL}/v1/auth/api_keys`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${jwt}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ label, scope }),
  });
  if (!res.ok) throw new Error(`api key create failed: ${res.status}`);
  return (await res.json()) as ApiKeyResult;
}

export async function getAlgorithms(): Promise<Array<Record<string, unknown>>> {
  const res = await fetch(`${SOLVER_URL}/v1/algorithms`);
  if (!res.ok) throw new Error(`algorithms list failed: ${res.status}`);
  return (await res.json()) as Array<Record<string, unknown>>;
}
