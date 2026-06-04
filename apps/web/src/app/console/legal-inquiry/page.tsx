"use client";
/** /console/legal-inquiry — Team+ legal inquiry SLA submission (Story 8.C.3). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusCard } from "@opticloud/ui";

import {
  OptiCloudClientError,
  submitLegalInquiry,
  type LegalInquiryCategory,
  type LegalInquiryResponse,
  type LegalInquiryUrgency,
} from "@/lib/api";

const categories: Array<{ value: LegalInquiryCategory; label: string }> = [
  { value: "pipl", label: "PIPL / 个人信息保护" },
  { value: "gdpr", label: "GDPR" },
  { value: "graded_protection", label: "等保 2.0" },
  { value: "data_export", label: "数据出境" },
  { value: "dpa", label: "DPA / 数据处理协议" },
  { value: "license", label: "开源/商业许可" },
  { value: "security", label: "安全与采购审查" },
  { value: "other", label: "其他法务问题" },
];

function normalizeError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    if (err.status === 403) return "当前账号没有 active Team 或 Enterprise 法务问询 SLA。";
    if (err.status === 409) return "该提交凭证已被其他内容使用，请重新提交。";
    return `${err.title}: ${err.detail}`;
  }
  if (err && typeof err === "object" && "title" in err && "detail" in err) {
    const payload = err as { status?: unknown; title?: unknown; detail?: unknown };
    if (payload.status === 403) return "当前账号没有 active Team 或 Enterprise 法务问询 SLA。";
    if (payload.status === 409) return "该提交凭证已被其他内容使用，请重新提交。";
    if (typeof payload.title === "string" && typeof payload.detail === "string") {
      return `${payload.title}: ${payload.detail}`;
    }
  }
  if (err instanceof Error) return err.message;
  return "请求失败";
}

function formatDate(value: string): string {
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function Field({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}): JSX.Element {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={["mt-1 break-words font-medium", mono ? "font-mono text-xs" : ""].join(" ")}>
        {value}
      </dd>
    </div>
  );
}

export default function LegalInquiryPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [category, setCategory] = useState<LegalInquiryCategory>("pipl");
  const [urgency, setUrgency] = useState<LegalInquiryUrgency>("normal");
  const [contactEmail, setContactEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<LegalInquiryResponse | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const validate = (): string | null => {
    const email = contactEmail.trim();
    if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return "请输入有效联系邮箱。";
    if (email.length > 254) return "联系邮箱不能超过 254 个字符。";
    if (companyName.trim().length > 160) return "公司/组织不能超过 160 个字符。";
    if (subject.trim().length < 3) return "请输入至少 3 个字符的主题。";
    if (subject.trim().length > 160) return "主题不能超过 160 个字符。";
    if (message.trim().length < 10) return "请输入至少 10 个字符的问询内容。";
    if (message.trim().length > 4000) return "问询内容不能超过 4000 个字符。";
    return null;
  };

  const clearSensitiveFields = (): void => {
    setContactEmail("");
    setCompanyName("");
    setSubject("");
    setMessage("");
    setUrgency("normal");
    setCategory("pipl");
  };

  const handleSubmit = async (): Promise<void> => {
    if (!jwt) return;
    const validationError = validate();
    if (validationError) {
      setFormError(validationError);
      return;
    }
    setFormError(null);
    setSubmitError(null);
    setLoading(true);
    try {
      const response = await submitLegalInquiry(jwt, {
        category,
        contact_email: contactEmail.trim(),
        company_name: companyName.trim() || null,
        subject: subject.trim(),
        message: message.trim(),
        urgency,
      });
      setResult(response);
      clearSensitiveFields();
    } catch (err) {
      setResult(null);
      setSubmitError(normalizeError(err));
      clearSensitiveFields();
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link href="/console/excel" className="text-muted-foreground hover:text-foreground">
              Excel
            </Link>
            <Link href="/console/providers" className="text-muted-foreground hover:text-foreground">
              Providers
            </Link>
            <Link
              href="/console/routing-history"
              className="text-muted-foreground hover:text-foreground"
            >
              Routing History
            </Link>
            <Link href="/console/legal-inquiry" className="font-medium text-foreground">
              Legal Inquiry
            </Link>
            <Link
              href="/console/audit-logs"
              className="text-muted-foreground hover:text-foreground"
            >
              审计日志
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Team+ 法务问询</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Team 和 Enterprise 用户可提交采购、隐私、数据出境、DPA、许可或安全审查问题，并获得 24h
              首次人工响应 SLA。
            </p>
          </div>
          <StatusCard
            variant="info"
            title="Linear-ready"
            description="提交后生成内部 ticket reference；真实法务意见和外部工单处理由人工流程完成。"
            ariaLabel="legal-inquiry.linear-boundary"
          />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <StatusCard
            variant="warning"
            title="Team+ 权限"
            description="Free、Starter、Pro 或过期订阅不会创建法务问询 SLA ticket。"
            ariaLabel="legal-inquiry.entitlement"
          />
          <StatusCard
            variant="info"
            title="内容边界"
            description="24h 表示首次人工响应期限，不表示最终法律意见或合同审批完成。"
            ariaLabel="legal-inquiry.sla-boundary"
          />
        </aside>

        <section className="space-y-5">
          <div className="rounded-md border border-border bg-background p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium">问题类型</span>
                <select
                  aria-label="问题类型"
                  value={category}
                  onChange={(event) => setCategory(event.target.value as LegalInquiryCategory)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  {categories.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">优先级</span>
                <select
                  aria-label="优先级"
                  value={urgency}
                  onChange={(event) => setUrgency(event.target.value as LegalInquiryUrgency)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  <option value="normal">normal</option>
                  <option value="urgent">urgent</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">联系邮箱</span>
                <input
                  aria-label="联系邮箱"
                  value={contactEmail}
                  onChange={(event) => setContactEmail(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="legal@example.com"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">公司/组织</span>
                <input
                  aria-label="公司/组织"
                  value={companyName}
                  onChange={(event) => setCompanyName(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="可选"
                />
              </label>
            </div>
            <label className="mt-4 block">
              <span className="mb-1 block text-sm font-medium">主题</span>
              <input
                aria-label="主题"
                value={subject}
                onChange={(event) => setSubject(event.target.value)}
                className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="例如：DPA 审查 / 数据出境问题"
              />
            </label>
            <label className="mt-4 block">
              <span className="mb-1 block text-sm font-medium">问询内容</span>
              <textarea
                aria-label="问询内容"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                className="min-h-[160px] w-full resize-y rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="请描述问题背景、采购/合规场景和希望法务协助判断的边界。"
              />
            </label>
            <div className="mt-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <button
                type="button"
                onClick={() => void handleSubmit()}
                disabled={!jwt || loading}
                className="min-h-touch rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "提交中..." : "提交法务问询"}
              </button>
              {formError && <p className="text-sm text-danger">{formError}</p>}
            </div>
          </div>

          {submitError && (
            <StatusCard
              variant="error"
              title="提交失败"
              description={submitError}
              ariaLabel="legal-inquiry.error"
            />
          )}

          {result && (
            <section className="space-y-4 rounded-md border border-border bg-background p-5">
              <div>
                <h2 className="text-lg font-semibold">已受理</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  已生成内部 Linear-ready ticket reference，法务/Customer Success 会在 SLA 截止前首次响应。
                </p>
              </div>
              <dl className="grid gap-3 md:grid-cols-2">
                <Field label="Inquiry ID" value={result.inquiry_id} mono />
                <Field label="Status" value={result.status} />
                <Field label="Ticket" value={result.linear_ticket.reference} mono />
                <Field label="Ticket status" value={result.linear_ticket.status} />
                <Field label="Submitted" value={formatDate(result.submitted_at)} />
                <Field label="SLA due" value={formatDate(result.sla_due_at)} />
              </dl>
            </section>
          )}
        </section>
      </section>
    </main>
  );
}
