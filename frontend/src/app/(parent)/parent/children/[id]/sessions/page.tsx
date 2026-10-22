"use client";

import { use, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { SessionCard } from "@/components/cards/SessionCard";
import { useChild, useChildSessions, type ChildSessionsFilter } from "@/features/parent/api";
import { cn } from "@/lib/utils";

const FILTERS: Array<{ key: NonNullable<ChildSessionsFilter["status"]>; label: string }> = [
  { key: "", label: "all" },
  { key: "active", label: "active" },
  { key: "completed", label: "completed" },
  { key: "needs_review", label: "needsReview" },
];

export default function ChildSessionsPage({ params }: PageProps<"/parent/children/[id]/sessions">) {
  const { id } = use(params);
  const t = useTranslations("parent.sessions");
  const th = useTranslations("history");
  const searchParams = useSearchParams();
  const subject = searchParams.get("subject") ?? undefined;
  const [status, setStatus] = useState<NonNullable<ChildSessionsFilter["status"]>>("");
  const child = useChild(id);
  const query = useChildSessions(id, { status, subject });
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  const subjectName = subject ? (items[0]?.subject?.name ?? subject) : null;

  return (
    <div>
      <PageHeader
        title={child.data ? t("titleFor", { name: child.data.nickname }) : t("title")}
        subtitle={subjectName ? t("subjectFilter", { subject: subjectName }) : undefined}
        backHref={`/parent/children/${id}`}
      />
      <div role="tablist" className="no-scrollbar mb-4 flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            role="tab"
            aria-selected={status === f.key}
            onClick={() => setStatus(f.key)}
            className={cn(
              "tap-target shrink-0 rounded-full px-4 text-sm font-semibold transition-colors",
              status === f.key ? "bg-teal text-white" : "bg-white text-foreground ring-1 ring-line hover:bg-muted",
            )}
          >
            {t(`filters.${f.label}`)}
          </button>
        ))}
      </div>

      {query.isPending && (
        <div className="flex flex-col gap-3">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {query.data && items.length === 0 && <EmptyState icon={<History />} text={t("empty")} />}
      {items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map((s) => (
            <li key={s.id}>
              <SessionCard session={s} href={`/parent/children/${id}/sessions/${s.id}`} />
            </li>
          ))}
        </ul>
      )}
      {query.hasNextPage && (
        <Button
          variant="outline"
          className="mt-4 w-full"
          onClick={() => query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
        >
          {th("loadMore")}
        </Button>
      )}
    </div>
  );
}
