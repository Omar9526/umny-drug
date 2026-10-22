"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { KnowledgeMap, MapLegend } from "@/components/learning/KnowledgeMap";
import { useSubjects } from "@/features/curriculum/api";
import { useKnowledgeMap } from "@/features/learning/api";
import { useChild } from "@/features/parent/api";
import { cn } from "@/lib/utils";

export default function ParentMapPage({
  params,
}: PageProps<"/parent/children/[id]/map">) {
  const { id } = use(params);
  const t = useTranslations("parent.map");
  const tm = useTranslations("map");
  const child = useChild(id);
  const subjects = useSubjects(child.data?.grade.id, { waitForGrade: true });
  const [chosen, setChosen] = useState<string | null>(null);
  const slug = chosen ?? subjects.data?.[0]?.slug ?? null;
  const map = useKnowledgeMap(slug, id);
  const done = map.data
    ? map.data.summary.completed + map.data.summary.mastered
    : 0;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={
          child.data ? t("title", { name: child.data.nickname }) : tm("title")
        }
        backHref={`/parent/children/${id}`}
      />
      {(child.isLoading || subjects.isLoading) && <CardSkeleton lines={2} />}
      {child.isError && (
        <ErrorState error={child.error} onRetry={() => child.refetch()} />
      )}
      {subjects.isError && (
        <ErrorState error={subjects.error} onRetry={() => subjects.refetch()} />
      )}
      {subjects.data && subjects.data.length === 0 && (
        <EmptyState text={t("noSubjects")} />
      )}
      {subjects.data && subjects.data.length > 0 && (
        <div
          role="tablist"
          aria-label={t("subject")}
          className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1"
        >
          {subjects.data.map((subject) => (
            <button
              key={subject.id}
              role="tab"
              aria-selected={slug === subject.slug}
              onClick={() => setChosen(subject.slug)}
              className={cn(
                "tap-target inline-flex shrink-0 items-center gap-2 rounded-full pr-4 pl-1.5 text-sm font-semibold transition-colors",
                slug === subject.slug
                  ? "bg-teal text-white"
                  : "bg-white text-foreground ring-1 ring-line hover:bg-muted",
              )}
            >
              <SubjectIcon
                icon={subject.icon}
                color={subject.color}
                size="sm"
              />
              {subject.name}
            </button>
          ))}
        </div>
      )}
      {slug && map.isLoading && <CardSkeleton lines={4} />}
      {map.isError && (
        <ErrorState error={map.error} onRetry={() => map.refetch()} />
      )}
      {map.data && (
        <>
          <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-base font-extrabold">
                {tm("progress", { done, total: map.data.summary.total })}
              </h2>
              <span className="text-sm font-semibold text-muted-foreground">
                {map.data.summary.total
                  ? Math.round((done / map.data.summary.total) * 100)
                  : 0}
                %
              </span>
            </div>
            <div
              className="mt-2 h-2.5 overflow-hidden rounded-full bg-muted"
              aria-hidden
            >
              <div
                className="h-full rounded-full bg-teal transition-[width]"
                style={{
                  width: `${map.data.summary.total ? (done / map.data.summary.total) * 100 : 0}%`,
                }}
              />
            </div>
            <MapLegend summary={map.data.summary} className="mt-3" />
          </section>
          {map.data.nodes.length === 0 ? (
            <EmptyState text={t("noTopics")} />
          ) : (
            <KnowledgeMap map={map.data} interactive={false} />
          )}
        </>
      )}
    </div>
  );
}
