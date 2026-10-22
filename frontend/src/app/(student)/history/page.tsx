"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { History } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { SessionCard } from "@/components/cards/SessionCard";
import { useHistory } from "@/features/dashboard/api";
import { cn } from "@/lib/utils";
import type { SessionStatus } from "@/lib/api/types";

const FILTERS: Array<{ key: "" | SessionStatus; label: string }> = [
  { key: "", label: "all" },
  { key: "active", label: "status.active" },
  { key: "completed", label: "status.completed" },
];

export default function HistoryPage() {
  const t = useTranslations("history");
  const ts = useTranslations("session");
  const [filter, setFilter] = useState<"" | SessionStatus>("");
  const query = useHistory(filter);
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];

  return (
    <div>
      <PageHeader title={t("title")} back={false} />
      <div role="tablist" className="no-scrollbar mb-4 flex gap-2 overflow-x-auto">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            role="tab"
            aria-selected={filter === f.key}
            onClick={() => setFilter(f.key)}
            className={cn(
              "tap-target shrink-0 rounded-full px-4 text-sm font-semibold transition-colors",
              filter === f.key ? "bg-teal text-white" : "bg-white text-foreground ring-1 ring-line hover:bg-muted",
            )}
          >
            {f.key === "" ? t("all") : ts(f.label)}
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
      {query.data && items.length === 0 && (
        <EmptyState icon={<History />} text={filter ? t("emptyFiltered") : t("empty")} />
      )}
      {items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map((s) => (
            <li key={s.id}>
              <SessionCard session={s} />
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
          {t("loadMore")}
        </Button>
      )}
    </div>
  );
}
