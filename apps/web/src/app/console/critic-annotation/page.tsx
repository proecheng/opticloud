"use client";

import Link from "next/link";
import { Suspense, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { StatusCard } from "@opticloud/ui";

import calibrationConfig from "../../../../../../apps/critic-service/config/critic-calibration.json";
import batchPayload from "../../../../../../tools/critic_calibration/annotation_batches/2026-05-25.json";
import dataset from "../../../../../../tools/critic_calibration/ground_truth_v1.json";

type CriticSample = {
  id: string;
  prompt: string;
  expected_escalate: boolean;
  critic_confidence: number;
  critic_reason_zh: string;
  category: string;
  source_story: string;
  llm_output_excerpt?: string;
};

type Ticket = {
  key: string;
  sample_id: string;
  due_date: string;
  status: string;
};

type ReviewDecision = "pass" | "escalate" | "auto-block";

const samples = dataset.samples as CriticSample[];
const tickets = batchPayload.tickets as Ticket[];
const defaultSampleId = tickets[0]?.sample_id ?? samples[0]?.id ?? "";
const threshold = calibrationConfig.recommended_threshold;

function formatExpectedLabel(value: boolean): string {
  return value ? "escalate" : "pass";
}

function predictionFor(confidence: number): string {
  return confidence < threshold ? "escalate" : "pass";
}

function CriticAnnotationContent(): JSX.Element {
  const searchParams = useSearchParams();
  const selectedSampleId = searchParams.get("sample") ?? defaultSampleId;
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [note, setNote] = useState("");

  const sample = useMemo(
    () => samples.find((item) => item.id === selectedSampleId),
    [selectedSampleId],
  );
  const ticket = useMemo(
    () => tickets.find((item) => item.sample_id === selectedSampleId),
    [selectedSampleId],
  );

  const localDecisionText = decision === null ? "unreviewed" : decision;

  if (!sample) {
    return (
      <main className="min-h-screen bg-background">
        <ConsoleHeader />
        <section className="mx-auto max-w-5xl px-6 py-8">
          <StatusCard
            variant="error"
            title="Sample not found"
            description={`No committed Critic sample matches ${selectedSampleId}.`}
            ariaLabel="critic.annotation.not_found"
          />
          <Link
            href={`/console/critic-annotation?sample=${defaultSampleId}`}
            className="mt-4 inline-flex rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
          >
            Open first batch ticket
          </Link>
        </section>
      </main>
    );
  }

  const prediction = predictionFor(sample.critic_confidence);

  return (
    <main className="min-h-screen bg-background">
      <ConsoleHeader />

      <section className="border-b border-border bg-muted">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <h1 className="text-2xl font-bold">Critic Annotation</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            Internal review surface for the committed M3.5b weekly annotation batch.
          </p>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-md border border-border bg-background p-4">
            <div className="text-sm font-medium">Batch</div>
            <dl className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Epic</dt>
                <dd className="font-mono">{batchPayload.epic_key}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Due</dt>
                <dd>{batchPayload.due_date}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Tickets</dt>
                <dd data-testid="critic-batch-progress">{tickets.length} todo</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Local decision</dt>
                <dd data-testid="critic-local-decision">{localDecisionText}</dd>
              </div>
            </dl>
          </div>

          <div className="rounded-md border border-border bg-background p-4">
            <div className="mb-3 text-sm font-medium">Tickets</div>
            <div className="space-y-2">
              {tickets.slice(0, 6).map((item) => (
                <Link
                  key={item.key}
                  href={`/console/critic-annotation?sample=${item.sample_id}`}
                  className={[
                    "block rounded-md border px-3 py-2 text-sm",
                    item.sample_id === sample.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-muted",
                  ].join(" ")}
                >
                  <div className="font-mono text-xs">{item.key}</div>
                  <div className="mt-1 font-mono text-xs text-muted-foreground">
                    {item.sample_id}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </aside>

        <section className="space-y-4">
          <div className="rounded-md border border-border bg-background p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="font-mono text-sm" data-testid="critic-sample-id">
                  {sample.id}
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {ticket?.key ?? "unbatched"} · {sample.source_story}
                </div>
              </div>
              <div className="rounded-md border border-border px-3 py-2 text-sm">
                threshold {threshold.toFixed(2)}
              </div>
            </div>

            <dl className="mt-5 grid gap-3 text-sm md:grid-cols-2">
              <div className="rounded-md bg-muted p-3">
                <dt className="text-muted-foreground">Category</dt>
                <dd className="mt-1 font-medium">{sample.category}</dd>
              </div>
              <div className="rounded-md bg-muted p-3">
                <dt className="text-muted-foreground">Expected</dt>
                <dd className="mt-1 font-medium">{formatExpectedLabel(sample.expected_escalate)}</dd>
              </div>
              <div className="rounded-md bg-muted p-3">
                <dt className="text-muted-foreground">Confidence</dt>
                <dd className="mt-1 font-medium">{sample.critic_confidence.toFixed(2)}</dd>
              </div>
              <div className="rounded-md bg-muted p-3">
                <dt className="text-muted-foreground">Current decision</dt>
                <dd className="mt-1 font-medium" data-testid="critic-current-decision">
                  {prediction}
                </dd>
              </div>
            </dl>

            <div className="mt-5 space-y-4">
              <section>
                <h2 className="text-sm font-semibold">Prompt</h2>
                <p className="mt-2 rounded-md border border-border p-3 text-sm">{sample.prompt}</p>
              </section>
              <section>
                <h2 className="text-sm font-semibold">LLM output</h2>
                <p className="mt-2 rounded-md border border-border p-3 text-sm">
                  {sample.llm_output_excerpt ?? "No excerpt captured for this M3 seed sample."}
                </p>
              </section>
              <section>
                <h2 className="text-sm font-semibold">Critic reason</h2>
                <p className="mt-2 rounded-md border border-border p-3 text-sm">
                  {sample.critic_reason_zh}
                </p>
              </section>
            </div>
          </div>

          <div className="rounded-md border border-border bg-background p-5">
            <fieldset>
              <legend className="text-sm font-semibold">Adjudication</legend>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {(["pass", "escalate", "auto-block"] as ReviewDecision[]).map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => setDecision(item)}
                    className={[
                      "rounded-md border px-3 py-2 text-sm",
                      decision === item
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border hover:bg-muted",
                    ].join(" ")}
                    data-testid={`critic-decision-${item}`}
                  >
                    {item}
                  </button>
                ))}
              </div>
            </fieldset>

            <label className="mt-4 block text-sm font-medium" htmlFor="critic-adjudication-note">
              Adjudication note
            </label>
            <textarea
              id="critic-adjudication-note"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              rows={4}
              className="mt-2 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />

            <StatusCard
              variant="info"
              title="Local summary"
              description={`${sample.id} · decision=${localDecisionText} · note=${note.trim() || "empty"}`}
              ariaLabel="critic.annotation.local_summary"
            />
          </div>
        </section>
      </section>
    </main>
  );
}

function ConsoleHeader(): JSX.Element {
  return (
    <header className="border-b border-border bg-background">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-7 w-7 rounded bg-primary" />
          <span className="font-semibold">OptiCloud</span>
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/console/repro" className="text-muted-foreground hover:text-foreground">
            Repro
          </Link>
          <Link
            href="/console/critic-annotation"
            className="text-muted-foreground hover:text-foreground"
          >
            Critic
          </Link>
        </nav>
      </div>
    </header>
  );
}

export default function CriticAnnotationPage(): JSX.Element {
  return (
    <Suspense fallback={<main className="min-h-screen bg-background" />}>
      <CriticAnnotationContent />
    </Suspense>
  );
}
