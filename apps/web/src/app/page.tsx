/** Landing page (UX-DR8 Page Direction Map: Landing → SSR / Direction "Engineer-First / 实证克制"). */
import Link from "next/link";

export default function LandingPage(): JSX.Element {
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
              算法目录
            </Link>
            <Link
              href="/academic"
              className="text-muted-foreground hover:text-foreground"
            >
              学术合作
            </Link>
            <Link href="/docs" className="text-muted-foreground hover:text-foreground">
              文档
            </Link>
            <Link href="/pricing" className="text-muted-foreground hover:text-foreground">
              定价
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              立即注册
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="bg-background py-20">
        <div className="mx-auto max-w-4xl px-6 text-center">
          <h1 className="text-balance text-4xl font-bold leading-tight md:text-5xl">
            让算法走出实验室
          </h1>
          <p className="mt-3 text-balance text-xl text-muted-foreground md:text-2xl">
            让懂业务的工程师 / 数据分析师 5 分钟用上 Gurobi / TimeGPT 级算法
          </p>
          <p className="mx-auto mt-6 max-w-2xl text-balance text-muted-foreground">
            76% 中型企业的工程师手里只有 Excel —— 算法用不起（Gurobi ≥¥5,000/月）、用不动。
            我们让他们用一行 API 跑通过去只有 Gurobi / DataRobot 能做的事。
            <strong className="text-foreground"> 月成本 ¥6 起。</strong>
          </p>

          <div className="mt-10 flex flex-col items-center justify-center gap-3 md:flex-row">
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-6 py-3 font-semibold text-primary-foreground shadow hover:bg-primary-600"
            >
              立即注册 →
            </Link>
            <Link
              href="/algorithms"
              className="min-h-touch rounded-md border border-border px-6 py-3 font-medium hover:bg-muted"
            >
              浏览 8 个算法 →
            </Link>
          </div>
        </div>
      </section>

      {/* Hello World preview */}
      <section className="border-t border-border bg-muted py-16">
        <div className="mx-auto max-w-4xl px-6">
          <h2 className="text-balance text-2xl font-semibold">3 分钟跑通第一个 LP 求解</h2>
          <pre className="mt-4 overflow-x-auto rounded-lg bg-background p-4 font-mono text-xs leading-relaxed shadow-sm">
            <code>{`# 1. 注册（手机+邮箱双因素，3 分钟）
curl -X POST https://api.opticloud.cn/v1/auth/signup \\
  -d '{"phone":"+86138...","email":"you@example.com","age_years":18}'

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
        <p>OptiCloud · M0 Sprint 0 · ✅ J1 Vertical Slice (Story 1.1a + 1.1b)</p>
      </footer>
    </main>
  );
}
