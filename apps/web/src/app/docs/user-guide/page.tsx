/** /docs/user-guide — HTML user operation manual for the public website. */
import Link from "next/link";

import { PublicPageHeader, PublicShell } from "@/components/PublicShell";

const PRIMARY_STEPS = [
  {
    title: "1. 注册并保存 API Key",
    body: "从首页或右上角进入注册页，填写手机号、邮箱和年龄信息。注册成功后会生成第一个 API Key，完整密钥只展示一次，请在离开页面前保存。",
    href: "/auth/signup",
    action: "进入注册",
  },
  {
    title: "2. 跑通 Hello World",
    body: "打开 quickstart，复制示例请求，或在欢迎页直接点击试跑 LP 求解。返回 objective、solution 和 provider metadata 即表示链路跑通。",
    href: "/docs/quickstart",
    action: "查看 Quickstart",
  },
  {
    title: "3. 选择 API 或 Excel 工作流",
    body: "已有系统集成时优先使用 API；手头是业务表格时进入 Excel 控制台，本地识别任务类型后再确认试跑。",
    href: "/console/excel",
    action: "打开 Excel 控制台",
  },
  {
    title: "4. 核对算法与 Provider",
    body: "在算法目录查看任务类型、tier、Provider、版本和示例输入，确认当前能力是否覆盖你的优化或预测问题。",
    href: "/algorithms",
    action: "浏览算法目录",
  },
];

const WORKFLOWS = [
  {
    title: "API 调用流程",
    points: [
      "准备 API Key，并在请求头设置 Authorization: Bearer sk-xxx。",
      "为写操作添加 Idempotency-Key，避免重试时重复扣费或重复创建任务。",
      "提交任务 JSON 后查看 objective、solution、status 和 provider metadata。",
      "将 request_id、model_version 和 provider 字段写入本地日志，便于复现和审计。",
    ],
  },
  {
    title: "Excel 上传流程",
    points: [
      "优先上传 .xlsx 文件，当前页面会在浏览器内解析，原始文件不直接上传到服务器。",
      "确认系统识别出的任务类型，例如库存预测、排班、路线或线性规划。",
      "检查字段映射和错误提示，必要时回到 Excel 修正 sheet、表头或公式值。",
      "试跑后下载结果，并保留原始文件版本用于后续复查。",
    ],
  },
  {
    title: "采购与评估流程",
    points: [
      "先从文档、算法目录和定价页确认能力、套餐假设和当前限制。",
      "查看状态页了解公开服务状态和事件历史。",
      "查看安全披露页确认漏洞反馈渠道和响应边界。",
      "需要合同、SLA 或正式发票时，走人工沟通和账单确认流程。",
    ],
  },
];

const CONSOLE_ITEMS = [
  ["预测", "/console/predictions", "查看预测任务状态、结果摘要和下载出口。"],
  ["复现", "/console/repro", "用 request_id 或元数据复查历史结果。"],
  ["Providers", "/console/providers", "查看 Provider 能力、健康状态和治理信息。"],
  ["路由历史", "/console/routing-history", "检查任务被路由到哪个 Provider 以及原因。"],
  ["数据导出", "/console/data-exports", "管理可下载的数据导出记录。"],
  ["账单发票", "/console/billing/invoices", "查看账单、发票和当前计费说明。"],
  ["审计日志", "/console/audit-logs", "查看关键账户和控制台操作记录。"],
  ["法律询证", "/console/legal-inquiry", "提交或跟进企业采购中的法务询证。"],
  ["Classroom", "/console/classroom", "规划课堂 cohort 和学术使用场景。"],
];

const TROUBLESHOOTING = [
  {
    problem: "注册后找不到完整 API Key",
    answer: "完整 API Key 只展示一次。如果已经关闭页面，请创建新密钥，并立即保存到团队的密钥管理工具。",
  },
  {
    problem: "Excel 文件无法识别",
    answer: "先确认文件是 .xlsx，大小和 sheet 数量在当前限制内；公式单元格需要先在 Excel 中重算并保存。",
  },
  {
    problem: "结果和预期不一致",
    answer: "记录 request_id、输入文件版本、Provider、model_version 和返回时间，再进入复现页或联系支持人员排查。",
  },
  {
    problem: "需要正式采购材料",
    answer: "先阅读定价、安全披露和状态页。合同、SLA、安全认证、退款和发票条款以人工确认后的正式文件为准。",
  },
];

export default function UserGuidePage(): JSX.Element {
  return (
    <PublicShell active="docs">
      <PublicPageHeader
        eyebrow="User guide"
        title="网站操作说明"
        description="面向首次使用、技术接入、Excel 试跑和采购评估的站内 HTML 操作手册。按顺序完成注册、试跑、算法确认和控制台复查。"
        actions={
          <>
            <Link
              href="/auth/signup"
              className="inline-flex min-h-touch items-center rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600"
            >
              开始注册
            </Link>
            <Link
              href="/docs"
              className="inline-flex min-h-touch items-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium hover:bg-muted"
            >
              返回文档
            </Link>
          </>
        }
      />

      <article className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
          <nav
            aria-label="操作说明目录"
            className="rounded-md border border-border bg-muted/30 p-4 text-sm"
          >
            <p className="font-semibold text-foreground">目录</p>
            <ol className="mt-3 space-y-2 text-muted-foreground">
              <li>
                <a className="hover:text-foreground" href="#start">
                  快速开始
                </a>
              </li>
              <li>
                <a className="hover:text-foreground" href="#workflows">
                  常用流程
                </a>
              </li>
              <li>
                <a className="hover:text-foreground" href="#console">
                  控制台入口
                </a>
              </li>
              <li>
                <a className="hover:text-foreground" href="#troubleshooting">
                  排障与支持
                </a>
              </li>
            </ol>
          </nav>
        </aside>

        <div className="min-w-0 space-y-10">
          <section id="start" className="scroll-mt-24">
            <div className="border-b border-border pb-3">
              <h2 className="text-2xl font-semibold">快速开始</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                如果只是评估网站是否可用，建议按下面四步走完。每一步都保留了可点击入口，方便回到实际页面操作。
              </p>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {PRIMARY_STEPS.map((step) => (
                <section key={step.title} className="rounded-md border border-border bg-background p-5">
                  <h3 className="text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{step.body}</p>
                  <Link
                    href={step.href}
                    className="mt-4 inline-flex min-h-touch items-center rounded-md border border-border px-3 py-2 text-sm font-medium text-primary hover:bg-muted"
                  >
                    {step.action}
                  </Link>
                </section>
              ))}
            </div>
          </section>

          <section id="workflows" className="scroll-mt-24">
            <div className="border-b border-border pb-3">
              <h2 className="text-2xl font-semibold">常用流程</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                API、Excel 和采购评估是当前网站的三条主路径。选择最贴近你现有材料的一条即可。
              </p>
            </div>

            <div className="mt-5 space-y-4">
              {WORKFLOWS.map((workflow) => (
                <section key={workflow.title} className="rounded-md border border-border bg-background p-5">
                  <h3 className="text-lg font-semibold">{workflow.title}</h3>
                  <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
                    {workflow.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          </section>

          <section id="console" className="scroll-mt-24">
            <div className="border-b border-border pb-3">
              <h2 className="text-2xl font-semibold">控制台入口</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                控制台用于查看任务、结果、治理、账单和审计信息。部分页面需要登录或本地开发 token。
              </p>
            </div>

            <div className="mt-5 overflow-hidden rounded-md border border-border">
              <div className="grid grid-cols-[minmax(120px,0.32fr)_minmax(0,1fr)] bg-muted/50 px-4 py-3 text-sm font-semibold">
                <span>入口</span>
                <span>用途</span>
              </div>
              {CONSOLE_ITEMS.map(([label, href, description]) => (
                <div
                  key={href}
                  className="grid grid-cols-[minmax(120px,0.32fr)_minmax(0,1fr)] gap-3 border-t border-border px-4 py-3 text-sm"
                >
                  <Link href={href} className="font-medium text-primary hover:underline">
                    {label}
                  </Link>
                  <p className="min-w-0 leading-6 text-muted-foreground">{description}</p>
                </div>
              ))}
            </div>
          </section>

          <section id="troubleshooting" className="scroll-mt-24">
            <div className="border-b border-border pb-3">
              <h2 className="text-2xl font-semibold">排障与支持</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                遇到问题时，优先保留请求编号、输入版本和页面提示。这样后续复现会更快。
              </p>
            </div>

            <div className="mt-5 grid gap-4 md:grid-cols-2">
              {TROUBLESHOOTING.map((item) => (
                <section key={item.problem} className="rounded-md border border-border bg-background p-5">
                  <h3 className="text-base font-semibold">{item.problem}</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.answer}</p>
                </section>
              ))}
            </div>

            <div className="mt-6 rounded-md border border-border bg-muted/30 p-5">
              <h3 className="text-lg font-semibold">操作前检查清单</h3>
              <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
                <li>已保存 API Key，且没有把密钥提交到代码仓库或截图中。</li>
                <li>已确认算法目录中的任务类型、Provider 和版本符合当前需求。</li>
                <li>Excel 试跑前已备份原始文件，并记录文件版本。</li>
                <li>采购评估时已阅读定价、状态页、安全披露和法律占位说明。</li>
              </ul>
            </div>
          </section>
        </div>
      </article>
    </PublicShell>
  );
}
