"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Bell, Check, ChevronRight, Copy, Plus, UserRoundPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { DemoBanner } from "@/components/feedback/DemoBanner";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/feedback/States";
import { TopicChip, WeekLine } from "@/components/parent/ProgressBits";
import { useAuth } from "@/features/auth/AuthProvider";
import { useOverview } from "@/features/parent/api";

export default function ParentHomePage() {
  const t = useTranslations("parent");
  const ta = useTranslations("app");
  const th = useTranslations("home");
  const { user } = useAuth();
  const overview = useOverview();
  const [copied, setCopied] = useState(false);

  async function copyCode() {
    if (!overview.data) return;
    try {
      await navigator.clipboard.writeText(overview.data.family_code);
      setCopied(true);
      toast.success(ta("copied"));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(ta("errorGeneric"));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-extrabold">{t("title")}</h1>
        {user && <p className="text-base text-muted-foreground">{t("hello", { name: user.display_name })}</p>}
      </div>

      <DemoBanner />

      {overview.data && overview.data.unread_notifications > 0 && (
        <Link
          href="/parent/notifications"
          className="flex items-center gap-3 rounded-3xl bg-teal px-4 py-3 text-white shadow-card transition hover:bg-teal/90"
        >
          <Bell className="size-5 shrink-0" />
          <span className="flex-1 text-base font-bold">
            {t("overview.unread", { count: overview.data.unread_notifications })}
          </span>
          <ChevronRight className="size-5" />
        </Link>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-extrabold">{t("children")}</h2>
          <Button size="sm" render={<Link href="/parent/children/new" />}>
            <Plus /> {t("addChild")}
          </Button>
        </div>
        {overview.isPending && (
          <div className="flex flex-col gap-3">
            <CardSkeleton lines={2} />
          </div>
        )}
        {overview.isError && <ErrorState error={overview.error} onRetry={() => overview.refetch()} />}
        {overview.data && overview.data.children.length === 0 && (
          <EmptyState
            icon={<UserRoundPlus />}
            text={t("noChildren")}
            action={
              <Button render={<Link href="/parent/children/new" />}>
                <Plus /> {t("addChild")}
              </Button>
            }
          />
        )}
        {overview.data && overview.data.children.length > 0 && (
          <ul className="flex flex-col gap-3">
            {overview.data.children.map(({ child, summary }) => (
              <li key={child.id}>
                <Link
                  href={`/parent/children/${child.id}`}
                  className="flex items-center gap-4 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line transition hover:bg-teal-soft"
                >
                  <ChildAvatar avatar={child.avatar} size="lg" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-lg font-bold">
                      {child.nickname}
                      <span className="ml-2 text-sm font-semibold text-muted-foreground">
                        {th("grade", { grade: child.grade.number })}
                      </span>
                    </p>
                    <WeekLine summary={summary} />
                    {summary.difficult_topics.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {summary.difficult_topics.slice(0, 2).map((topic) => (
                          <TopicChip key={topic.topic_id} topic={topic} />
                        ))}
                      </div>
                    )}
                  </div>
                  <ChevronRight className="size-5 shrink-0 text-muted-foreground" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-[28px] bg-lime p-5">
        <h2 className="text-base font-extrabold text-teal">{t("familyCodeTitle")}</h2>
        <p className="mt-1 text-sm text-ink/80">{t("familyCodeText")}</p>
        {overview.data && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="rounded-2xl bg-white px-4 py-2.5 font-heading text-2xl font-extrabold tracking-[0.2em] text-teal">
              {overview.data.family_code}
            </span>
            <Button variant="soft" size="sm" onClick={copyCode} aria-label={ta("copy")}>
              {copied ? <Check /> : <Copy />} {ta("copy")}
            </Button>
            <Link href="/parent/settings" className="text-sm font-bold text-teal hover:underline">
              {t("overview.manageCode")}
            </Link>
          </div>
        )}
      </section>
    </div>
  );
}
