"use client";

/** Landing page (UX-DR8 Page Direction Map: Landing → Direction "Engineer-First / 实证克制"). */
import Link from "next/link";

import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { usePreferredLocale } from "@/components/LocaleProvider";
import { translateWithLocale } from "@/lib/messages";

export default function LandingPage(): JSX.Element {
  const { locale } = usePreferredLocale();
  const t = translateWithLocale(locale);

  return (
    <main className="flex min-h-screen flex-col">
      {/* Header */}
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded bg-primary" />
            <span className="font-semibold text-lg">OptiCloud</span>
          </div>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/algorithms"
              className="text-muted-foreground hover:text-foreground"
            >
              {t("landing.algorithms")}
            </Link>
            <Link
              href="/auth/login"
              className="text-muted-foreground hover:text-foreground"
            >
              {t("landing.login")}
            </Link>
            <Link
              href="/academic"
              className="text-muted-foreground hover:text-foreground"
            >
              {t("landing.academic")}
            </Link>
            <Link
              href="/docs"
              className="text-muted-foreground hover:text-foreground"
            >
              {t("landing.docs")}
            </Link>
            <Link
              href="/pricing"
              className="text-muted-foreground hover:text-foreground"
            >
              {t("landing.pricing")}
            </Link>
            <LanguageSwitcher />
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              {t("landing.signup")}
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="bg-background py-20">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <h1 className="text-balance text-4xl font-bold leading-tight md:text-5xl">
            {t("landing.heroTitle")}
          </h1>
          <p className="mt-3 text-balance text-xl text-muted-foreground md:text-2xl">
            {t("landing.heroSubtitle")}
          </p>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-muted-foreground">
            {t("landing.heroBody")}
            <strong className="text-foreground">{t("landing.heroCost")}</strong>
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 md:flex-row">
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-6 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600"
            >
              {t("landing.signup")} →
            </Link>
            <Link
              href="/algorithms"
              className="min-h-touch rounded-md border border-border px-6 py-3 font-medium hover:bg-muted"
            >
              {t("landing.browseAlgorithms")}
            </Link>
          </div>
        </div>
      </section>

      {/* Hello World preview */}
      <section className="border-t border-border bg-muted py-16">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-balance text-2xl font-semibold">
            {t("landing.helloTitle")}
          </h2>
          <pre className="mt-4 overflow-x-auto rounded-lg bg-background p-4 font-mono text-xs leading-relaxed shadow-sm">
            <code>{`# 1. 注册（手机+邮箱双因素，3 分钟）
curl -X POST https://api.opticloud.cn/v1/auth/signup \\
  -d '{"phone":"+86138...","email":"you@example.com"}'

# 2. 拿到 sk-xxx API Key，立即可用：
curl -X POST https://api.opticloud.cn/v1/optimizations \\
  -H "Authorization: Bearer sk-xxx" \\
  -H "Idempotency-Key: $(uuidgen)" \\
  -d '{"task_type":"lp","minimize":{"c":[1,1]},"st":{"A":[[1,1]],"b":[10]}}'

# 5 秒内返回 200 + 最优解 + 含 Provider 透明的 model_version
`}</code>
          </pre>
        </div>
      </section>

      <footer className="mt-auto border-t border-border bg-background py-6 text-center text-sm text-muted-foreground">
        <p>{t("landing.footer")}</p>
      </footer>
    </main>
  );
}
