/** Auth helpers — generate randomized E2E test users.
 *
 * All emails carry `e2e-${runId}-` prefix so cleanup script can purge.
 */

import { randomBytes } from "node:crypto";

import { postCreateApiKey, postSignup } from "./api";

// Unique run id (timestamp + random hex) — used as email prefix
export const RUN_ID = `${Date.now().toString(36)}-${randomBytes(3).toString("hex")}`;

export interface RandomUser {
  phone: string;
  email: string;
  jwt: string;
  user_id: string;
  edu_tier: boolean;
}

export function randomPhone(): string {
  // E.164 mainland China format: +86 + 13-19 prefix + 8 digits (crypto random — CR2 fix)
  const prefixes = ["138", "139", "187", "189"];
  const prefix = prefixes[randomBytes(1)[0] % prefixes.length]!;
  // 8 digits from 4 crypto bytes (modulo into 0-99999999 range)
  const buf = randomBytes(4);
  const num = buf.readUInt32BE(0) % 100_000_000;
  return `+86${prefix}${String(num).padStart(8, "0")}`;
}

export function randomEmail(): string {
  const localPart = randomBytes(4).toString("hex");
  return `e2e-${RUN_ID}-${localPart}@example.com`;
}

/** Signup a random E2E test user — returns JWT for subsequent API key creation. */
export async function signupRandomUser(): Promise<RandomUser> {
  const phone = randomPhone();
  const email = randomEmail();
  const result = await postSignup(phone, email);
  return {
    phone,
    email,
    jwt: result.jwt_access,
    user_id: result.user_id,
    edu_tier: result.edu_tier,
  };
}

/** Signup + create API Key in one call — common test setup. */
export async function signupAndCreateApiKey(
  scope: string[] = ["optimize:write"],
): Promise<RandomUser & { api_key: string }> {
  const user = await signupRandomUser();
  const key = await postCreateApiKey(user.jwt, "e2e-test-key", scope);
  return { ...user, api_key: key.api_key };
}
