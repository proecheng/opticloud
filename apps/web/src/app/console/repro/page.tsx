"use client";

import { useMemo, useState } from "react";

import { StatusCard, VoucherCard, type VoucherCardVoucher } from "@opticloud/ui";

import { ConsolePageHeader, ConsoleShell } from "@/components/ConsoleShell";
import {
  OptiCloudClientError,
  rerunReproductionVoucher,
  type ReproductionRerunResponse,
} from "@/lib/api";

type DemoVoucher = VoucherCardVoucher;

const demoVouchers: DemoVoucher[] = [
  {
    voucherId: "repro-2026-K7X9P2",
    status: "issued",
    createdAt: "2026-05-22T02:56:27.000Z",
    expiresAt: "2031-05-22T02:56:27.000Z",
    lockedSolver: "highs",
    lockedModelVersion: {
      provider_id: "scipy",
      name: "linprog",
      version: "1.11.4",
    },
    requestFingerprint: "fixture-fingerprint-2026-issued-voucher",
    seedLocked: true,
    seed: null,
    anonymous: true,
  },
  {
    voucherId: "repro-2026-M4N8Q1",
    status: "rerun_child",
    createdAt: "2026-05-22T03:14:09.000Z",
    expiresAt: "2031-05-22T03:14:09.000Z",
    lockedSolver: "highs",
    lockedModelVersion: {
      provider_id: "scipy",
      name: "linprog",
      version: "1.11.4",
    },
    requestFingerprint: "fixture-fingerprint-2026-rerun-child",
    seedLocked: true,
    seed: 42,
    rerunOfVoucherId: "repro-2026-K7X9P2",
    sourceOptimizationId: "11111111-1111-1111-1111-111111111111",
    childVoucherId: "repro-2026-M4N8Q1",
  },
  {
    voucherId: "repro-2026-R8T2V4",
    status: "expired",
    createdAt: "2021-05-22T03:14:09.000Z",
    expiresAt: "2026-05-22T03:14:09.000Z",
    lockedSolver: "highs",
    lockedModelVersion: {
      provider_id: "scipy",
      name: "linprog",
      version: "1.11.4",
    },
    requestFingerprint: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    seedLocked: false,
    seed: null,
  },
];

function normalizeClientError(err: unknown): string {
  if (err instanceof OptiCloudClientError) {
    return `${err.title}: ${err.detail}`;
  }
  if (err instanceof Error) return err.message;
  return "rerun failed";
}

function summarizeRerunResult(result: ReproductionRerunResponse | null): string | null {
  if (!result) return null;
  const voucherId = result.reproducibility?.voucher_id ?? "(missing voucher_id)";
  return `${voucherId} · rerun_of=${result.rerun_of_voucher_id} · source=${result.source_optimization_id}`;
}

export default function ReproConsolePage(): JSX.Element {
  const [apiKey, setApiKey] = useState("");
  const [selectedVoucherId, setSelectedVoucherId] = useState(demoVouchers[0]?.voucherId ?? "");
  const [sessionNote, setSessionNote] = useState<string | null>(null);
  const [rerunningId, setRerunningId] = useState<string | null>(null);
  const [rerunError, setRerunError] = useState<string | undefined>();
  const [rerunResult, setRerunResult] = useState<ReproductionRerunResponse | null>(null);

  const selectedVoucher = useMemo(
    () => demoVouchers.find((voucher) => voucher.voucherId === selectedVoucherId) ?? demoVouchers[0],
    [selectedVoucherId],
  );

  const selectVoucher = (voucherId: string): void => {
    setSelectedVoucherId(voucherId);
    setSessionNote(null);
    setRerunError(undefined);
    setRerunResult(null);
  };

  const handleRerun = async (voucherId: string): Promise<void> => {
    if (!apiKey.trim()) {
      setRerunError("Please enter an API key for this session.");
      return;
    }

    selectVoucher(voucherId);
    setRerunningId(voucherId);

    try {
      const result = await rerunReproductionVoucher(apiKey.trim(), voucherId);
      setRerunResult(result);
      setSessionNote(
        summarizeRerunResult(result) ??
          "Rerun completed, but the response did not include full lineage fields.",
      );
    } catch (err) {
      setRerunError(normalizeClientError(err));
    } finally {
      setRerunningId(null);
    }
  };

  return (
    <ConsoleShell active="repro">
      <ConsolePageHeader
        eyebrow="Console / Reproducibility"
        title="Repro Dashboard"
        description="Voucher fixtures, rerun state, and a session-only API key input for the existing reproduction rerun client."
        meta={
          <>
            <span className="inline-flex min-h-touch items-center rounded-md border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary">
              Session-only API key
            </span>
            <span className="inline-flex min-h-touch items-center rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground">
              Fixture dashboard
            </span>
          </>
        }
      />

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="min-w-0 space-y-4">
          <div className="rounded-md border border-border bg-background p-4">
            <label className="block text-sm font-medium text-foreground" htmlFor="repro-api-key">
              API key
            </label>
            <input
              id="repro-api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Bearer token for this browser session"
              className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              Stored only in memory for this page session.
            </p>
          </div>

          <div className="rounded-md border border-border bg-background p-4">
            <div className="mb-3 text-sm font-medium">Issued vouchers</div>
            <div className="space-y-2">
              {demoVouchers.map((voucher) => (
                <button
                  key={voucher.voucherId}
                  type="button"
                  onClick={() => selectVoucher(voucher.voucherId)}
                  className={[
                    "block w-full rounded-md border px-3 py-2 text-left text-sm",
                    selectedVoucherId === voucher.voucherId
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted",
                  ].join(" ")}
                >
                  <div className="font-mono">{voucher.voucherId}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{voucher.status}</div>
                </button>
              ))}
            </div>
          </div>

          <StatusCard
            variant="info"
            title="Dashboard scope"
            description="No voucher list/search endpoint exists yet. This page only demonstrates fixtures and one-click rerun."
            ariaLabel="repro.dashboard.scope"
          />
        </aside>

        <section className="min-w-0 space-y-4">
          {sessionNote && (
            <StatusCard
              variant="ok"
              title="Rerun completed"
              description={sessionNote}
              ariaLabel="repro.dashboard.success"
            />
          )}
          {rerunError && (
            <StatusCard
              variant="error"
              title="Rerun failed"
              description={rerunError}
              ariaLabel="repro.dashboard.error"
            />
          )}

          <VoucherCard
            voucher={selectedVoucher}
            canRerun={selectedVoucher.status === "issued"}
            isRerunning={rerunningId === selectedVoucher.voucherId}
            rerunError={rerunError}
            rerunResult={
              rerunResult
                ? {
                    childVoucherId:
                      rerunResult.reproducibility?.voucher_id ?? "(missing voucher_id)",
                    rerunOfVoucherId: rerunResult.rerun_of_voucher_id,
                    sourceOptimizationId: rerunResult.source_optimization_id,
                  }
                : undefined
            }
            onRerun={(voucherId) => void handleRerun(voucherId)}
            onCopyVoucherId={async (voucherId) => {
              try {
                await navigator.clipboard.writeText(voucherId);
              } catch {
                // Session-only dashboard; clipboard failures should not block the card.
              }
            }}
            onViewDetails={(voucherId) => selectVoucher(voucherId)}
          />
        </section>
      </section>
    </ConsoleShell>
  );
}
