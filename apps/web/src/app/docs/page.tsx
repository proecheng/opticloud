/** /docs — product documentation index. */
import Link from "next/link";

import { PublicPageHeader, PublicShell } from "@/components/PublicShell";

const DOC_GROUPS = [
  {
    title: "开始接入",
    summary: "把 API Key、示例请求和 Excel 上传边界先跑通。",
    items: [
      {
        href: "/docs/quickstart",
        label: "Hello World Quickstart",
        task: "5 分钟首个请求",
        description: "继续完成 API Key、Postman 和第一个 LP 求解。",
      },
      {
        href: "/docs/excel-upload-faq",
        label: "Excel 上传常见问题",
        task: "上传前排查格式",
        description: "文件大小、格式和公式处理的当前 v1 边界。",
      },
    ],
  },
  {
    title: "学术合作",
    summary: "确认 Provider onboarding、引用、IP attribution 和课堂计划边界。",
    items: [
      {
        href: "/docs/academic-provider-handbook",
        label: "Academic Provider Handbook",
        task: "学者 Provider 入驻",
        description: "学者 Provider onboarding、IP attribution 和课堂计划边界。",
      },
      {
        href: "/docs/customer-faqs/academic-onboarding-faq",
        label: "Academic Onboarding FAQ",
        task: "合作前 FAQ",
        description: "面向学者的常见问题和人工 cohort 沟通口径。",
      },
    ],
  },
  {
    title: "评估与信任",
    summary: "面向采购、安全和运维评估的公开入口。",
    items: [
      {
        href: "/pricing",
        label: "定价说明",
        task: "估算套餐",
        description: "Free、Starter、Pro、Team、Enterprise 的当前包装假设。",
      },
      {
        href: "/status",
        label: "状态页",
        task: "检查服务状态",
        description: "公开服务状态、事件历史和订阅入口。",
      },
      {
        href: "/security",
        label: "安全披露",
        task: "提交安全问题",
        description: "白帽提交、响应边界和安全联系方式。",
      },
    ],
  },
];

export default function DocsIndexPage(): JSX.Element {
  return (
    <PublicShell active="docs">
      <PublicPageHeader
        eyebrow="Docs"
        title="文档"
        description="按任务选择当前产品内可打开的操作文档、FAQ 和支持页面。公开文档只指向已存在路由，避免评估时遇到空链接。"
        actions={
          <>
            <Link
              href="/docs/quickstart"
              className="inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600"
            >
              快速开始
            </Link>
            <Link
              href="/algorithms"
              className="inline-flex min-h-touch items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              浏览算法
            </Link>
          </>
        }
      />

      <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,0.82fr)_minmax(280px,0.38fr)]">
          <div className="min-w-0 space-y-6">
            {DOC_GROUPS.map((group) => (
              <section key={group.title} className="min-w-0">
                <div className="flex flex-col gap-1 border-b border-border pb-3">
                  <h2 className="text-xl font-semibold">{group.title}</h2>
                  <p className="text-sm text-muted-foreground">{group.summary}</p>
                </div>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  {group.items.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="block min-w-0 rounded-md border border-border bg-background p-4 transition hover:bg-muted focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <span className="block text-xs font-semibold uppercase text-primary">
                        {item.task}
                      </span>
                      <span className="mt-2 block break-words font-medium">{item.label}</span>
                      <span className="mt-2 block text-sm leading-6 text-muted-foreground">
                        {item.description}
                      </span>
                    </Link>
                  ))}
                </div>
              </section>
            ))}
          </div>

          <aside className="min-w-0 rounded-md border border-border bg-muted/30 p-5">
            <h2 className="text-lg font-semibold">推荐阅读顺序</h2>
            <ol className="mt-4 space-y-3 text-sm">
              <li>
                <Link href="/docs/quickstart" className="font-medium text-primary hover:underline">
                  1. 跑通 Quickstart
                </Link>
                <p className="mt-1 text-muted-foreground">先确认 API Key 和首个 LP 请求路径。</p>
              </li>
              <li>
                <Link href="/algorithms" className="font-medium text-primary hover:underline">
                  2. 选择算法与 tier
                </Link>
                <p className="mt-1 text-muted-foreground">从公开 catalog 查看 Provider 和适用任务。</p>
              </li>
              <li>
                <Link href="/pricing" className="font-medium text-primary hover:underline">
                  3. 评估套餐与上线风险
                </Link>
                <p className="mt-1 text-muted-foreground">同步查看状态页和安全披露边界。</p>
              </li>
            </ol>
          </aside>
        </div>
      </section>
    </PublicShell>
  );
}
