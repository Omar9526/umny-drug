"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { AnimatePresence, motion } from "motion/react";
import { BookOpenCheck, Check, ChevronRight, Sparkles, X } from "lucide-react";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type {
  AvatarKey,
  KnowledgeMap as KnowledgeMapData,
  MapNode,
  ProgressStatus,
} from "@/lib/api/types";

const TILE: Record<ProgressStatus, string> = {
  not_started: "bg-white text-ink ring-1 ring-line",
  learning: "bg-lime-pale text-ink ring-1 ring-lime-deep",
  completed: "bg-lime text-ink",
  mastered: "bg-lime text-ink",
  needs_review: "bg-peach text-[#8a4b00] ring-1 ring-warning/30",
};

const SWATCH: Record<ProgressStatus, string> = {
  not_started: "bg-white ring-1 ring-line",
  learning: "bg-lime-pale ring-1 ring-lime-deep",
  completed: "bg-lime",
  mastered: "bg-lime",
  needs_review: "bg-peach ring-1 ring-warning/30",
};

const isDone = (status: ProgressStatus) =>
  status === "completed" || status === "mastered";

/** Status legend with honest counts, square swatches to match the tiles. */
export function MapLegend({
  summary,
  className,
}: {
  summary: KnowledgeMapData["summary"];
  className?: string;
}) {
  const t = useTranslations("subjects.topicStatus");
  const order: ProgressStatus[] = [
    "mastered",
    "completed",
    "learning",
    "needs_review",
    "not_started",
  ];
  return (
    <ul
      className={cn(
        "flex flex-wrap gap-x-3 gap-y-1 text-xs font-semibold text-muted-foreground",
        className,
      )}
    >
      {order
        .filter((status) => summary[status] > 0)
        .map((status) => (
          <li key={status} className="inline-flex items-center gap-1.5">
            <span
              className={cn("size-3 rounded-[5px]", SWATCH[status])}
              aria-hidden
            />
            {t(status)} · {summary[status]}
          </li>
        ))}
    </ul>
  );
}

function groupBySection(nodes: MapNode[]) {
  const sections: Array<{ id: number; name: string; nodes: MapNode[] }> = [];
  for (const node of nodes) {
    const last = sections[sections.length - 1];
    if (last && last.id === node.section.id) last.nodes.push(node);
    else sections.push({ ...node.section, nodes: [node] });
  }
  return sections;
}

function TileBadge({ status }: { status: ProgressStatus }) {
  if (status === "mastered")
    return (
      <span className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-teal text-lime ring-2 ring-white">
        <Sparkles className="size-3" />
      </span>
    );
  if (status === "completed")
    return (
      <span className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-teal text-white ring-2 ring-white">
        <Check className="size-3" strokeWidth={3} />
      </span>
    );
  if (status === "needs_review")
    return (
      <span className="absolute -top-1.5 -right-1.5 flex size-5 items-center justify-center rounded-full bg-warning text-[11px] font-extrabold text-white ring-2 ring-white">
        !
      </span>
    );
  return null;
}

/**
 * The knowledge map as a board game: every section is a level card with numbered square tiles,
 * one per topic. Tiles are coloured by real progress, the child's avatar sits on the next step,
 * and tapping a tile opens a peek panel with the topic's status and actions.
 */
export function KnowledgeMap({
  map,
  avatar,
  interactive = true,
  onStartQuiz,
  quizPending = false,
  className,
}: {
  map: KnowledgeMapData;
  /** Student avatar shown bouncing on the next topic. */
  avatar?: AvatarKey;
  /** Parents get a read-only board: the peek panel shows status only. */
  interactive?: boolean;
  onStartQuiz?: (node: MapNode) => void;
  quizPending?: boolean;
  className?: string;
}) {
  const t = useTranslations("subjects.topicStatus");
  const tm = useTranslations("map");
  const tq = useTranslations("quiz");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const sections = useMemo(() => groupBySection(map.nodes), [map.nodes]);
  const numberOf = useMemo(
    () => new Map(map.nodes.map((node, index) => [node.topic_id, index + 1])),
    [map.nodes],
  );
  const selected =
    map.nodes.find((node) => node.topic_id === selectedId) ?? null;

  useEffect(() => {
    if (selectedId === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedId]);

  return (
    <div className={cn("flex flex-col", className)}>
      {sections.map((section, sectionIndex) => {
        const done = section.nodes.filter((n) => isDone(n.status)).length;
        return (
          <div key={section.id}>
            {sectionIndex > 0 && (
              <div aria-hidden className="flex h-8 justify-center">
                <span className="w-0.5 rounded-full bg-[repeating-linear-gradient(to_bottom,var(--teal)_0_4px,transparent_4px_9px)] opacity-40" />
              </div>
            )}
            <section className="rounded-[28px] bg-white p-4 shadow-card ring-1 ring-line">
              <header className="mb-3 flex items-center gap-3">
                <span className="flex size-9 shrink-0 items-center justify-center rounded-[12px] bg-teal font-heading text-sm font-extrabold text-white">
                  {sectionIndex + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-[11px] font-bold tracking-wide text-muted-foreground uppercase">
                    {tm("level", { n: sectionIndex + 1 })}
                  </p>
                  <h3 className="truncate text-base font-extrabold">
                    {section.name}
                  </h3>
                </div>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-bold",
                    done === section.nodes.length
                      ? "bg-lime text-ink"
                      : "bg-lime-pale text-teal",
                  )}
                >
                  {done}/{section.nodes.length}
                </span>
              </header>
              <ol className="grid grid-cols-5 gap-2.5">
                {section.nodes.map((node) => {
                  const number = numberOf.get(node.topic_id) ?? 0;
                  const isCurrent = node.topic_id === map.next_topic_id;
                  const isSelected = node.topic_id === selectedId;
                  return (
                    <li
                      key={node.topic_id}
                      className={cn("relative", isCurrent && "z-10")}
                    >
                      <button
                        type="button"
                        data-topic-id={node.topic_id}
                        aria-label={`${node.name}: ${t(node.status)}`}
                        aria-pressed={isSelected}
                        onClick={() =>
                          setSelectedId((current) =>
                            current === node.topic_id ? null : node.topic_id,
                          )
                        }
                        className={cn(
                          "pop-in relative flex aspect-square w-full items-center justify-center rounded-[16px] font-heading text-lg font-extrabold transition-[transform,box-shadow] duration-200 active:scale-95",
                          TILE[node.status],
                          isCurrent &&
                            "bg-teal text-white shadow-float ring-0 ring-transparent",
                          isSelected && "scale-105 ring-4 ring-teal/30",
                        )}
                        style={{
                          animationDelay: `${Math.min(number, 30) * 35}ms`,
                        }}
                      >
                        {number}
                        {!isCurrent && <TileBadge status={node.status} />}
                      </button>
                      {isCurrent &&
                        (avatar ? (
                          <span
                            className="bounce-soft pointer-events-none absolute -top-6 left-1/2 -translate-x-1/2"
                            aria-hidden
                          >
                            <ChildAvatar
                              avatar={avatar}
                              size="sm"
                              className="ring-2 ring-white shadow-tile"
                            />
                          </span>
                        ) : (
                          <span
                            className="pointer-events-none absolute -top-1 -right-1 size-3.5 rounded-full bg-lime ring-2 ring-white"
                            aria-hidden
                          />
                        ))}
                    </li>
                  );
                })}
              </ol>
            </section>
          </div>
        );
      })}
      <p className="mt-3 text-center text-xs font-semibold text-muted-foreground">
        {tm("tapHint")}
      </p>

      <AnimatePresence>
        {selected && (
          <motion.div
            key={selected.topic_id}
            role="dialog"
            aria-modal="false"
            aria-label={selected.name}
            initial={{ y: 48, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 48, opacity: 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className="fixed inset-x-4 bottom-[92px] z-30 mx-auto max-w-md rounded-[28px] bg-white p-5 shadow-float ring-1 ring-line md:bottom-8"
          >
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  "flex size-12 shrink-0 items-center justify-center rounded-[16px] font-heading text-lg font-extrabold",
                  selected.topic_id === map.next_topic_id
                    ? "bg-teal text-white"
                    : TILE[selected.status],
                )}
              >
                {numberOf.get(selected.topic_id)}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-bold tracking-wide text-muted-foreground uppercase">
                  {selected.section.name}
                </p>
                <h4 className="text-base leading-snug font-extrabold">
                  {selected.name}
                </h4>
                <div className="mt-1.5 flex flex-wrap gap-1.5 text-xs font-bold">
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-1",
                      TILE[selected.status],
                    )}
                  >
                    {t(selected.status)}
                  </span>
                  {selected.topic_id === map.next_topic_id && (
                    <span className="rounded-full bg-teal px-2.5 py-1 text-white">
                      {tm("nextStep")}
                    </span>
                  )}
                  {selected.last_quiz && (
                    <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
                      {tm("quizScore", {
                        correct: selected.last_quiz.correct_count,
                        total: selected.last_quiz.total_count,
                      })}
                    </span>
                  )}
                </div>
              </div>
              <button
                type="button"
                aria-label={tm("close")}
                onClick={() => setSelectedId(null)}
                className="flex size-11 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground transition hover:bg-line"
              >
                <X className="size-4" />
              </button>
            </div>
            {interactive && (
              <div
                className={cn(
                  "mt-4 grid gap-2",
                  onStartQuiz ? "grid-cols-2" : "grid-cols-1",
                )}
              >
                <Button
                  size="lg"
                  render={<Link href={`/topics/${selected.topic_id}`} />}
                >
                  {tm("open")} <ChevronRight />
                </Button>
                {onStartQuiz && (
                  <Button
                    size="lg"
                    variant="lime"
                    onClick={() => onStartQuiz(selected)}
                    disabled={quizPending}
                  >
                    <BookOpenCheck /> {tq("title")}
                  </Button>
                )}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
