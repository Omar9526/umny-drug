"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { Check, ChevronDown, ChevronUp, CircleHelp, EyeOff, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { ChatMessage } from "@/components/tutor/ChatMessage";
import { useChildSession } from "@/features/parent/api";
import { cn } from "@/lib/utils";
import type { AnswerAttempt, Verdict } from "@/lib/api/types";

const VERDICT_TONE: Record<Verdict, string> = {
  correct: "bg-success/10 text-success",
  partial: "bg-warning/15 text-warning",
  incorrect: "bg-destructive/10 text-destructive",
  uncertain: "bg-muted text-muted-foreground",
};

function AttemptRow({ attempt }: { attempt: AnswerAttempt }) {
  const t = useTranslations("parent.sessionDetail");
  const verdict = attempt.verification?.verdict;
  return (
    <li className="flex items-start gap-3 rounded-2xl bg-white px-4 py-3 ring-1 ring-line">
      <span
        className={cn(
          "mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full",
          verdict ? VERDICT_TONE[verdict] : "bg-muted text-muted-foreground",
        )}
        aria-hidden
      >
        {verdict === "correct" ? <Check className="size-4" /> : <CircleHelp className="size-4" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-semibold text-muted-foreground">
          {t("attempt", { n: attempt.attempt_number })}
          {attempt.is_independent ? ` · ${t("independentMark")}` : ` · ${t("withHints", { count: attempt.hints_before })}`}
        </p>
        <p className="mt-0.5 whitespace-pre-wrap text-base font-semibold">{attempt.answer_text}</p>
        {attempt.verification && (
          <p className="mt-1 text-sm text-muted-foreground">
            <span className={cn("rounded-full px-2 py-0.5 text-xs font-bold", VERDICT_TONE[attempt.verification.verdict])}>
              {attempt.verification.verdict_label}
            </span>{" "}
            · {attempt.verification.method_label}
          </p>
        )}
      </div>
    </li>
  );
}

export default function ParentSessionPage({ params }: PageProps<"/parent/children/[id]/sessions/[sessionId]">) {
  const { id, sessionId } = use(params);
  const t = useTranslations("parent.sessionDetail");
  const ts = useTranslations("session");
  const format = useFormatter();
  const query = useChildSession(id, sessionId);
  const [stepsOpen, setStepsOpen] = useState(false);
  const back = `/parent/children/${id}/sessions`;

  if (query.isPending) {
    return (
      <div>
        <PageHeader title={t("title")} backHref={back} />
        <CardSkeleton lines={4} />
      </div>
    );
  }
  if (query.isError) {
    return (
      <div>
        <PageHeader title={t("title")} backHref={back} />
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      </div>
    );
  }

  const data = query.data;
  const title = data.title || data.topic_name || data.subject?.name || ts(`mode.${data.mode}`);
  const needsReview = data.outcome === "needs_review";

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={title} subtitle={format.dateTime(new Date(data.created_at), { dateStyle: "long", timeStyle: "short" })} backHref={back} />

      <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <div className="flex items-start gap-3">
          <SubjectIcon icon={data.subject?.icon ?? "book-open"} color={data.subject?.color ?? "sage"} />
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold tracking-wide text-muted-foreground uppercase">{t("task")}</p>
            <p className="mt-1 whitespace-pre-wrap text-base">{data.assignment?.text ?? data.assignment_text ?? title}</p>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5 text-xs font-semibold">
          <span
            className={cn(
              "rounded-full px-2.5 py-1",
              needsReview ? "bg-warning/15 text-warning" : data.status === "completed" ? "bg-teal text-white" : "bg-lime text-ink",
            )}
          >
            {needsReview ? ts("outcome.needs_review") : ts(`status.${data.status}`)}
          </span>
          {data.status === "completed" && data.outcome && !needsReview && (
            <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">{ts(`outcome.${data.outcome}`)}</span>
          )}
          <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">{ts("hints", { count: data.hints_used })}</span>
        </div>
        {data.summary_for_parent && (
          <div className="mt-4 rounded-2xl bg-teal-soft px-4 py-3">
            <p className="text-xs font-bold tracking-wide text-teal uppercase">{t("summary")}</p>
            <p className="mt-1 text-base">{data.summary_for_parent}</p>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-extrabold">{t("attempts")}</h2>
        {data.attempts.length === 0 ? (
          <EmptyState text={t("noAttempts")} />
        ) : (
          <ul className="flex flex-col gap-2">
            {data.attempts.map((attempt) => (
              <AttemptRow key={attempt.id} attempt={attempt} />
            ))}
          </ul>
        )}
      </section>

      {data.steps.length > 0 && (
        <section className="rounded-3xl bg-white p-4 shadow-card ring-1 ring-line">
          <button
            type="button"
            onClick={() => setStepsOpen((v) => !v)}
            className="flex w-full items-center justify-between text-left"
            aria-expanded={stepsOpen}
          >
            <span className="flex items-center gap-2 text-base font-bold">
              <Lightbulb className="size-4 text-teal" /> {t("steps", { count: data.steps.length })}
            </span>
            {stepsOpen ? <ChevronUp className="size-5" /> : <ChevronDown className="size-5" />}
          </button>
          {stepsOpen && (
            <ol className="mt-3 flex flex-col gap-2">
              {data.steps.map((step) => (
                <li key={step.id} className="rounded-2xl bg-ivory px-3 py-2">
                  <p className="text-sm font-bold">
                    {step.order}. {step.title}
                  </p>
                  {step.content && <p className="mt-0.5 text-sm text-muted-foreground">{step.content}</p>}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-extrabold">{t("transcript")}</h2>
        {data.conversation_visible ? (
          data.messages.length === 0 ? (
            <EmptyState text={t("noMessages")} />
          ) : (
            <div className="flex flex-col gap-3">
              {data.messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
            </div>
          )
        ) : (
          <EmptyState
            icon={<EyeOff />}
            text={t("hidden")}
            action={
              <Button variant="soft" render={<Link href={`/parent/children/${id}/settings`} />}>
                {t("enable")}
              </Button>
            }
          />
        )}
      </section>
    </div>
  );
}
