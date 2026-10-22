"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { QuizAttempt } from "@/lib/api/types";

export type QuizTileState = "correct" | "wrong" | "current" | "open";

const TILE: Record<QuizTileState, string> = {
  correct: "bg-lime text-ink",
  wrong: "bg-peach text-[#8a4b00] ring-1 ring-warning/30",
  current: "bg-teal text-white shadow-float",
  open: "bg-white text-ink ring-1 ring-line",
};

export function quizTileState(
  attempt: QuizAttempt,
  index: number,
  current?: number,
): QuizTileState {
  const result = attempt.results[String(attempt.questions[index].id)];
  if (result) return result.correct ? "correct" : "wrong";
  return index === current ? "current" : "open";
}

/**
 * Numbered question tiles (the «Quiz Progress» board): lime = answered correctly, peach = mistake,
 * teal = the question on screen, white = not answered yet. With `onSelect` the tiles navigate.
 */
export function QuizProgressGrid({
  attempt,
  current,
  onSelect,
  size = "sm",
  className,
}: {
  attempt: QuizAttempt;
  current?: number;
  onSelect?: (index: number) => void;
  size?: "sm" | "lg";
  className?: string;
}) {
  const t = useTranslations("quiz");
  return (
    <ol
      className={cn(
        size === "sm" ? "flex flex-wrap gap-2" : "grid grid-cols-5 gap-2.5",
        className,
      )}
      aria-label={t("answersTitle")}
    >
      {attempt.questions.map((question, index) => {
        const state = quizTileState(attempt, index, current);
        return (
          <li key={question.id}>
            <button
              type="button"
              aria-label={`${t("goTo", { n: index + 1 })}: ${t(`legend.${state === "open" ? "skipped" : state}`)}`}
              aria-current={state === "current" ? "step" : undefined}
              onClick={() => onSelect?.(index)}
              disabled={!onSelect}
              className={cn(
                "pop-in flex items-center justify-center font-heading font-extrabold transition-transform active:scale-95 disabled:cursor-default",
                size === "sm"
                  ? "size-11 rounded-[14px] text-base"
                  : "aspect-square w-full rounded-[18px] text-xl",
                TILE[state],
              )}
              style={{ animationDelay: `${index * 50}ms` }}
            >
              {index + 1}
            </button>
          </li>
        );
      })}
    </ol>
  );
}

export function QuizLegend({
  items,
  className,
}: {
  items: QuizTileState[];
  className?: string;
}) {
  const t = useTranslations("quiz.legend");
  return (
    <ul
      className={cn(
        "flex flex-wrap gap-x-4 gap-y-1.5 text-xs font-semibold text-muted-foreground",
        className,
      )}
    >
      {items.map((state) => (
        <li key={state} className="inline-flex items-center gap-1.5">
          <span className={cn("size-3.5 rounded-[5px]", TILE[state])} aria-hidden />
          {t(state === "open" ? "skipped" : state)}
        </li>
      ))}
    </ul>
  );
}
