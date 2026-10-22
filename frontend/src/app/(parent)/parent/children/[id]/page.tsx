"use client";

import { use } from "react";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import {
  BookOpenCheck,
  CalendarDays,
  Map,
  Settings,
  Sparkles,
} from "lucide-react";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { SessionCard } from "@/components/cards/SessionCard";
import {
  DifficultTopicRow,
  RecommendationCard,
  SubjectRow,
  WeekTiles,
} from "@/components/parent/ProgressBits";
import { useChildProgress } from "@/features/parent/api";

export default function ChildProgressPage({
  params,
}: PageProps<"/parent/children/[id]">) {
  const { id } = use(params);
  const t = useTranslations("parent.progress");
  const th = useTranslations("home");
  const format = useFormatter();
  const query = useChildProgress(id);

  if (query.isPending) {
    return (
      <div>
        <PageHeader title={t("title")} backHref="/parent" />
        <div className="flex flex-col gap-3">
          <CardSkeleton lines={3} />
          <CardSkeleton lines={2} />
        </div>
      </div>
    );
  }
  if (query.isError) {
    return (
      <div>
        <PageHeader title={t("title")} backHref="/parent" />
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      </div>
    );
  }

  const {
    child,
    summary,
    weekly_report: report,
    recommendations,
    subjects,
    difficult_topics,
    recent_sessions,
    recent_quizzes,
  } = query.data;
  const period = `${format.dateTime(new Date(report.period_start), { day: "numeric", month: "short" })} – ${format.dateTime(
    new Date(report.period_end),
    { day: "numeric", month: "short" },
  )}`;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={child.nickname}
        subtitle={`${th("grade", { grade: child.grade.number })} · ${child.explanation_language.toUpperCase()}`}
        backHref="/parent"
        action={
          <div className="flex gap-2">
            <Button
              variant="soft"
              size="sm"
              render={<Link href={`/parent/children/${id}/map`} />}
            >
              <Map /> {t("map")}
            </Button>
            <Button
              variant="soft"
              size="sm"
              aria-label={t("settings")}
              render={<Link href={`/parent/children/${id}/settings`} />}
            >
              <Settings />
            </Button>
          </div>
        }
      />

      <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <div className="flex items-center gap-3">
          <ChildAvatar avatar={child.avatar} size="lg" />
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-extrabold">{t("report")}</h2>
            <p className="flex items-center gap-1 text-xs font-semibold text-muted-foreground">
              <CalendarDays className="size-3.5" /> {period}
            </p>
          </div>
        </div>
        <p className="mt-4 text-base leading-relaxed">{report.text}</p>
        {report.has_data && (
          <WeekTiles
            className="mt-4"
            independent={report.independent}
            withHelp={report.with_help}
            needsReview={report.needs_review}
          />
        )}
        {summary.sessions_total > 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            {t("totals", {
              total: summary.sessions_total,
              independent: summary.independent_total,
            })}
          </p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-extrabold">{t("recommendations")}</h2>
        {recommendations.length === 0 ? (
          <EmptyState
            icon={<Sparkles />}
            text={
              summary.sessions_total === 0
                ? t("noDataYet")
                : t("noRecommendations")
            }
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {recommendations.map((item, index) => (
              <RecommendationCard
                key={`${item.kind}-${index}`}
                item={item}
                childId={id}
              />
            ))}
          </ul>
        )}
      </section>

      {subjects.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-extrabold">{t("subjects")}</h2>
          <ul className="flex flex-col gap-3">
            {subjects.map((row) => (
              <SubjectRow key={row.subject.id} row={row} />
            ))}
          </ul>
        </section>
      )}

      {difficult_topics.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-extrabold">
            {t("difficultTopics")}
          </h2>
          <ul className="flex flex-col gap-3">
            {difficult_topics.map((topic) => (
              <DifficultTopicRow key={topic.topic_id} topic={topic} />
            ))}
          </ul>
        </section>
      )}

      {recent_quizzes.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-extrabold">{t("quizzes")}</h2>
          <ul className="flex flex-col gap-2">
            {recent_quizzes.map((quiz) => (
              <li
                key={quiz.id}
                className="flex items-center gap-3 rounded-3xl bg-white px-4 py-3 shadow-card ring-1 ring-line"
              >
                <SubjectIcon
                  icon={quiz.subject.icon}
                  color={quiz.subject.color}
                  size="sm"
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-base font-bold">
                    {quiz.topic_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {format.relativeTime(new Date(quiz.finished_at))}
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ${
                    quiz.score >= 0.8
                      ? "bg-success/10 text-success"
                      : quiz.score >= 0.5
                        ? "bg-lime text-ink"
                        : "bg-warning/15 text-warning"
                  }`}
                >
                  <BookOpenCheck className="size-3.5" />{" "}
                  {t("quizScore", {
                    correct: quiz.correct_count,
                    total: quiz.total_count,
                  })}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-extrabold">{t("recent")}</h2>
          {recent_sessions.length > 0 && (
            <Link
              href={`/parent/children/${id}/sessions`}
              className="text-sm font-bold text-teal hover:underline"
            >
              {t("allSessions")}
            </Link>
          )}
        </div>
        {recent_sessions.length === 0 ? (
          <EmptyState text={t("noSessions", { name: child.nickname })} />
        ) : (
          <ul className="flex flex-col gap-3">
            {recent_sessions.map((session) => (
              <li key={session.id}>
                <SessionCard
                  session={session}
                  href={`/parent/children/${id}/sessions/${session.id}`}
                />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
