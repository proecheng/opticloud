"use client";
/** Demo: charge confirmation modal (Story 5.A.1 J1 anchor #4).
 *
 * Sales-demo flow: sign up first, then click "Try a ¥6 charge". The modal
 * shows current balance + cost + post-charge balance; on confirm the
 * billing-service creates and finalizes the Saga.
 */

import { useCallback, useEffect, useState } from "react";

import { ChargeModal } from "@opticloud/ui";

import {
  OptiCloudClientError,
  confirmCharge,
  createCharge,
  getBalance,
} from "@/lib/api";

const CHARGE_AMOUNT = "6.00";

function randomUUID(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export default function DemoChargePage(): JSX.Element {
  const [jwt, setJwt] = useState<string | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
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
    } catch (e) {
      if (e instanceof OptiCloudClientError) {
        setError(`Cannot fetch balance: ${e.detail}`);
      }
    }
  }, [jwt]);

  useEffect(() => {
    void refreshBalance();
  }, [refreshBalance]);

  const startCharge = useCallback(() => {
    setError(undefined);
    setSuccessMsg(null);
    setOpen(true);
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
      const charge = await createCharge(
        jwt,
        { amount: CHARGE_AMOUNT, purpose: "demo", reference_id: referenceId },
        idempotencyKey,
      );
      const finalized = await confirmCharge(jwt, charge.charge_id);
      setSuccessMsg(
        `Charged ¥${finalized.amount}. New balance: ¥${finalized.balance_after}`,
      );
      setOpen(false);
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
  }, [jwt, referenceId, refreshBalance]);

  return (
    <main className="container mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold">Demo: charge confirmation</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        J1 Vertical Slice anchor #4. Click the button to see the charge modal.
        Requires a signed-in session — visit{" "}
        <a href="/auth/signup" className="text-primary underline">
          /auth/signup
        </a>{" "}
        first if needed.
      </p>

      <section className="mt-6 rounded-md border border-border p-4">
        <h2 className="font-semibold">Your balance</h2>
        {jwt === null ? (
          <p className="mt-2 text-sm text-warning">
            Not signed in — balance unavailable.
          </p>
        ) : balance === null ? (
          <p className="mt-2 text-sm text-muted-foreground">Loading…</p>
        ) : (
          <p className="mt-2 text-3xl font-bold" data-testid="demo-balance">
            ¥{balance.toFixed(2)}
          </p>
        )}
      </section>

      <button
        type="button"
        onClick={startCharge}
        disabled={!jwt}
        className="mt-6 rounded-md bg-primary px-6 py-3 text-white hover:bg-primary/90 disabled:opacity-50"
        data-testid="start-charge"
      >
        Try a ¥{CHARGE_AMOUNT} charge
      </button>

      {error && !open && (
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

      <ChargeModal
        open={open}
        amount={Number(CHARGE_AMOUNT)}
        currency="CNY"
        balance={balance ?? 0}
        purpose="Demo charge (Story 5.A.1)"
        referenceId={referenceId}
        onConfirm={handleConfirm}
        onCancel={() => setOpen(false)}
        isLoading={isLoading}
        error={error}
      />
    </main>
  );
}
