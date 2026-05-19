/** /console/excel — 老张 Excel upload surface (Story 3.E.1, FG1.2 / FR E11 v1 entry).
 *
 * 公开免鉴权入口；本 story 仅做"接住文件 + 友好确认"，不解析、不上传后端。
 * 后续 story 接管：3.E.2 task_type detect → 3.E.3-5 模板 → 3.E.6 结果下载.
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  type ExcelRejectReason,
  ExcelDropZone,
  LoadingShimmer,
  StatusCard,
} from "@opticloud/ui";

type ExcelState =
  | { kind: "idle" }
  | { kind: "received"; file: File }
  | { kind: "rejected"; reason: ExcelRejectReason };

function ReceivedCard({ file, onReset }: { file: File; onReset: () => void }): JSX.Element {
  const [phase, setPhase] = useState<"parsing" | "handoff">("parsing");

  useEffect(() => {
    const id = setTimeout(() => setPhase("handoff"), 2000);
    return () => clearTimeout(id);
  }, []);

  const sizeMB = (file.size / 1024 / 1024).toFixed(2);

  return (
    <div className="space-y-3" data-testid="excel-received-card">
      <StatusCard
        variant="ok"
        title="✅ 已收到您的 Excel 文件"
        description={`${file.name} · ${sizeMB} MB`}
        ariaLabel="console.excel.received"
        icon="📊"
      />

      <div className="rounded-md border border-border bg-muted/30 p-4">
        {phase === "parsing" ? (
          <>
            <div className="mb-2 text-sm text-muted-foreground">解析中...</div>
            <LoadingShimmer variant="line" />
            <LoadingShimmer variant="line" />
          </>
        ) : (
          <p className="text-sm text-muted-foreground">
            📋 下一步：3.E.2 将自动识别 task_type（VRPTW / Schedule / Inventory）并跳到对应模板。
            本 story (3.E.1) 仅完成"接住文件 + 友好确认"环节。
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onReset}
        className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        data-testid="excel-reset-button"
      >
        重新选择文件
      </button>
    </div>
  );
}

function RejectedCard({
  reason,
  onReset,
}: {
  reason: ExcelRejectReason;
  onReset: () => void;
}): JSX.Element {
  const title = reason.code === "too_large" ? "文件过大" : "不支持的文件类型";
  const variant = reason.code === "too_large" ? "warning" : "error";

  return (
    <div className="space-y-3" data-testid="excel-rejected-card">
      <StatusCard
        variant={variant}
        title={title}
        description={reason.message}
        ariaLabel={`console.excel.rejected.${reason.code}`}
        icon={reason.code === "too_large" ? "⚠️" : "🚫"}
      />

      {reason.code === "too_large" && (
        <div className="rounded-md border border-border bg-muted/30 p-4 text-sm">
          <p className="mb-2 font-medium">试试这三步：</p>
          <ul className="ml-4 list-disc space-y-1 text-muted-foreground">
            <li>① 删除多余 sheet（保留只参与求解的工作表）</li>
            <li>② 拆分为 2 个 .xlsx（按客户 / 时间段 / 部门拆）</li>
            <li>③ 转 CSV (≤10MB) — 我们也支持 .csv 上传（v1 末）</li>
          </ul>
          <p className="mt-3">
            <Link
              href="/docs/excel-upload-faq"
              className="text-primary hover:underline"
            >
              📖 看教程：如何拆分大 Excel
            </Link>
          </p>
        </div>
      )}

      <button
        type="button"
        onClick={onReset}
        className="min-h-touch rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
        data-testid="excel-reset-button"
      >
        重试
      </button>
    </div>
  );
}

export default function ConsoleExcelPage(): JSX.Element {
  const [state, setState] = useState<ExcelState>({ kind: "idle" });

  const reset = (): void => setState({ kind: "idle" });

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-background">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded bg-primary" />
            <span className="font-semibold">OptiCloud</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/algorithms" className="text-muted-foreground hover:text-foreground">
              算法目录
            </Link>
            <Link
              href="/auth/signup"
              className="min-h-touch rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary-600"
            >
              注册
            </Link>
          </nav>
        </div>
      </header>

      <section className="bg-muted py-12">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h1 className="text-balance text-3xl font-bold">上传 Excel，自动求解</h1>
          <p className="mt-2 text-balance text-muted-foreground">
            适合 VRPTW / 排班 / 库存预测 — 不写代码，拖一下就行（≤5 MB / 50K 行）
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 py-8">
        {state.kind === "idle" && (
          <ExcelDropZone
            onFile={(file) => setState({ kind: "received", file })}
            onReject={(reason) => setState({ kind: "rejected", reason })}
          />
        )}

        {state.kind === "received" && <ReceivedCard file={state.file} onReset={reset} />}

        {state.kind === "rejected" && (
          <RejectedCard reason={state.reason} onReset={reset} />
        )}
      </section>

      <footer className="mt-12 border-t border-border bg-background py-6 text-center text-sm text-muted-foreground">
        <p>
          想用 cURL / Postman / SDK 直接调？{" "}
          <Link href="/algorithms" className="text-primary hover:underline">
            看算法目录 →
          </Link>
        </p>
      </footer>
    </main>
  );
}
