"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import { Camera, Home, RotateCcw, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SessionState, TaskBrief } from "@/lib/api/types";

export function ResultCard({
  state,
  siblings,
  topicId,
}: {
  state: SessionState;
  siblings: TaskBrief[];
  topicId?: number | null;
}) {
  const t = useTranslations("result");
  const tt = useTranslations("tutor");
  const nextTask = siblings.find((s) => s.status === "recognized" || s.status === "confirmed");
  const titles = {
    independent: t("title"),
    with_help: t("titleHelp"),
    needs_review: t("titleReview"),
    not_completed: t("titleAbandoned"),
    "": t("titleAbandoned"),
  } as const;
  const texts = {
    independent: t("independent"),
    with_help: t("withHelp"),
    needs_review: t("needsReview"),
    not_completed: t("notCompleted"),
    "": t("notCompleted"),
  } as const;
  const celebratory = state.outcome === "independent" || state.outcome === "with_help";

  return (
    <section className={`rise-in rounded-[28px] p-6 shadow-card ${celebratory ? "bg-lime" : "bg-white ring-1 ring-line"}`}>
      <p className="text-4xl" aria-hidden>
        {celebratory ? "🎉" : state.outcome === "needs_review" ? "📚" : "👋"}
      </p>
      <h2 className="mt-2 text-2xl font-extrabold text-teal">{titles[state.outcome]}</h2>
      <p className="mt-1 text-base text-ink/80">{texts[state.outcome]}</p>
      <p className="mt-3 text-sm font-semibold text-muted-foreground">
        {tt("attempts", { count: state.attempts_count })} · {tt("hintsUsed", { count: state.hints_used })}
      </p>
      {state.understood_points.length > 0 && (
        <div className="mt-4">
          <p className="text-sm font-bold">{t("understood")}</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {state.understood_points.map((point) => (
              <li key={point} className="rounded-full bg-white/80 px-3 py-1 text-sm ring-1 ring-line">
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-5 flex flex-col gap-2">
        {nextTask ? (
          <Button size="lg" render={<Link href={`/assignments/${nextTask.id}/confirm`} />}>
            <ArrowRight /> {t("nextFromPhoto")}: {nextTask.label || nextTask.excerpt.slice(0, 24)}
          </Button>
        ) : (
          <Button size="lg" render={<Link href="/assignments/new?source=camera" />}>
            <Camera /> {t("newPhoto")}
          </Button>
        )}
        {topicId && (
          <Button variant="soft" size="lg" render={<Link href={`/ask?mode=explain_topic&topic=${topicId}`} />}>
            <RotateCcw /> {t("repeatTopic")}
          </Button>
        )}
        <Button variant="ghost" size="lg" render={<Link href="/home" />}>
          <Home /> {t("home")}
        </Button>
      </div>
    </section>
  );
}
