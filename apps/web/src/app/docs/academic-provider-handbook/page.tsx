/** /docs/academic-provider-handbook — web entry for the academic handbook. */
import Link from "next/link";

const CHECKPOINTS = [
  "确认学者身份、机构邮箱和可公开展示的学术贡献。",
  "记录算法、数据、代码、论文和许可边界，避免把未审核资产发布到公开 SKU。",
  "明确 IP Attribution tier、BibTeX、DOI、provider_url 和 reproducibility voucher 的展示口径。",
  "课堂计划在 v1 只作为人工 cohort planning stub，不自动创建学生账号、LMS 连接或 Credits 分配。",
];

export default function AcademicProviderHandbookPage(): JSX.Element {
  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/docs" className="font-semibold">
            OptiCloud Docs
          </Link>
          <Link href="/academic" className="text-sm text-primary hover:underline">
            学术合作
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-4xl px-6 py-12">
        <p className="text-sm text-muted-foreground">Academic onboarding</p>
        <h1 className="mt-2 text-3xl font-bold">Academic Provider Handbook</h1>
        <p className="mt-3 max-w-3xl text-sm text-muted-foreground">
          本页是产品内可点击入口，汇总学术 Provider onboarding 的执行边界。长文源文件仍在
          <code className="mx-1 rounded bg-muted px-1 py-0.5 font-mono text-xs">
            docs/academic-provider-handbook.md
          </code>
          维护。
        </p>

        <section className="mt-8 rounded-md border border-border bg-background p-5">
          <h2 className="text-lg font-semibold">执行检查点</h2>
          <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-muted-foreground">
            {CHECKPOINTS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="mt-6 rounded-md border border-border bg-muted/40 p-5">
          <h2 className="text-lg font-semibold">相关入口</h2>
          <div className="mt-4 flex flex-wrap gap-3 text-sm">
            <Link
              href="/docs/customer-faqs/academic-onboarding-faq"
              className="font-medium text-primary hover:underline"
            >
              Academic Onboarding FAQ
            </Link>
            <Link href="/console/classroom" className="font-medium text-primary hover:underline">
              Classroom Plan v1 stub
            </Link>
            <Link href="/algorithms" className="font-medium text-primary hover:underline">
              算法目录
            </Link>
          </div>
        </section>
      </section>
    </main>
  );
}
