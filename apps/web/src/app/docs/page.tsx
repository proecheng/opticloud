/** /docs — product documentation index. */
import Link from "next/link";

const DOC_GROUPS = [
  {
    title: "快速开始",
    items: [
      {
        href: "/docs/quickstart",
        label: "Hello World Quickstart",
        description: "继续完成 API Key、Postman 和第一个 LP 求解。",
      },
      {
        href: "/docs/excel-upload-faq",
        label: "Excel 上传常见问题",
        description: "文件大小、格式和公式处理的当前 v1 边界。",
      },
    ],
  },
  {
    title: "学术合作",
    items: [
      {
        href: "/docs/academic-provider-handbook",
        label: "Academic Provider Handbook",
        description: "学者 Provider onboarding、IP attribution 和课堂计划边界。",
      },
      {
        href: "/docs/customer-faqs/academic-onboarding-faq",
        label: "Academic Onboarding FAQ",
        description: "面向学者的常见问题和人工 cohort 沟通口径。",
      },
    ],
  },
  {
    title: "产品与运营",
    items: [
      {
        href: "/pricing",
        label: "定价说明",
        description: "Free、Starter、Pro、Team、Enterprise 的当前包装假设。",
      },
      {
        href: "/status",
        label: "状态页",
        description: "公开服务状态、事件历史和订阅入口。",
      },
      {
        href: "/security",
        label: "安全披露",
        description: "白帽提交、响应边界和安全联系方式。",
      },
    ],
  },
];

export default function DocsIndexPage(): JSX.Element {
  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold">
            OptiCloud
          </Link>
          <Link
            href="/auth/signup"
            className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary-600"
          >
            立即注册
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <h1 className="text-3xl font-bold">文档</h1>
        <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
          选择当前产品内可打开的操作文档、FAQ 和支持页面。
        </p>

        <div className="mt-8 space-y-8">
          {DOC_GROUPS.map((group) => (
            <section key={group.title}>
              <h2 className="text-lg font-semibold">{group.title}</h2>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                {group.items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="block rounded-md border border-border bg-background p-4 transition hover:bg-muted"
                  >
                    <span className="font-medium">{item.label}</span>
                    <span className="mt-2 block text-sm text-muted-foreground">
                      {item.description}
                    </span>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      </section>
    </main>
  );
}
