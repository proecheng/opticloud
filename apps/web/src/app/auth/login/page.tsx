/** Login page — Story 1.2 (FR A1 OTP 双因素).
 *
 * 2-step flow:
 *   Step 1: phone + email → POST /v1/auth/otp/request → server returns dev codes (local dev only)
 *   Step 2: dev shows codes inline; user copies into the OTP input fields → POST /v1/auth/login
 *   Success: JWT stored, redirect to /demo/charge.
 */
"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { RFC7807Panel, StatusCard } from "@opticloud/ui";

import {
  type OTPRequestResponse,
  OptiCloudClientError,
  login,
  requestOTP,
} from "@/lib/api";
import {
  createInitialOnboardingState,
  getOnboardingStorageKey,
  markOnboardingStep,
  safeParseOnboardingState,
  saveOnboardingState,
  shouldResumeOnboardingAfterLogin,
} from "@/lib/onboarding";

type Stage = "credentials" | "otp";

export default function LoginPage(): JSX.Element {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("credentials");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [phoneOtp, setPhoneOtp] = useState("");
  const [emailOtp, setEmailOtp] = useState("");
  const [otpInfo, setOtpInfo] = useState<OTPRequestResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<OptiCloudClientError | null>(null);

  const frozenAppealUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (phone) params.set("phone", phone);
    if (email) params.set("email", email);
    const qs = params.toString();
    return qs ? `/auth/frozen-appeal?${qs}` : "/auth/frozen-appeal";
  }, [email, phone]);

  const isFrozen = error?.status === 403 && error.detail === "account frozen";
  const errorMessage = isFrozen
    ? "账户已冻结，请继续申诉流程"
    : error?.status === 404
      ? "No account found for this phone/email"
      : error?.status === 401
        ? "Invalid or expired OTP, try again"
        : error?.status === 403
          ? "Account frozen, contact support"
          : null;

  const handleRequestOTP = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await requestOTP({ phone, email });
      setOtpInfo(result);
      setStage("otp");
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setError(err);
      } else {
        setError(
          new OptiCloudClientError({
            status: 0,
            title: "Network Error",
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login({
        phone,
        email,
        phone_otp: phoneOtp,
        email_otp: emailOtp,
      });
      // Match signup's session storage AND also write localStorage so /demo/charge can read it
      sessionStorage.setItem("jwt_access", result.jwt_access);
      sessionStorage.setItem("jwt_refresh", result.jwt_refresh);
      sessionStorage.setItem("user_id", result.user_id);
      sessionStorage.setItem("edu_tier", String(result.edu_tier));
      localStorage.setItem("jwt_access", result.jwt_access);
      const params = new URLSearchParams(window.location.search);
      if (shouldResumeOnboardingAfterLogin(params, sessionStorage, result.user_id)) {
        const stored = sessionStorage.getItem(getOnboardingStorageKey(result.user_id));
        const current = stored
          ? safeParseOnboardingState(stored, result.user_id)
          : createInitialOnboardingState(result.user_id);
        saveOnboardingState(
          sessionStorage,
          markOnboardingStep(current, "verify", "complete"),
        );
        router.push("/welcome");
        return;
      }
      router.push("/demo/charge");
    } catch (err) {
      if (err instanceof OptiCloudClientError) {
        setError(err);
      } else {
        setError(
          new OptiCloudClientError({
            status: 0,
            title: "Network Error",
            detail: String((err as Error).message),
          }),
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleResend = (): void => {
    setStage("credentials");
    setOtpInfo(null);
    setPhoneOtp("");
    setEmailOtp("");
    setError(null);
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-background p-8 shadow-lg">
        <header className="mb-6 text-center">
          <h1 className="text-2xl font-bold">登录 OptiCloud</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            手机 + 邮箱 OTP 双因素验证 (FR A1)
          </p>
        </header>

        {error && (
          <div className="mb-4">
            {isFrozen ? (
              <RFC7807Panel
                payload={{
                  title: error.title,
                  status: error.status,
                  detail: error.detail,
                  errors: error.errors,
                  next_action_url: error.next_action_url ?? frozenAppealUrl,
                }}
              />
            ) : errorMessage ? (
              <StatusCard
                variant="error"
                title="登录失败"
                description={errorMessage}
                ariaLabel={`error.login.${error.status}`}
              />
            ) : error.errors && error.errors.length > 0 ? (
              <RFC7807Panel
                payload={{
                  title: error.title,
                  status: error.status,
                  detail: error.detail,
                  errors: error.errors,
                  next_action_url: error.next_action_url,
                }}
              />
            ) : (
              <StatusCard
                variant="error"
                title={error.title}
                description={error.detail}
                ariaLabel={`error.login.${error.status}`}
              />
            )}
          </div>
        )}

        {stage === "credentials" && (
          <form onSubmit={handleRequestOTP} noValidate>
            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="phone" className="mb-1 block text-sm font-medium">
                手机号
              </label>
              <input
                id="phone"
                type="tel"
                required
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+8613800138000"
                autoComplete="tel"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </fieldset>

            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="email" className="mb-1 block text-sm font-medium">
                邮箱
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </fieldset>

            <button
              type="submit"
              disabled={loading || !phone || !email}
              className="min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600 disabled:opacity-50"
            >
              {loading ? "正在发送..." : "发送 OTP →"}
            </button>

            <p className="mt-4 text-center text-xs text-muted-foreground">
              没有账号？{" "}
              <a href="/auth/signup" className="text-primary hover:underline">
                立即注册
              </a>
            </p>
            {isFrozen && (
              <p className="mt-3 text-center text-xs">
                <a
                  href={frozenAppealUrl}
                  className="text-primary hover:underline"
                  data-testid="frozen-appeal-cta"
                >
                  前往冻结申诉
                </a>
              </p>
            )}
          </form>
        )}

        {stage === "otp" && (
          <form onSubmit={handleLogin} noValidate>
            {otpInfo && (otpInfo.dev_phone_otp || otpInfo.dev_email_otp) && (
              <div
                className="mb-4 rounded-md border border-warning/40 bg-warning/10 p-3 text-xs"
                data-testid="login-dev-otps"
              >
                <strong>(dev mode)</strong> phone OTP:{" "}
                <code className="font-mono">{otpInfo.dev_phone_otp}</code> · email OTP:{" "}
                <code className="font-mono">{otpInfo.dev_email_otp}</code>
              </div>
            )}

            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="phone-otp" className="mb-1 block text-sm font-medium">
                手机 OTP
              </label>
              <input
                id="phone-otp"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                required
                value={phoneOtp}
                onChange={(e) => setPhoneOtp(e.target.value.replace(/\D/g, ""))}
                placeholder="6 位数字"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 font-mono focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </fieldset>

            <fieldset className="mb-4" disabled={loading}>
              <label htmlFor="email-otp" className="mb-1 block text-sm font-medium">
                邮箱 OTP
              </label>
              <input
                id="email-otp"
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                required
                value={emailOtp}
                onChange={(e) => setEmailOtp(e.target.value.replace(/\D/g, ""))}
                placeholder="6 位数字"
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 font-mono focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </fieldset>

            <button
              type="submit"
              disabled={loading || phoneOtp.length !== 6 || emailOtp.length !== 6}
              className="min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600 disabled:opacity-50"
            >
              {loading ? "正在登录..." : "登录 →"}
            </button>

            <button
              type="button"
              onClick={handleResend}
              className="mt-2 w-full text-center text-xs text-muted-foreground hover:text-primary"
            >
              重新发送 OTP
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
