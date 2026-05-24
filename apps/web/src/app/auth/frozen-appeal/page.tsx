"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { RFC7807Panel, StatusCard } from "@opticloud/ui";

import {
  acceptFrozenAppeal,
  getFrozenAppeal,
  OptiCloudClientError,
  startFrozenAppeal,
  submitFrozenAppealProposal,
  type FrozenAppealStartResponse,
  type FrozenAppealStatusResponse,
} from "@/lib/api";

type Step = 1 | 2 | 3;

const STORAGE_KEY = "opticloud:frozen-appeal:session";

function safeSessionSet(key: string, value: string): void {
  if (typeof window !== "undefined") {
    sessionStorage.setItem(key, value);
  }
}

function safeSessionGet(key: string): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(key);
}

function safeSessionRemove(key: string): void {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem(key);
  }
}

function saveAppealSession(appealId: string, token: string): void {
  safeSessionSet(STORAGE_KEY, JSON.stringify({ appealId, token }));
}

function loadAppealSession(): { appealId: string; token: string } | null {
  const raw = safeSessionGet(STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as { appealId?: string; token?: string };
    if (parsed.appealId && parsed.token) {
      return { appealId: parsed.appealId, token: parsed.token };
    }
  } catch {
    return null;
  }
  return null;
}

function nextActionLabel(action: FrozenAppealStatusResponse["next_action"]): string {
  return {
    submit_proposal: "提交提案",
    await_review: "等待复审",
    accept_merge: "接受合并",
    completed: "已完成",
    contact_support: "联系支持",
  }[action];
}

export default function FrozenAppealPage(): JSX.Element {
  const searchParams = useSearchParams();
  const [step, setStep] = useState<Step>(1);
  const [phone, setPhone] = useState(searchParams.get("phone") ?? "");
  const [email, setEmail] = useState(searchParams.get("email") ?? "");
  const [appealId, setAppealId] = useState<string>("");
  const [trackingToken, setTrackingToken] = useState<string>("");
  const [appeal, setAppeal] = useState<FrozenAppealStartResponse | null>(null);
  const [status, setStatus] = useState<FrozenAppealStatusResponse | null>(null);
  const [duplicateUserIds, setDuplicateUserIds] = useState("");
  const [reason, setReason] = useState("");
  const [contactEmail, setContactEmail] = useState(searchParams.get("email") ?? "");
  const [supportingNote, setSupportingNote] = useState("");
  const [teamSize, setTeamSize] = useState("2");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<OptiCloudClientError | null>(null);
  const [accepted, setAccepted] = useState(false);

  const frozenSummary = useMemo(() => {
    if (!status && !appeal) return null;
    return status?.risk_summary ?? appeal?.risk_summary ?? null;
  }, [appeal, status]);

  const loadExistingStatus = async (appealId: string, token: string): Promise<void> => {
    const result = await getFrozenAppeal(appealId, token);
    setAppealId(appealId);
    setStatus(result);
    setAccepted(result.status === "accepted");
    setStep(result.next_action === "submit_proposal" ? 2 : 3);
  };

  useEffect(() => {
    const appealId = searchParams.get("appeal_id");
    const token = searchParams.get("tracking_token");
    if (appealId && token) {
      setTrackingToken(token);
      setAppealId(appealId);
      saveAppealSession(appealId, token);
      void loadExistingStatus(appealId, token).catch((err) => {
        if (err instanceof OptiCloudClientError) setError(err);
      });
    }
  }, [searchParams]);

  useEffect(() => {
    const stored = loadAppealSession();
    if (stored) {
      setTrackingToken(stored.token);
      void loadExistingStatus(stored.appealId, stored.token).catch((err) => {
        if (err instanceof OptiCloudClientError) setError(err);
      });
    }
  }, []);

  useEffect(() => {
    if (!trackingToken || !appeal) return;
    saveAppealSession(appeal.appeal_id, trackingToken);
  }, [appeal, trackingToken]);

  const handleStart = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const result = await startFrozenAppeal({ phone, email });
      setAppeal(result);
      setAppealId(result.appeal_id);
      setTrackingToken(result.tracking_token);
      saveAppealSession(result.appeal_id, result.tracking_token);
      setStatus({
        appeal_id: result.appeal_id,
        status: result.status,
        expires_at: result.expires_at,
        last_viewed_at: null,
        risk_summary: result.risk_summary,
        proposal: result.proposal,
        next_action:
          result.next_action === "submit_proposal" ? "submit_proposal" : result.next_action,
      });
      setAccepted(false);
      setStep(result.next_action === "submit_proposal" ? 2 : 3);
    } catch (err) {
      setError(err instanceof OptiCloudClientError ? err : null);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitProposal = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    const currentAppealId = appealId || appeal?.appeal_id;
    if (!currentAppealId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await submitFrozenAppealProposal(currentAppealId, {
        tracking_token: trackingToken,
        duplicate_user_ids: duplicateUserIds
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        reason,
        contact_email: contactEmail,
        supporting_note: supportingNote || null,
        team_size: teamSize ? Number(teamSize) : null,
      });
      setStatus(result);
      setStep(3);
    } catch (err) {
      setError(err instanceof OptiCloudClientError ? err : null);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (): Promise<void> => {
    const currentAppealId = appealId || appeal?.appeal_id;
    if (!currentAppealId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await acceptFrozenAppeal(currentAppealId, {
        tracking_token: trackingToken,
      });
      setStatus(result);
      setAccepted(true);
      setStep(3);
      safeSessionRemove(STORAGE_KEY);
    } catch (err) {
      setError(err instanceof OptiCloudClientError ? err : null);
    } finally {
      setLoading(false);
    }
  };

  const visibleStatus = status ?? null;

  return (
    <main className="min-h-screen bg-muted p-4">
      <div className="mx-auto max-w-4xl py-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold">账户已触发风控冻结</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            提交后可用此页面查看复审状态。
          </p>
        </header>

        {error && (
          <div className="mb-4">
            {error.errors && error.errors.length > 0 ? (
              <RFC7807Panel
                payload={{
                  title: error.title,
                  status: error.status,
                  detail: error.detail,
                  errors: error.errors,
                  next_action_url: error.next_action_url,
                }}
              />
            ) : (
              <StatusCard
                variant="error"
                title={error.title}
                description={error.detail}
                ariaLabel={`error.frozen-appeal.${error.status}`}
              />
            )}
          </div>
        )}

        <div className="mb-4 grid gap-3 md:grid-cols-3">
          {[
            { id: 1, label: "1. 开始申诉" },
            { id: 2, label: "2. 提交提案" },
            { id: 3, label: "3. 查看状态" },
          ].map((item) => (
            <div
              key={item.id}
              className={
                step === item.id
                  ? "rounded-md border border-primary bg-primary/5 p-3 text-sm font-medium"
                  : "rounded-md border border-border bg-background p-3 text-sm text-muted-foreground"
              }
              data-testid={`appeal-step-${item.id}`}
            >
              {item.label}
            </div>
          ))}
        </div>

        {step === 1 && (
          <form onSubmit={handleStart} className="rounded-md border border-border bg-background p-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="appeal-phone" className="mb-1 block text-sm font-medium">
                  手机号
                </label>
                <input
                  id="appeal-phone"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="appeal-email" className="mb-1 block text-sm font-medium">
                  邮箱
                </label>
                <input
                  id="appeal-email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading || !phone || !email}
              className="mt-4 min-h-touch rounded-md bg-primary px-4 py-2 text-white"
            >
              开始申诉
            </button>
          </form>
        )}

        {step === 2 && (appeal || appealId) && (
          <form
            onSubmit={handleSubmitProposal}
            className="rounded-md border border-border bg-background p-6"
            data-testid="appeal-submit-form"
          >
            <div className="mb-4 rounded-md border border-border bg-muted/40 p-4 text-sm">
              <p className="font-medium">安全风险概览</p>
              <p className="mt-1">
                风险分数 {frozenSummary?.risk_score ?? 0} · 规则数 {frozenSummary?.total_flag_count ?? 0}
              </p>
              <p className="mt-1 text-muted-foreground">
                最近规则：{frozenSummary?.latest_rule_codes.join(", ") || "无"}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label htmlFor="duplicate-user-ids" className="mb-1 block text-sm font-medium">
                  重复账户 ID
                </label>
                <textarea
                  id="duplicate-user-ids"
                  value={duplicateUserIds}
                  onChange={(event) => setDuplicateUserIds(event.target.value)}
                  className="min-h-[96px] w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
                />
              </div>
              <div className="grid gap-4">
                <div>
                  <label htmlFor="contact-email" className="mb-1 block text-sm font-medium">
                    联系邮箱
                  </label>
                  <input
                    id="contact-email"
                    type="email"
                    value={contactEmail}
                    onChange={(event) => setContactEmail(event.target.value)}
                    className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
                  />
                </div>
                <div>
                  <label htmlFor="team-size" className="mb-1 block text-sm font-medium">
                    团队人数
                  </label>
                  <input
                    id="team-size"
                    type="number"
                    min={1}
                    max={50}
                    value={teamSize}
                    onChange={(event) => setTeamSize(event.target.value)}
                    className="min-h-touch w-full rounded-md border border-border bg-background px-3 py-2"
                  />
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-4">
              <div>
                <label htmlFor="reason" className="mb-1 block text-sm font-medium">
                  申诉说明
                </label>
                <textarea
                  id="reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </div>
              <div>
                <label htmlFor="supporting-note" className="mb-1 block text-sm font-medium">
                  补充说明
                </label>
                <textarea
                  id="supporting-note"
                  value={supportingNote}
                  onChange={(event) => setSupportingNote(event.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !duplicateUserIds || !reason || !contactEmail}
              className="mt-4 min-h-touch rounded-md bg-primary px-4 py-2 text-white"
            >
              提交提案
            </button>
          </form>
        )}

        {step === 3 && visibleStatus && (
          <section className="rounded-md border border-border bg-background p-6" data-testid="appeal-status-panel">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <p className="text-sm text-muted-foreground">当前状态</p>
                <p className="font-medium">{visibleStatus.status}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">下一步</p>
                <p className="font-medium">{nextActionLabel(visibleStatus.next_action)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">复审截止</p>
                <p className="font-medium">{visibleStatus.expires_at}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">风险分数</p>
                <p className="font-medium">{visibleStatus.risk_summary.risk_score}</p>
              </div>
            </div>

            {visibleStatus.proposal && (
              <div className="mt-4 rounded-md border border-border bg-muted/40 p-4 text-sm">
                <p className="font-medium">合并提案</p>
                <p className="mt-1">状态：{visibleStatus.proposal.status}</p>
                <p>复审模式：{visibleStatus.proposal.review_mode}</p>
                <p>得分：{visibleStatus.proposal.auto_score ?? "-"}</p>
                <p>到期：{visibleStatus.proposal.review_due_at}</p>
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-3">
              {visibleStatus.next_action === "accept_merge" && !accepted && (
                <button
                  type="button"
                  onClick={() => void handleAccept()}
                  disabled={loading}
                  className="min-h-touch rounded-md bg-primary px-4 py-2 text-white"
                  data-testid="accept-merge-button"
                >
                  接受合并
                </button>
              )}
              <a href="/auth/login" className="min-h-touch rounded-md border border-border px-4 py-2">
                返回登录
              </a>
            </div>

            {accepted && (
              <p className="mt-4 text-sm text-success">
                接受后保留主账户，重复账户会保持冻结，审计与账单记录保留。
              </p>
            )}
          </section>
        )}
      </div>
    </main>
  );
}
