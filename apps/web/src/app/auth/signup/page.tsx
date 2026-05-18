/** Signup page — Story 1.1a J1 Vertical Slice 第 1a 段.
 *
 * FR A1: 手机号+邮箱双因素验证（OTP stub — 实际 OTP 在 Story 1.x）
 * FR A9: Onboarding Wizard ≤ 5 步骤（v1 实施 stub: 1 步表单 + 1 步成功页）
 * FR A4: 教育版邮箱白名单自动激活
 */
"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorBoundary, RFC7807Panel, StatusCard } from "@opticloud/ui";

import { OptiCloudClientError, signup } from "@/lib/api";

interface FormState {
  phone: string;
  email: string;
}

export default function SignupPage(): JSX.Element {
  const router = useRouter();
  const [form, setForm] = useState<FormState>({ phone: "", email: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<OptiCloudClientError | null>(null);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await signup({ phone: form.phone, email: form.email });
      // Store JWT in sessionStorage (production: HttpOnly cookie)
      sessionStorage.setItem("jwt_access", result.jwt_access);
      sessionStorage.setItem("jwt_refresh", result.jwt_refresh);
      sessionStorage.setItem("user_id", result.user_id);
      sessionStorage.setItem("edu_tier", String(result.edu_tier));
      router.push("/welcome");
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

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted p-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-background p-8 shadow-lg">
        <header className="mb-6 text-center">
          <h1 className="text-2xl font-bold">注册 OptiCloud</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            3 分钟拿到 API Key，立即跑 Hello World
          </p>
        </header>

        {error && (
          <div className="mb-4">
            {error.errors && error.errors.length > 0 ? (
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
                ariaLabel={`error.signup.${error.status}`}
              />
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <fieldset className="mb-4" disabled={loading}>
            <label htmlFor="phone" className="mb-1 block text-sm font-medium">
              手机号
              <span className="ml-1 text-danger" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="phone"
              type="tel"
              required
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+8613800138000"
              autoComplete="tel"
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              aria-describedby="phone-hint"
            />
            <p id="phone-hint" className="mt-1 text-xs text-muted-foreground">
              E.164 国际格式（+86 开头）
            </p>
          </fieldset>

          <fieldset className="mb-4" disabled={loading}>
            <label htmlFor="email" className="mb-1 block text-sm font-medium">
              邮箱
              <span className="ml-1 text-danger" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="email"
              type="email"
              required
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              placeholder="you@example.com"
              autoComplete="email"
              className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
              aria-describedby="email-hint"
            />
            <p id="email-hint" className="mt-1 text-xs text-muted-foreground">
              .edu / .ac.cn 邮箱自动激活教育版 (Starter 2K/月 永久免费)
            </p>
          </fieldset>

          <button
            type="submit"
            disabled={loading || !form.phone || !form.email}
            className="min-h-touch w-full rounded-md bg-primary px-4 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600 disabled:opacity-50"
          >
            {loading ? "正在注册..." : "立即注册 →"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          注册即同意{" "}
          <a href="/legal/tos" className="text-primary hover:underline">
            服务条款
          </a>{" "}
          +{" "}
          <a href="/legal/privacy" className="text-primary hover:underline">
            隐私政策
          </a>{" "}
          (PIPL 合规)
        </p>
      </div>
    </main>
  );
}
