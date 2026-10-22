"use client";

import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { toast } from "sonner";
import { AlertTriangle, Bell, CalendarCheck, CheckCheck, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { useMarkRead, useNotifications, useOverview } from "@/features/parent/api";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { NotificationKind, ParentNotification } from "@/lib/api/types";

const KIND_ICON: Record<NotificationKind, LucideIcon> = {
  weekly_report: CalendarCheck,
  difficult_topic: AlertTriangle,
  session_completed: Sparkles,
  consent: ShieldCheck,
  system: Bell,
};

const KIND_TONE: Record<NotificationKind, string> = {
  weekly_report: "bg-teal-soft text-teal",
  difficult_topic: "bg-warning/15 text-warning",
  session_completed: "bg-success/10 text-success",
  consent: "bg-lime text-ink",
  system: "bg-muted text-muted-foreground",
};

function targetFor(item: ParentNotification): string | null {
  if (!item.student_id) return null;
  const sessionId = typeof item.data.session_id === "string" ? item.data.session_id : null;
  if (sessionId) return `/parent/children/${item.student_id}/sessions/${sessionId}`;
  return `/parent/children/${item.student_id}`;
}

export default function NotificationsPage() {
  const t = useTranslations("parent.notifications");
  const th = useTranslations("history");
  const format = useFormatter();
  const query = useNotifications(false);
  const overview = useOverview();
  const markRead = useMarkRead();
  const items = query.data?.pages.flatMap((p) => p.results) ?? [];
  const unread = overview.data?.unread_notifications ?? 0;

  async function readAll() {
    try {
      await markRead.mutateAsync(undefined);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  function onOpen(item: ParentNotification) {
    if (!item.read_at) markRead.mutate(item.id);
  }

  return (
    <div>
      <PageHeader
        title={t("title")}
        back={false}
        action={
          unread > 0 ? (
            <Button variant="ghost" size="sm" onClick={readAll} disabled={markRead.isPending}>
              <CheckCheck /> {t("markAll")}
            </Button>
          ) : undefined
        }
      />
      {query.isPending && (
        <div className="flex flex-col gap-3">
          <CardSkeleton />
          <CardSkeleton />
        </div>
      )}
      {query.isError && <ErrorState error={query.error} onRetry={() => query.refetch()} />}
      {query.data && items.length === 0 && <EmptyState icon={<Bell />} text={t("empty")} />}
      {items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map((item) => {
            const Icon = KIND_ICON[item.kind] ?? Bell;
            const href = targetFor(item);
            const body = (
              <>
                <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-2xl", KIND_TONE[item.kind])}>
                  <Icon className="size-5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className={cn("truncate text-base", item.read_at ? "font-semibold" : "font-extrabold")}>{item.title}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{format.relativeTime(new Date(item.created_at))}</span>
                  </span>
                  <span className="mt-0.5 block text-sm text-muted-foreground">{item.body}</span>
                </span>
                {!item.read_at && <span className="mt-2 size-2.5 shrink-0 rounded-full bg-teal" aria-label={t("unreadDot")} />}
              </>
            );
            const className = cn(
              "flex w-full items-start gap-3 rounded-3xl p-4 text-left shadow-card ring-1 ring-line transition",
              item.read_at ? "bg-white" : "bg-teal-soft/60",
              href && "hover:bg-teal-soft",
            );
            return (
              <li key={item.id}>
                {href ? (
                  <Link href={href} className={className} onClick={() => onOpen(item)}>
                    {body}
                  </Link>
                ) : (
                  <button type="button" className={className} onClick={() => onOpen(item)}>
                    {body}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {query.hasNextPage && (
        <Button variant="outline" className="mt-4 w-full" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
          {th("loadMore")}
        </Button>
      )}
    </div>
  );
}
