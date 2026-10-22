"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import {
  AlertTriangle,
  BookOpenCheck,
  Camera,
  Lightbulb,
  Sparkles,
  TrendingDown,
  type LucideIcon,
} from "lucide-react";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { cn } from "@/lib/utils";
import type {
  ChildSummary,
  DifficultTopic,
  Recommendation,
  SubjectBreakdown,
} from "@/lib/api/types";

/** Three honest numbers for the week: solved alone / with hints / needs review. */
export function WeekTiles({
  independent,
  withHelp,
  needsReview,
  className,
}: {
  independent: number;
  withHelp: number;
  needsReview: number;
  className?: string;
}) {
  const t = useTranslations("parent.progress.stats");
  const tiles = [
    {
      key: "independent",
      value: independent,
      tone: "bg-success/10 text-success",
    },
    { key: "withHelp", value: withHelp, tone: "bg-lime text-ink" },
    {
      key: "needsReview",
      value: needsReview,
      tone: "bg-warning/15 text-warning",
    },
  ] as const;
  return (
    <div className={cn("grid grid-cols-3 gap-2", className)}>
      {tiles.map((tile) => (
        <div
          key={tile.key}
          className={cn("rounded-2xl px-3 py-3 text-center", tile.tone)}
        >
          <p className="font-heading text-2xl font-extrabold leading-none">
            {tile.value}
          </p>
          <p className="mt-1 text-xs font-semibold">{t(tile.key)}</p>
        </div>
      ))}
    </div>
  );
}

/** One-line week summary for a child card on the overview. */
export function WeekLine({ summary }: { summary: ChildSummary }) {
  const t = useTranslations("parent.overview");
  const format = useFormatter();
  if (summary.sessions_total === 0) {
    return <p className="text-sm text-muted-foreground">{t("noActivity")}</p>;
  }
  if (summary.sessions_week === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        {t("lastActivity", {
          time: summary.last_activity_at
            ? format.relativeTime(new Date(summary.last_activity_at))
            : "",
        })}
      </p>
    );
  }
  const parts = [
    summary.independent_week > 0 &&
      `${summary.independent_week} ${t("independent")}`,
    summary.with_help_week > 0 && `${summary.with_help_week} ${t("withHelp")}`,
    summary.needs_review_week > 0 &&
      `${summary.needs_review_week} ${t("needsReview")}`,
  ].filter(Boolean);
  return (
    <p className="text-sm text-muted-foreground">
      <span className="font-semibold text-foreground">
        {t("week")}: {t("sessionsWeek", { count: summary.sessions_week })}
      </span>
      {parts.length > 0 && ` · ${parts.join(" · ")}`}
    </p>
  );
}

export function TopicChip({ topic }: { topic: DifficultTopic }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full bg-warning/15 px-2.5 py-1 text-xs font-semibold text-warning">
      <AlertTriangle className="size-3 shrink-0" />
      <span className="truncate">{topic.name}</span>
    </span>
  );
}

export function SubjectRow({ row }: { row: SubjectBreakdown }) {
  const t = useTranslations("parent.progress");
  const share =
    row.completed > 0 ? Math.round((row.independent / row.completed) * 100) : 0;
  return (
    <li className="flex items-center gap-3 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line">
      <SubjectIcon icon={row.subject.icon} color={row.subject.color} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <p className="truncate text-base font-bold">{row.subject.name}</p>
          <p className="shrink-0 text-xs font-semibold text-muted-foreground">
            {t("sessionsCount", { count: row.sessions })}
          </p>
        </div>
        <div
          className="mt-2 h-2 overflow-hidden rounded-full bg-muted"
          aria-hidden
        >
          <div
            className="h-full rounded-full bg-success transition-[width]"
            style={{ width: `${share}%` }}
          />
        </div>
        <p className="mt-1.5 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
          <span>{t("independentShare", { percent: share })}</span>
          {row.needs_review > 0 && (
            <span className="font-semibold text-warning">
              {t("needsReviewCount", { count: row.needs_review })}
            </span>
          )}
          {row.hints_avg > 0 && (
            <span>{t("hintsAvg", { count: row.hints_avg })}</span>
          )}
        </p>
      </div>
    </li>
  );
}

export function DifficultTopicRow({ topic }: { topic: DifficultTopic }) {
  const t = useTranslations("parent.progress");
  const format = useFormatter();
  return (
    <li className="flex items-center gap-3 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line">
      <SubjectIcon
        icon={topic.subject?.icon ?? "book-open"}
        color={topic.subject?.color ?? "sage"}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-base font-bold">{topic.name}</p>
        <p className="truncate text-xs text-muted-foreground">
          {topic.subject?.name}
          {typeof topic.attempts_count === "number" &&
            ` · ${t("attempts", { count: topic.attempts_count })}`}
          {typeof topic.hints_count === "number" &&
            topic.hints_count > 0 &&
            ` · ${t("hints", { count: topic.hints_count })}`}
        </p>
      </div>
      {topic.last_activity_at && (
        <span className="shrink-0 text-xs text-muted-foreground">
          {format.relativeTime(new Date(topic.last_activity_at))}
        </span>
      )}
    </li>
  );
}

const RECOMMENDATION_ICON: Record<Recommendation["kind"], LucideIcon> = {
  review_topic: AlertTriangle,
  review_session: BookOpenCheck,
  too_many_reveals: TrendingDown,
  doing_great: Sparkles,
  inactive: Camera,
  subject_needs_support: Lightbulb,
};

const RECOMMENDATION_TONE: Record<Recommendation["kind"], string> = {
  review_topic: "bg-warning/15 text-warning",
  review_session: "bg-warning/15 text-warning",
  too_many_reveals: "bg-destructive/10 text-destructive",
  doing_great: "bg-success/10 text-success",
  inactive: "bg-teal-soft text-teal",
  subject_needs_support: "bg-lime text-ink",
};

export function RecommendationCard({
  item,
  childId,
}: {
  item: Recommendation;
  childId: string;
}) {
  const t = useTranslations("parent.progress");
  const Icon = RECOMMENDATION_ICON[item.kind];
  const action = item.action;
  const href =
    action?.type === "explain_topic" || action?.type === "subject"
      ? `/parent/children/${childId}/sessions?subject=${encodeURIComponent(action.subject_slug)}`
      : action?.type === "session"
        ? `/parent/children/${childId}/sessions/${action.session_id}`
        : null;
  const linkLabel =
    action?.type === "session" ? t("actionSession") : t("actionSessions");
  return (
    <li className="flex gap-3 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line">
      <span
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-2xl",
          RECOMMENDATION_TONE[item.kind],
        )}
      >
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-base font-bold">{item.title}</p>
        <p className="mt-0.5 text-sm text-muted-foreground">{item.text}</p>
        {href && (
          <Link
            href={href}
            className="mt-2 inline-block text-sm font-bold text-teal hover:underline"
          >
            {linkLabel} →
          </Link>
        )}
      </div>
    </li>
  );
}
