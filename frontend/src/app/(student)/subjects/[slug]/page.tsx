"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { motion } from "motion/react";
import { toast } from "sonner";
import { ArrowLeft, ChevronRight, List, Map as MapIcon, Play } from "lucide-react";
import { SubjectArt } from "@/components/brand/SubjectArt";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/feedback/States";
import { Hero, roundButtonClass } from "@/components/layout/Hero";
import { KnowledgeMap, MapLegend } from "@/components/learning/KnowledgeMap";
import { ProgressRing } from "@/components/learning/ProgressRing";
import { useSubject } from "@/features/curriculum/api";
import { useDashboard } from "@/features/dashboard/api";
import { useKnowledgeMap, useStartQuiz } from "@/features/learning/api";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { MapNode, ProgressStatus } from "@/lib/api/types";

const STATUS_BADGE: Record<ProgressStatus, string> = {
  not_started: "bg-white text-muted-foreground ring-1 ring-line",
  learning: "bg-lime-pale text-ink ring-1 ring-lime-deep",
  completed: "bg-lime text-ink",
  needs_review: "bg-peach text-[#8a4b00]",
  mastered: "bg-lime text-ink",
};

type View = "map" | "list";

export default function SubjectPage({ params }: PageProps<"/subjects/[slug]">) {
  const { slug } = use(params);
  const t = useTranslations("subjects");
  const tm = useTranslations("map");
  const th = useTranslations("home");
  const ta = useTranslations("app");
  const router = useRouter();
  const [view, setView] = useState<View>("map");
  const subject = useSubject(slug);
  const map = useKnowledgeMap(slug);
  const dashboard = useDashboard();
  const startQuiz = useStartQuiz();
  const isPending = subject.isPending || map.isPending;
  const error = subject.error ?? map.error;
  const data = subject.data;
  const route = map.data;
  const done = route ? route.summary.completed + route.summary.mastered : 0;
  const total = route?.summary.total ?? 0;
  const topicsTotal =
    total || (data?.sections.reduce((n, s) => n + s.topics.length, 0) ?? 0);
  const next =
    route?.nodes.find((n) => n.topic_id === route.next_topic_id) ?? null;
  const numberOf = useMemo(
    () =>
      new Map(
        (route?.nodes ?? []).map((node, index) => [node.topic_id, index + 1]),
      ),
    [route],
  );

  async function quizFor(node: MapNode) {
    try {
      const attempt = await startQuiz.mutateAsync(node.topic_id);
      router.push(`/quizzes/${attempt.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Hero>
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={ta("back")}
            onClick={() => router.push("/subjects")}
            className={roundButtonClass()}
          >
            <ArrowLeft />
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-bold tracking-wide text-ink/60 uppercase">
              {data
                ? `${t("subtitle", { grade: data.grade.number })} · ${th("topicsCount", { count: topicsTotal })}`
                : t("title")}
            </p>
            <h1 className="truncate font-heading text-[26px] leading-tight font-extrabold text-teal">
              {data?.name ?? "…"}
            </h1>
          </div>
          {data && (
            <SubjectArt
              icon={data.icon}
              className="float-slow size-16 text-teal"
            />
          )}
        </div>

        {route && total > 0 && (
          <div className="mt-5 rounded-[24px] bg-white/85 p-4 ring-1 ring-teal/10">
            <div className="flex items-center gap-4">
              <ProgressRing value={total ? done / total : 0} size={68}>
                <span className="font-heading text-sm font-extrabold text-teal">
                  {Math.round((done / total) * 100)}%
                </span>
              </ProgressRing>
              <div className="min-w-0 flex-1">
                <p className="font-heading text-base font-extrabold">
                  {tm("progress", { done, total })}
                </p>
                <MapLegend summary={route.summary} className="mt-1" />
              </div>
            </div>
            {next && (
              <Link
                href={`/topics/${next.topic_id}`}
                className="shine relative mt-4 flex items-center gap-3 overflow-hidden rounded-full bg-teal p-1.5 pr-4 text-white transition hover:bg-teal/90"
              >
                <span className="flex size-11 shrink-0 items-center justify-center rounded-full bg-lime text-teal">
                  <Play className="size-5" fill="currentColor" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[10px] font-bold tracking-wide text-white/70 uppercase">
                    {tm("nextStep")}
                  </span>
                  <span className="block truncate text-[15px] font-bold">
                    {next.name}
                  </span>
                </span>
                <ChevronRight className="size-5 shrink-0" />
              </Link>
            )}
          </div>
        )}
      </Hero>

      {isPending && (
        <div className="flex flex-col gap-3">
          <CardSkeleton lines={2} />
          <CardSkeleton lines={3} />
        </div>
      )}
      {error && (
        <ErrorState
          error={error}
          onRetry={() => {
            void subject.refetch();
            void map.refetch();
          }}
        />
      )}
      {data && route && route.nodes.length === 0 && (
        <EmptyState text={t("noTopics")} />
      )}

      {data && route && route.nodes.length > 0 && (
        <>
          <div
            role="tablist"
            className="mx-auto grid w-full max-w-xs grid-cols-2 rounded-full bg-white p-1 shadow-tile ring-1 ring-line"
          >
            {(["map", "list"] as View[]).map((key) => (
              <button
                key={key}
                role="tab"
                aria-selected={view === key}
                onClick={() => setView(key)}
                className={cn(
                  "relative flex h-10 items-center justify-center gap-1.5 rounded-full text-sm font-bold transition-colors",
                  view === key ? "text-white" : "text-foreground",
                )}
              >
                {view === key && (
                  <motion.span
                    layoutId="subject-view-tab"
                    className="absolute inset-0 rounded-full bg-teal"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <span className="relative flex items-center gap-1.5">
                  {key === "map" ? (
                    <MapIcon className="size-4" />
                  ) : (
                    <List className="size-4" />
                  )}
                  {tm(key === "map" ? "tabMap" : "tabList")}
                </span>
              </button>
            ))}
          </div>

          {view === "map" ? (
            <KnowledgeMap
              map={route}
              avatar={dashboard.data?.student.avatar}
              onStartQuiz={quizFor}
              quizPending={startQuiz.isPending}
            />
          ) : (
            <div className="flex flex-col gap-4">
              {data.sections.map((section, sectionIndex) => (
                <section
                  key={section.id}
                  className="rounded-[28px] bg-white p-4 shadow-card ring-1 ring-line"
                >
                  <h2 className="mb-1 flex items-center gap-2 font-heading text-base font-extrabold">
                    <span className="flex size-7 items-center justify-center rounded-[9px] bg-teal text-xs text-white">
                      {sectionIndex + 1}
                    </span>
                    {section.name}
                  </h2>
                  <ul className="divide-y divide-line">
                    {section.topics.map((topic) => (
                      <li key={topic.id}>
                        <Link
                          href={`/topics/${topic.id}`}
                          className="-mx-1 flex min-h-14 items-center gap-3 rounded-xl px-1 py-2.5 transition hover:bg-lime-pale/60"
                        >
                          <span
                            className={cn(
                              "flex size-9 shrink-0 items-center justify-center rounded-[12px] font-heading text-sm font-extrabold",
                              STATUS_BADGE[topic.progress_status],
                            )}
                          >
                            {numberOf.get(topic.id) ?? "·"}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-[15px] leading-snug font-semibold">
                              {topic.name}
                            </span>
                            <span className="block text-xs text-muted-foreground">
                              {t(`topicStatus.${topic.progress_status}`)}
                            </span>
                          </span>
                          <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
