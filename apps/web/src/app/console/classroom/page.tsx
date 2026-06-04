"use client";
/** /console/classroom — Classroom Plan v1 local planning stub (Story 8.C.7). */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusCard } from "@opticloud/ui";

import {
  buildClassroomPlanDraft,
  type ClassroomLmsProvider,
  type ClassroomPlanDraft,
  type ClassroomPlanValidationErrors,
} from "@/lib/classroom-plan";

const lmsOptions: Array<{ value: ClassroomLmsProvider; label: string }> = [
  { value: "manual_cohort", label: "Manual cohort" },
  { value: "canvas", label: "Canvas" },
  { value: "moodle", label: "Moodle" },
  { value: "yuketang", label: "雨课堂" },
  { value: "xuetangx", label: "学堂在线" },
];

function Field({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-w-0 rounded-md border border-border bg-background p-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 break-words font-medium">{value}</dd>
    </div>
  );
}

function ConsoleNav(): JSX.Element {
  return (
    <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
      <Link href="/console/excel" className="text-muted-foreground hover:text-foreground">
        Excel
      </Link>
      <Link href="/console/providers" className="text-muted-foreground hover:text-foreground">
        Providers
      </Link>
      <Link href="/console/classroom" className="font-medium text-foreground hover:text-primary">
        Classroom
      </Link>
      <Link
        href="/console/routing-history"
        className="text-muted-foreground hover:text-foreground"
      >
        Routing History
      </Link>
      <Link
        href="/console/legal-inquiry"
        className="text-muted-foreground hover:text-foreground"
      >
        Legal Inquiry
      </Link>
      <Link
        href="/console/billing/invoices"
        className="text-muted-foreground hover:text-foreground"
      >
        账单
      </Link>
      <Link href="/console/audit-logs" className="text-muted-foreground hover:text-foreground">
        审计日志
      </Link>
    </nav>
  );
}

function DraftSummary({ draft }: { draft: ClassroomPlanDraft }): JSX.Element {
  return (
    <section className="space-y-4 rounded-md border border-border bg-background p-5">
      <div>
        <h2 className="text-lg font-semibold">Local v1 Classroom Plan stub</h2>
        <p className="mt-1 text-sm text-muted-foreground">{draft.boundaryCopy}</p>
      </div>
      <dl className="grid gap-3 md:grid-cols-2">
        <Field label="Teacher contact / master planning email" value={draft.teacherEmail} />
        <Field label="Course name" value={draft.courseName} />
        <Field label="Student seats" value={String(draft.studentSeats)} />
        <Field
          label="Shared Credits monthly request"
          value={`${draft.sharedCreditsMonthlyRequest} Credits`}
        />
        <Field label="Shared Credits label" value={draft.sharedCreditsLabel} />
        <Field label="LMS provider" value={draft.lms.label} />
        <Field label="LMS status" value={draft.lms.integrationLabel} />
        <Field label="LMS connected" value={`connected=${String(draft.lms.connected)}`} />
        <Field label="Handling mode" value={draft.handlingMode} />
      </dl>
    </section>
  );
}

export default function ClassroomPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [teacherEmail, setTeacherEmail] = useState("");
  const [courseName, setCourseName] = useState("");
  const [studentSeats, setStudentSeats] = useState("25");
  const [sharedCreditsMonthlyRequest, setSharedCreditsMonthlyRequest] = useState("2000");
  const [lmsProvider, setLmsProvider] = useState<ClassroomLmsProvider>("manual_cohort");
  const [errors, setErrors] = useState<ClassroomPlanValidationErrors>({});
  const [draft, setDraft] = useState<ClassroomPlanDraft | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const handleGenerate = (): void => {
    const result = buildClassroomPlanDraft({
      teacherEmail,
      courseName,
      studentSeats,
      sharedCreditsMonthlyRequest,
      lmsProvider,
    });
    if (!result.ok) {
      setErrors(result.errors);
      setDraft(null);
      return;
    }
    setErrors({});
    setDraft(result.draft);
  };

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <ConsoleNav />
        </div>
      </header>

      <section className="border-b border-border bg-muted">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 py-6 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-bold">Classroom Plan v1 stub</h1>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              本页只生成本地 planning summary，用于人工 cohort 沟通；不创建账号、Credits、LMS
              连接、作业或成绩。
            </p>
          </div>
          <StatusCard
            variant="warning"
            title="Local stub only"
            description="Shared Credits 是 manual request / planning estimate，不是钱包余额、账本凭证、发票、赠款或实际分配。"
            ariaLabel="classroom.local-stub-boundary"
          />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[360px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <StatusCard
            variant="info"
            title="v1 manual cohort"
            description="Manual cohort 可人工处理；Canvas、Moodle、雨课堂、学堂在线仅为 foundation/planned。"
            ariaLabel="classroom.manual-cohort"
          />
          <StatusCard
            variant="info"
            title="Docs handoff"
            description="Handbook 和 FAQ 是操作/沟通边界，不是法律审批或合同完成。"
            ariaLabel="classroom.docs-boundary"
          />
        </aside>

        <section className="space-y-5">
          <section className="rounded-md border border-border bg-background p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <label className="block">
                <span className="mb-1 block text-sm font-medium">
                  Teacher contact / master planning email
                </span>
                <input
                  aria-label="Teacher contact / master planning email"
                  value={teacherEmail}
                  onChange={(event) => setTeacherEmail(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="professor@example.edu"
                />
                {errors.teacherEmail && (
                  <p className="mt-1 text-sm text-danger">{errors.teacherEmail}</p>
                )}
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Course name</span>
                <input
                  aria-label="Course name"
                  value={courseName}
                  onChange={(event) => setCourseName(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Optimization 101"
                />
                {errors.courseName && (
                  <p className="mt-1 text-sm text-danger">{errors.courseName}</p>
                )}
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">Student seats</span>
                <input
                  aria-label="Student seats"
                  value={studentSeats}
                  onChange={(event) => setStudentSeats(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  inputMode="numeric"
                  placeholder="5-200"
                />
                {errors.studentSeats && (
                  <p className="mt-1 text-sm text-danger">{errors.studentSeats}</p>
                )}
              </label>
              <label className="block">
                <span className="mb-1 block text-sm font-medium">
                  Shared Credits monthly request
                </span>
                <input
                  aria-label="Shared Credits monthly request"
                  value={sharedCreditsMonthlyRequest}
                  onChange={(event) => setSharedCreditsMonthlyRequest(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  inputMode="numeric"
                  placeholder="0-2000000"
                />
                {errors.sharedCreditsMonthlyRequest && (
                  <p className="mt-1 text-sm text-danger">
                    {errors.sharedCreditsMonthlyRequest}
                  </p>
                )}
              </label>
              <label className="block md:col-span-2">
                <span className="mb-1 block text-sm font-medium">LMS provider</span>
                <select
                  aria-label="LMS provider"
                  value={lmsProvider}
                  onChange={(event) => setLmsProvider(event.target.value as ClassroomLmsProvider)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  {lmsOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                {errors.lmsProvider && (
                  <p className="mt-1 text-sm text-danger">{errors.lmsProvider}</p>
                )}
              </label>
            </div>
            <button
              type="button"
              disabled={!jwt}
              onClick={handleGenerate}
              className="mt-4 min-h-touch rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Generate local Classroom stub
            </button>
          </section>

          {draft && <DraftSummary draft={draft} />}

          <section className="space-y-3 rounded-md border border-border bg-background p-5">
            <h2 className="text-lg font-semibold">v1 manual cohort closure checklist</h2>
            <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
              <li>Confirm teacher contact and future master-owner candidate.</li>
              <li>Course roster collection happens out-of-band; this stub does not accept roster data.</li>
              <li>Students register with education email before any manual cohort handling.</li>
              <li>Manually grant or use existing education quota outside this page.</li>
              <li>No LMS gradebook, assignment sync, SSO launch or course code happens here.</li>
            </ul>
          </section>

          <section className="space-y-3 rounded-md border border-border bg-background p-5">
            <h2 className="text-lg font-semibold">Privacy and ethics boundaries</h2>
            <ul className="list-disc space-y-2 pl-5 text-sm text-muted-foreground">
              <li>Student input belongs to students and is not Provider training data.</li>
              <li>Teacher visibility is progress and submission summary, not default raw data download.</li>
              <li>Sensitive human or education data requires an IRB or school ethics path.</li>
            </ul>
          </section>

          <section className="space-y-3 rounded-md border border-border bg-background p-5">
            <h2 className="text-lg font-semibold">Documentation handoff</h2>
            <p className="text-sm text-muted-foreground">
              These documents define communication boundaries only. They do not approve legal terms,
              shared Credits, LMS integration, contracts or student data processing.
            </p>
            <div className="flex flex-wrap gap-3 text-sm">
              <Link
                href="/docs/academic-provider-handbook"
                className="font-medium text-primary hover:underline"
              >
                Academic Provider Handbook
              </Link>
              <Link
                href="/docs/customer-faqs/academic-onboarding-faq"
                className="font-medium text-primary hover:underline"
              >
                Academic Onboarding FAQ
              </Link>
            </div>
          </section>
        </section>
      </section>
    </main>
  );
}
