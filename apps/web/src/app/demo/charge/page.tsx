"use client";
/** Demo: charge confirmation modal (Story 5.A.1 J1 anchor #4 + 5.A.5 pre-charge guard).
 *
 * Sales-demo flow:
 * 1. Sign up → page loads balance
 * 2. Click "Try a ¥6 charge" → app calls POST /charges/estimate
 * 3. If warnings → show ConfirmationModal (variant=p5_alert or balance_warn)
 *    - User confirms → close warning, open ChargeModal with confirmed=true threaded through
 *    - User cancels → back to idle
 * 4. ChargeModal shows balance recap → user clicks Confirm → POST /charges + /confirm
 */

import { useCallback, useEffect, useState } from "react";

import {
  ChargeModal,
  ConfirmationModal,
  CreditsBalanceBucket,
  type ConfirmationVariant,
} from "@opticloud/ui";

import {
  type BalanceResponse,
  type EstimateResponse,
  OptiCloudClientError,
  type WarningResponse,
  confirmCharge,
  createCharge,
  estimateCharge,
  getBalance,
} from "@/lib/api";

const CHARGE_AMOUNT = "6.00";
const CHARGE_MAX_SECONDS = 60;

function randomUUID(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function variantFor(warnings: WarningResponse[]): ConfirmationVariant {
  if (warnings.length === 0) return "generic";
  const kinds = new Set(warnings.map((w) => w.kind));
  if (kinds.has("p5_call") || kinds.has("p5_call_and_balance_low")) return "p5_alert";
  return "balance_warn";
}

export default function DemoChargePage(): JSX.Element {
  const [jwt, setJwt] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [balanceFull, setBalanceFull] = useState<BalanceResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [warningOpen, setWarningOpen] = useState(false);
  const [estimate, setEstimate] = useState<EstimateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [referenceId] = useState(randomUUID());

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem("jwt_access") : null;
    setJwt(stored);
  }, []);

  const refreshBalance = useCallback(async () => {
    if (!jwt) return;
    try {
      const b = await getBalance(jwt);
      setBalance(Number(b.balance));
      setBalanceFull(b);
    } catch (e) {
      if (e instanceof OptiCloudClientError) {
        setError(`Cannot fetch balance: ${e.detail}`);
      }
    }
  }, [jwt]);

  useEffect(() => {
    void refreshBalance();
  }, [refreshBalance]);

  const startCharge = useCallback(async () => {
    if (!jwt) return;
    setError(undefined);
    setSuccessMsg(null);
    try {
      const est = await estimateCharge(jwt, {
        purpose: "demo",
        max_solve_seconds: CHARGE_MAX_SECONDS,
      });
      setEstimate(est);
      if (est.requires_explicit_confirm) {
        setWarningOpen(true);
      } else {
        setOpen(true);
      }
    } catch (e) {
      setError(e instanceof OptiCloudClientError ? `${e.title}: ${e.detail}` : String(e));
    }
  }, [jwt]);

  const handleWarningConfirm = useCallback(() => {
    setWarningOpen(false);
    setOpen(true);
  }, []);

  const handleWarningCancel = useCallback(() => {
    setWarningOpen(false);
    setEstimate(null);
  }, []);

  const handleConfirm = useCallback(async () => {
    if (!jwt) {
      setError("Not signed in — go to /auth/signup first.");
      return;
    }
    setIsLoading(true);
    setError(undefined);
    try {
      const idempotencyKey = randomUUID();
      // 5.A.5 — thread confirmed=true ONLY when the prior estimate had warnings
      const confirmed = estimate?.requires_explicit_confirm ?? false;
      const charge = await createCharge(
        jwt,
        { amount: CHARGE_AMOUNT, purpose: "demo", reference_id: referenceId, confirmed },
        idempotencyKey,
      );
      const finalized = await confirmCharge(jwt, charge.charge_id);
      // 5.A.3 — show "saved from cap" suffix when actual < estimated by ≥ ¥0.10
      const previewedCap = estimate ? Number(estimate.estimated_amount) : Number(finalized.amount);
      const actuallyCharged = Number(finalized.amount);
      const saved = previewedCap - actuallyCharged;
      const savedSuffix = saved >= 0.1 ? ` (saved ¥${saved.toFixed(2)} from cap)` : "";
      setSuccessMsg(
        `Charged ¥${finalized.amount}${savedSuffix}. New balance: ¥${finalized.balance_after}`,
      );
      setOpen(false);
      setEstimate(null);
      void refreshBalance();
    } catch (e) {
      if (e instanceof OptiCloudClientError) {
        setError(`${e.title}: ${e.detail}`);
      } else {
        setError(String(e));
      }
    } finally {
      setIsLoading(false);
    }
  }, [jwt, referenceId, refreshBalance, estimate]);

  const warningVariant = estimate ? variantFor(estimate.warnings) : "generic";
  const warningTitle =
    warningVariant === "p5_alert"
      ? "⚠ 高额扣费确认 / High-cost charge confirmation"
      : "⚠ 余额不足提示 / Balance warning";
  const warningMessage = estimate?.warnings[0]?.message ?? "";

  return (
    <main className="container mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold">Demo: charge confirmation</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        J1 Vertical Slice anchor #4 + 5.A.5 pre-charge guard. Click the button to see the
        full flow. Requires a signed-in session — visit{" "}
        <a href="/auth/signup" className="text-primary underline">
          /auth/signup
        </a>{" "}
        first if needed.
      </p>

      <section className="mt-6">
        {jwt === null ? (
          <div className="rounded-md border border-border p-4">
            <h2 className="font-semibold">Your balance</h2>
            <p className="mt-2 text-sm text-warning">
              Not signed in — balance unavailable.
            </p>
          </div>
        ) : balanceFull === null ? (
          <div className="rounded-md border border-border p-4">
            <p className="mt-2 text-sm text-muted-foreground">Loading…</p>
          </div>
        ) : (
          <CreditsBalanceBucket
            ariaLabel="demo.balance.buckets"
            buckets={balanceFull.buckets.map((b) => ({
              name: b.name,
              labelZh: b.label_zh,
              balance: Number(b.balance),
              expiresHint: b.expires_hint ?? undefined,
            }))}
          />
        )}
      </section>

      <button
        type="button"
        onClick={() => void startCharge()}
        disabled={!jwt}
        className="mt-6 rounded-md bg-primary px-6 py-3 text-white hover:bg-primary/90 disabled:opacity-50"
        data-testid="start-charge"
      >
        Try a ¥{CHARGE_AMOUNT} charge
      </button>

      {error && !open && !warningOpen && (
        <div className="mt-4 rounded-md border border-danger/40 bg-danger/10 p-3 text-sm text-danger">
          {error}
        </div>
      )}
      {successMsg && (
        <div
          className="mt-4 rounded-md border border-success/40 bg-success/10 p-3 text-sm text-success"
          data-testid="charge-success"
        >
          {successMsg}
        </div>
      )}

      <ConfirmationModal
        open={warningOpen}
        onClose={handleWarningCancel}
        onConfirm={handleWarningConfirm}
        variant={warningVariant}
        ariaLabel="Pre-charge warning"
        title={warningTitle}
        description={warningMessage}
        body={
          estimate ? (
            <div className="rounded-md bg-muted/30 p-3 text-sm">
              <div>
                Estimated max charge: <strong>¥{estimate.estimated_amount}</strong>
              </div>
              <div>
                Current balance: <strong>¥{estimate.balance}</strong>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                FR B2: actual ≤ estimated / 实际扣费不超过预估
              </div>
            </div>
          ) : null
        }
        confirmLabel="我已理解，继续扣费 / Proceed"
        cancelLabel="取消 / Cancel"
      />

      <ChargeModal
        open={open}
        amount={Number(CHARGE_AMOUNT)}
        currency="CNY"
        balance={balance ?? 0}
        purpose="Demo charge (Story 5.A.1 + 5.A.5)"
        referenceId={referenceId}
        onConfirm={handleConfirm}
        onCancel={() => setOpen(false)}
        isLoading={isLoading}
        error={error}
      />
    </main>
  );
}
