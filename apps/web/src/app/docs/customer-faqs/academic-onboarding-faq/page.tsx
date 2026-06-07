/** /docs/customer-faqs/academic-onboarding-faq — scholar-facing FAQ entry. */
import Link from "next/link";

const FAQS = [
  {
    question: "我需要先成为商业 Provider 吗？",
    answer:
      "不需要。学术 onboarding 可以先以人工评审和 attribution 记录开始，正式路由、分成和 SLA 另行启用。",
  },
  {
    question: "我的论文和算法会如何署名？",
    answer:
      "公开 SKU 会按 IP Attribution tier 展示 BibTeX、DOI、license-only 或贡献说明；未审核自研算法不会进入公开目录。",
  },
  {
    question: "课堂计划现在能自动同步 LMS 吗？",
    answer:
      "不能。v1 页面只生成本地 planning summary；Canvas、Moodle、雨课堂、学堂在线等 LMS 集成仍是 v2+ 路线图。",
  },
  {
    question: "学生数据会被 Provider 训练使用吗？",
    answer:
      "不会默认作为 Provider 训练数据。涉及敏感教育或人体数据时，需要走学校伦理、IRB 或等价审批路径。",
  },
];

export default function AcademicOnboardingFAQPage(): JSX.Element {
  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/docs" className="font-semibold">
            OptiCloud Docs
          </Link>
          <Link
            href="/docs/academic-provider-handbook"
            className="text-sm text-primary hover:underline"
          >
            Handbook
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-sm text-muted-foreground">Academic onboarding</p>
        <h1 className="mt-2 text-3xl font-bold">Academic Onboarding FAQ</h1>
        <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
          面向学者、课程教师和 Academic Relations 的常见问题入口。长文源文件仍在
          <code className="mx-1 rounded bg-muted px-1 py-0.5 font-mono text-xs">
            docs/customer-faqs/academic-onboarding-faq.md
          </code>
          维护。
        </p>

        <div className="mt-8 space-y-4">
          {FAQS.map((faq) => (
            <section key={faq.question} className="rounded-md border border-border p-5">
              <h2 className="font-semibold">{faq.question}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{faq.answer}</p>
            </section>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap gap-3 text-sm">
          <Link
            href="/console/classroom"
            className="font-medium text-primary hover:underline"
          >
            打开 Classroom Plan v1 stub
          </Link>
          <Link href="/academic" className="font-medium text-primary hover:underline">
            返回学术合作页
          </Link>
        </div>
      </section>
    </main>
  );
}
