/** /docs/quickstart — Story 1.8 onboarding support entry. */
import Link from "next/link";

export default function QuickstartPage(): JSX.Element {
  return (
    <main className="mx-auto min-h-screen max-w-3xl px-6 py-12">
      <Link href="/welcome" className="text-sm text-primary hover:underline">
        ← 返回 onboarding
      </Link>

      <h1 className="mt-4 text-3xl font-bold">Hello World Quickstart</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        这份速查用于 onboarding 中断时继续完成 API Key、Postman 和第一个 LP 求解。
      </p>

      <ol className="mt-8 space-y-5">
        <li className="rounded-md border border-border bg-background p-4">
          <h2 className="font-semibold">1. 复制 API Key</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            注册后在欢迎页保存完整 API Key。完整值只展示一次，后续只显示 masked prefix。
          </p>
        </li>
        <li className="rounded-md border border-border bg-background p-4">
          <h2 className="font-semibold">2. 导入 Postman</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            在注册成功弹窗点击「导入 Postman」，下载集合后导入 Postman 工作区。
          </p>
        </li>
        <li className="rounded-md border border-border bg-background p-4">
          <h2 className="font-semibold">3. 跑通第一个 LP</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            回到欢迎页点击「试跑 LP 求解」。看到「求解完成」和 objective 后，wizard 会标记完成。
          </p>
        </li>
      </ol>

      <Link
        href="/welcome"
        className="mt-8 inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
      >
        回到欢迎页继续
      </Link>
    </main>
  );
}
