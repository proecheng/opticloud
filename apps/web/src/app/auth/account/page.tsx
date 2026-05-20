/** Account page — Story 1.6 (FR A6 PIPL 7 day deletion). */
"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ConfirmationModal, StatusCard } from "@opticloud/ui";

import {
  type AccountDeletionStatusResponse,
  OptiCloudClientError,
  getAccountDeletionStatus,
  requestAccountDeletion,
} from "@/lib/api";

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function AccountPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [status, setStatus] = useState<AccountDeletionStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
  }, [router]);

  const refresh = useCallback(async () => {
    if (!jwt) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getAccountDeletionStatus(jwt);
      setStatus(result);
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setLoading(false);
    }
  }, [jwt]);

  useEffect(() => {
    if (jwt) void refresh();
  }, [jwt, refresh]);

  const handleDelete = async (): Promise<void> => {
    if (!jwt) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await requestAccountDeletion(jwt);
      setStatus(result);
      sessionStorage.removeItem("jwt_access");
      sessionStorage.removeItem("jwt_refresh");
      sessionStorage.removeItem("user_id");
      sessionStorage.removeItem("edu_tier");
      localStorage.removeItem("jwt_access");
      setConfirmOpen(false);
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const deletionScheduled = status?.status === "scheduled" || status?.status === "completed";

  return (
    <main className="min-h-screen bg-muted p-4">
      <div className="mx-auto max-w-3xl py-10">
        <header className="mb-6">
          <h1 className="text-2xl font-bold">账户设置</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            管理账户合规操作。账户删除会立即停用登录和 API Key，并在 7 天后永久删除身份数据。
          </p>
        </header>

        {error && (
          <div className="mb-4">
            <StatusCard
              variant="error"
              title="账户状态读取失败"
              description={error}
              ariaLabel="account.error"
            />
          </div>
        )}

        {loading ? (
          <div className="rounded-md border border-border bg-background p-6 text-sm text-muted-foreground">
            正在读取账户状态...
          </div>
        ) : (
          <section className="rounded-md border border-border bg-background p-6">
            <div className="mb-5 flex flex-col gap-3 border-b border-border pb-5 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold">账户删除</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  删除请求确认后，账户立即软删除；系统保留审计记录，并在 7 天后执行硬删除。
                </p>
              </div>
              <span
                className={
                  deletionScheduled
                    ? "w-fit rounded bg-warning/10 px-2 py-1 text-xs font-medium text-warning"
                    : "w-fit rounded bg-success/10 px-2 py-1 text-xs font-medium text-success"
                }
              >
                {deletionScheduled ? "删除已排期" : "正常"}
              </span>
            </div>

            <dl className="grid gap-3 text-sm md:grid-cols-2">
              <div>
                <dt className="text-muted-foreground">请求时间</dt>
                <dd className="font-medium">{formatDate(status?.requested_at ?? null)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">计划硬删除时间</dt>
                <dd className="font-medium">{formatDate(status?.hard_delete_at ?? null)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">完成时间</dt>
                <dd className="font-medium">{formatDate(status?.completed_at ?? null)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">宽限期</dt>
                <dd className="font-medium">{status?.grace_period_days ?? 7} 天</dd>
              </div>
            </dl>

            <div className="mt-6">
              <button
                type="button"
                disabled={deletionScheduled || submitting}
                onClick={() => setConfirmOpen(true)}
                className="min-h-touch rounded-md bg-danger px-4 py-2 font-semibold text-white hover:bg-danger/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletionScheduled ? "删除请求已提交" : "删除账户"}
              </button>
            </div>
          </section>
        )}
      </div>

      <ConfirmationModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => void handleDelete()}
        variant="destructive"
        ariaLabel="account.delete.confirm"
        title="确认删除账户"
        description="确认后会立即停用登录和全部 API Key。身份数据将在 7 天后硬删除，审计记录会保留用于合规追踪。"
        confirmLabel={submitting ? "提交中..." : "确认删除"}
        cancelLabel="取消"
      />
    </main>
  );
}
