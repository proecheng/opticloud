/** Account page — Story 1.6 (FR A6 PIPL 7 day deletion). */
"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ConfirmationModal, StatusCard } from "@opticloud/ui";

import {
  type AccountMergeProposalResponse,
  type AccountDeletionStatusResponse,
  type NotificationPreferenceEventType,
  type NotificationPreferenceItem,
  type NotificationPreferencesResponse,
  acceptAccountMergeProposal,
  createAccountMergeProposal,
  getNotificationPreferences,
  OptiCloudClientError,
  getAccountDeletionStatus,
  listAccountMergeProposals,
  putNotificationPreferences,
  requestAccountDeletion,
} from "@/lib/api";

const NOTIFICATION_EVENTS: Array<{
  event_type: NotificationPreferenceEventType;
  label: string;
  defaultEmail: boolean;
  defaultInApp: boolean;
}> = [
  {
    event_type: "billing.budget.alerted",
    label: "预算达到提醒阈值",
    defaultEmail: true,
    defaultInApp: true,
  },
  {
    event_type: "billing.budget.paused",
    label: "预算自动暂停扣费",
    defaultEmail: true,
    defaultInApp: true,
  },
  {
    event_type: "status.incident.published",
    label: "公开 incident 发布",
    defaultEmail: false,
    defaultInApp: false,
  },
];

type NotificationPreferenceFormItem = {
  event_type: NotificationPreferenceEventType;
  email: boolean;
  webhook: boolean;
  in_app: boolean;
  webhook_url: string;
};

function formatDate(value: string | null): string {
  if (!value) return "-";
  return new Date(value).toLocaleString("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function defaultNotificationPreferenceForm(): NotificationPreferenceFormItem[] {
  return NOTIFICATION_EVENTS.map(({ event_type, defaultEmail, defaultInApp }) => ({
    event_type,
    email: defaultEmail,
    webhook: false,
    in_app: defaultInApp,
    webhook_url: "",
  }));
}

function preferencesToForm(
  response: NotificationPreferencesResponse,
): NotificationPreferenceFormItem[] {
  const byEvent = new Map(response.items.map((item) => [item.event_type, item]));
  return NOTIFICATION_EVENTS.map(({ event_type, defaultEmail, defaultInApp }) => {
    const item = byEvent.get(event_type);
    return {
      event_type,
      email: item?.email ?? defaultEmail,
      webhook: item?.webhook ?? false,
      in_app: item?.in_app ?? defaultInApp,
      webhook_url: item?.webhook_url ?? "",
    };
  });
}

function preferenceErrorMessage(error: unknown): string {
  return error instanceof OptiCloudClientError ? `${error.title}: ${error.detail}` : String(error);
}

function eventLabel(eventType: NotificationPreferenceEventType): string {
  return NOTIFICATION_EVENTS.find((event) => event.event_type === eventType)?.label ?? eventType;
}

function enabledChannelsLabel(item: NotificationPreferenceItem): string {
  if (item.channels.length === 0) return "无通知渠道";
  return item.channels
    .map((channel) =>
      channel === "email" ? "邮件" : channel === "webhook" ? "Webhook" : "站内",
    )
    .join("、");
}

export default function AccountPage(): JSX.Element {
  const router = useRouter();
  const [jwt, setJwt] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [status, setStatus] = useState<AccountDeletionStatusResponse | null>(null);
  const [mergeProposals, setMergeProposals] = useState<AccountMergeProposalResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateIds, setDuplicateIds] = useState("");
  const [mergeReason, setMergeReason] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [teamSize, setTeamSize] = useState("2");
  const [notificationPreferences, setNotificationPreferences] =
    useState<NotificationPreferencesResponse | null>(null);
  const [notificationForm, setNotificationForm] = useState<NotificationPreferenceFormItem[]>(
    defaultNotificationPreferenceForm,
  );
  const [notificationLoading, setNotificationLoading] = useState(true);
  const [notificationSaving, setNotificationSaving] = useState(false);
  const [notificationError, setNotificationError] = useState<string | null>(null);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? sessionStorage.getItem("jwt_access") : null;
    const storedUserId = typeof window !== "undefined" ? sessionStorage.getItem("user_id") : null;
    if (!stored) {
      router.push("/auth/login");
      return;
    }
    setJwt(stored);
    setUserId(storedUserId);
  }, [router]);

  const refresh = useCallback(async () => {
    if (!jwt) return;
    setLoading(true);
    setError(null);
    try {
      const [result, proposals] = await Promise.all([
        getAccountDeletionStatus(jwt),
        listAccountMergeProposals(jwt),
      ]);
      setStatus(result);
      setMergeProposals(proposals);
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setLoading(false);
    }
  }, [jwt]);

  useEffect(() => {
    if (jwt) void refresh();
  }, [jwt, refresh]);

  const refreshNotificationPreferences = useCallback(async () => {
    if (!jwt) return;
    setNotificationLoading(true);
    setNotificationError(null);
    try {
      const result = await getNotificationPreferences(jwt);
      setNotificationPreferences(result);
      setNotificationForm(preferencesToForm(result));
    } catch (e) {
      setNotificationError(preferenceErrorMessage(e));
    } finally {
      setNotificationLoading(false);
    }
  }, [jwt]);

  useEffect(() => {
    if (jwt) void refreshNotificationPreferences();
  }, [jwt, refreshNotificationPreferences]);

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

  const handleMergeSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    if (!jwt) return;
    if (!userId) {
      setError("当前登录态缺少 user_id，请重新登录后再提交账户合并提案。");
      return;
    }
    const parsedDuplicateIds = duplicateIds
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    setSubmitting(true);
    setError(null);
    try {
      await createAccountMergeProposal(jwt, {
        primary_user_id: userId,
        duplicate_user_ids: parsedDuplicateIds,
        evidence: {
          reason: mergeReason,
          contact_email: contactEmail,
          team_size: Number(teamSize || "2"),
        },
      });
      setDuplicateIds("");
      setMergeReason("");
      setContactEmail("");
      setTeamSize("2");
      await refresh();
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleAcceptMerge = async (proposalId: string): Promise<void> => {
    if (!jwt) return;
    setSubmitting(true);
    setError(null);
    try {
      await acceptAccountMergeProposal(jwt, proposalId);
      await refresh();
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const updateNotificationForm = (
    eventType: NotificationPreferenceEventType,
    patch: Partial<NotificationPreferenceFormItem>,
  ): void => {
    setNotificationForm((current) =>
      current.map((item) => (item.event_type === eventType ? { ...item, ...patch } : item)),
    );
  };

  const handleNotificationSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    if (!jwt) return;
    setNotificationSaving(true);
    setNotificationError(null);
    try {
      const result = await putNotificationPreferences(jwt, {
        items: notificationForm.map((item) => ({
          event_type: item.event_type,
          email: item.email,
          webhook: item.webhook,
          in_app: item.in_app,
          webhook_url: item.webhook_url.trim() || null,
        })),
      });
      setNotificationPreferences(result);
      setNotificationForm(preferencesToForm(result));
    } catch (e) {
      setNotificationError(preferenceErrorMessage(e));
    } finally {
      setNotificationSaving(false);
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

        {!loading && (
          <section className="mt-6 rounded-md border border-border bg-background p-6">
            <div className="mb-5 border-b border-border pb-5">
              <h2 className="text-lg font-semibold">账户合并</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                冻结账户可提交合并提案。接受后保留主账户，重复账户会保持冻结，审计与账单记录保留。
              </p>
            </div>

            <form onSubmit={(event) => void handleMergeSubmit(event)} className="grid gap-4">
              <div>
                <label htmlFor="primary-user-id" className="mb-1 block text-sm font-medium">
                  主账户
                </label>
                <input
                  id="primary-user-id"
                  value={userId ?? ""}
                  readOnly
                  placeholder="重新登录后自动填充"
                  className="min-h-touch w-full rounded-md border border-border bg-muted px-3 py-2 font-mono text-xs"
                />
              </div>
              <div>
                <label htmlFor="duplicate-user-ids" className="mb-1 block text-sm font-medium">
                  重复账户 ID（逗号分隔）
                </label>
                <input
                  id="duplicate-user-ids"
                  value={duplicateIds}
                  onChange={(event) => setDuplicateIds(event.target.value)}
                  placeholder="uuid-1, uuid-2"
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label htmlFor="merge-contact-email" className="mb-1 block text-sm font-medium">
                    联系邮箱
                  </label>
                  <input
                    id="merge-contact-email"
                    type="email"
                    value={contactEmail}
                    onChange={(event) => setContactEmail(event.target.value)}
                    className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label htmlFor="merge-team-size" className="mb-1 block text-sm font-medium">
                    团队人数
                  </label>
                  <input
                    id="merge-team-size"
                    type="number"
                    min={1}
                    max={50}
                    value={teamSize}
                    onChange={(event) => setTeamSize(event.target.value)}
                    className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="merge-reason" className="mb-1 block text-sm font-medium">
                  合并说明
                </label>
                <textarea
                  id="merge-reason"
                  value={mergeReason}
                  onChange={(event) => setMergeReason(event.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </div>
              <button
                type="submit"
                disabled={submitting || !userId || !duplicateIds || !mergeReason || !contactEmail}
                className="min-h-touch w-fit rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "提交中..." : "提交合并提案"}
              </button>
            </form>

            <div className="mt-6 space-y-3">
              {mergeProposals.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无合并提案。</p>
              ) : (
                mergeProposals.map((proposal) => (
                  <div
                    key={proposal.id}
                    className="rounded-md border border-border bg-muted/40 p-4 text-sm"
                  >
                    <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="font-medium">
                          {proposal.status} · {proposal.review_mode}
                          {proposal.auto_score !== null ? ` · score ${proposal.auto_score}` : ""}
                        </p>
                        <p className="mt-1 text-muted-foreground">
                          复审截止：{formatDate(proposal.review_due_at)}
                        </p>
                      </div>
                      {(proposal.status === "approved" ||
                        proposal.status === "auto_approved") && (
                        <button
                          type="button"
                          disabled={submitting}
                          onClick={() => void handleAcceptMerge(proposal.id)}
                          className="min-h-touch rounded-md bg-success px-3 py-2 font-semibold text-white hover:bg-success/90 disabled:opacity-50"
                        >
                          接受合并
                        </button>
                      )}
                    </div>
                    <p className="mt-2 break-all font-mono text-xs text-muted-foreground">
                      duplicate: {proposal.duplicate_user_ids.join(", ")}
                    </p>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        {jwt && !loading && (
          <section
            id="notification-preferences"
            className="mt-6 rounded-md border border-border bg-background p-6"
          >
            <div className="mb-5 border-b border-border pb-5">
              <h2 className="text-lg font-semibold">通知偏好</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                按预算和公开 incident 事件选择邮件、Webhook 或站内通知渠道。
              </p>
            </div>

            {notificationError && (
              <div className="mb-4">
                <StatusCard
                  variant="error"
                  title="通知偏好保存失败"
                  description={notificationError}
                  ariaLabel="notification-preferences.error"
                />
              </div>
            )}

            {notificationLoading ? (
              <div className="rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
                正在读取通知偏好...
              </div>
            ) : (
              <form onSubmit={(event) => void handleNotificationSubmit(event)} className="grid gap-5">
                {notificationForm.map((item) => (
                  <fieldset
                    key={item.event_type}
                    className="rounded-md border border-border bg-muted/30 p-4"
                  >
                    <legend className="px-1 text-sm font-semibold">
                      {eventLabel(item.event_type)}
                    </legend>
                    <div className="mt-3 grid gap-3 sm:grid-cols-3">
                      <label className="flex min-h-touch items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
                        <input
                          type="checkbox"
                          checked={item.email}
                          onChange={(event) =>
                            updateNotificationForm(item.event_type, {
                              email: event.target.checked,
                            })
                          }
                        />
                        邮件
                      </label>
                      <label className="flex min-h-touch items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
                        <input
                          type="checkbox"
                          checked={item.in_app}
                          onChange={(event) =>
                            updateNotificationForm(item.event_type, {
                              in_app: event.target.checked,
                            })
                          }
                        />
                        站内
                      </label>
                      <label className="flex min-h-touch items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-sm">
                        <input
                          type="checkbox"
                          checked={item.webhook}
                          onChange={(event) =>
                            updateNotificationForm(item.event_type, {
                              webhook: event.target.checked,
                            })
                          }
                        />
                        Webhook
                      </label>
                    </div>
                    <label className="mt-3 block text-sm">
                      <span className="mb-1 block font-medium">Webhook URL</span>
                      <input
                        type="url"
                        value={item.webhook_url}
                        onChange={(event) =>
                          updateNotificationForm(item.event_type, {
                            webhook_url: event.target.value,
                          })
                        }
                        placeholder="https://hooks.example.com/opticloud"
                        className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
                      />
                    </label>
                  </fieldset>
                ))}

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <button
                    type="submit"
                    disabled={notificationSaving}
                    className="min-h-touch w-fit rounded-md bg-primary px-4 py-2 font-semibold text-primary-foreground hover:bg-primary-600 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {notificationSaving ? "保存中..." : "保存通知偏好"}
                  </button>
                  {notificationPreferences && (
                    <p className="text-xs text-muted-foreground">
                      当前：{" "}
                      {notificationPreferences.items
                        .map((item) => `${eventLabel(item.event_type)}=${enabledChannelsLabel(item)}`)
                        .join("；")}
                    </p>
                  )}
                </div>
              </form>
            )}
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
