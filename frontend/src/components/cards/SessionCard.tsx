"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { ChevronRight } from "lucide-react";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { cn } from "@/lib/utils";
import type { SessionSummary } from "@/lib/api/types";

const STATUS_STYLES: Record<SessionSummary["status"], string> = {
  active: "bg-lime text-ink",
  completed: "bg-teal text-white",
  abandoned: "bg-muted text-muted-foreground",
};

export function SessionCard({
  session,
  highlight,
  href,
}: {
  session: SessionSummary;
  highlight?: boolean;
  /** Override the target, e.g. the parent's read-only view. */
  href?: string;
}) {
  const t = useTranslations("session");
  const th = useTranslations("home");
  const format = useFormatter();
  const title = session.title || session.topic_name || session.subject?.name || t(`mode.${session.mode}`);
  const needsReview = session.outcome === "needs_review";

  return (
    <Link
      href={href ?? `/sessions/${session.id}`}
      className={cn(
        "flex items-center gap-3 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line transition hover:bg-teal-soft",
        highlight && "ring-2 ring-teal",
      )}
    >
      <SubjectIcon icon={session.subject?.icon ?? "book-open"} color={session.subject?.color ?? "sage"} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-base font-bold">{title}</p>
        <p className="truncate text-sm text-muted-foreground">
          {session.assignment_text ?? session.subject?.name ?? t(`mode.${session.mode}`)}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs font-semibold">
          <span className={cn("rounded-full px-2 py-0.5", needsReview ? "bg-warning/15 text-warning" : STATUS_STYLES[session.status])}>
            {needsReview ? t("outcome.needs_review") : t(`status.${session.status}`)}
          </span>
          {session.status === "completed" && session.outcome && session.outcome !== "needs_review" && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-muted-foreground">{t(`outcome.${session.outcome}`)}</span>
          )}
          <span className="text-muted-foreground">
            {format.relativeTime(new Date(session.last_activity_at))}
          </span>
        </div>
      </div>
      {highlight ? (
        <span className="rounded-full bg-teal px-3 py-1.5 text-sm font-bold text-white">{th("continue")}</span>
      ) : (
        <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
      )}
    </Link>
  );
}
