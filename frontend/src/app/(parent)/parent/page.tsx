"use client";

import { useState } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Bell, Check, ChevronRight, Copy, Plus, UserRoundPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { LogoMark } from "@/components/brand/Logo";
import { DemoBanner } from "@/components/feedback/DemoBanner";
import { CardSkeleton, EmptyState, ErrorState } from "@/components/feedback/States";
import { Hero } from "@/components/layout/Hero";
import { InstallPrompt } from "@/components/pwa/InstallPrompt";
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
      <Hero>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink/70">{t("title")}</p>
            {user && (
              <p className="truncate font-heading text-xl font-extrabold">{t("hello", { name: user.display_name })}</p>
            )}
          </div>
          <LogoMark size={44} />
        </div>
        <h1 className="mt-5 font-heading text-[30px] leading-[1.1] font-extrabold text-teal">{t("heroTitle")}</h1>
        <p className="mt-2 text-base text-ink/75">{t("familyCodeText")}</p>
        {overview.data && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-white px-4 py-2 font-heading text-xl font-extrabold tracking-[0.18em] text-teal ring-1 ring-teal/10">
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
      </Hero>
      <InstallPrompt />

      <DemoBanner />

      {overview.data && overview.data.unread_notifications > 0 && (
        <Link
          href="/parent/notifications"
          className="rise-in flex items-center gap-3 rounded-full bg-teal py-2 pr-4 pl-2 text-white shadow-float transition hover:bg-teal/90"
        >
          <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-lime text-teal">
            <Bell className="size-5" />
          </span>
          <span className="flex-1 text-base font-bold">
            {t("overview.unread", { count: overview.data.unread_notifications })}
          </span>
          <ChevronRight className="size-5" />
        </Link>
      )}

      <section className="rise-in rise-in-delay-1">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-heading text-lg font-extrabold">{t("children")}</h2>
          <Button size="sm" variant="lime" render={<Link href="/parent/children/new" />}>
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
            {overview.data.children.map(({ child, summary }, index) => (
              <li key={child.id} className="pop-in" style={{ animationDelay: `${index * 70}ms` }}>
                <Link
                  href={`/parent/children/${child.id}`}
                  className="flex items-center gap-4 rounded-[28px] bg-white p-4 shadow-card ring-1 ring-line transition hover:-translate-y-0.5 hover:bg-lime-pale/60"
                >
                  <ChildAvatar avatar={child.avatar} size="lg" className="ring-4 ring-lime-pale" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-heading text-lg font-extrabold">
                      {child.nickname}
                      <span className="ml-2 font-sans text-sm font-semibold text-muted-foreground">
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
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-teal text-white">
                    <ChevronRight className="size-5" />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
