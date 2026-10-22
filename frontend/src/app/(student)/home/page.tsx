"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
import {
  Camera,
  ChevronRight,
  HelpCircle,
  ImageUp,
  Keyboard,
  Lightbulb,
  ListChecks,
  NotebookPen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { LogoMark } from "@/components/brand/Logo";
import { DemoBanner } from "@/components/feedback/DemoBanner";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/feedback/States";
import { SessionCard } from "@/components/cards/SessionCard";
import { Hero, roundButtonClass } from "@/components/layout/Hero";
import { SubjectTile } from "@/components/learning/SubjectTile";
import { useDashboard } from "@/features/dashboard/api";

const QUICK = [
  { key: "askQuestion", href: "/ask?mode=question", icon: HelpCircle },
  { key: "explainTopic", href: "/ask?mode=explain_topic", icon: Lightbulb },
  { key: "checkAnswer", href: "/ask?mode=check_answer", icon: ListChecks },
  { key: "examPrep", href: "/ask?mode=exam_prep", icon: NotebookPen },
] as const;

export default function HomePage() {
  const t = useTranslations("home");
  const tn = useTranslations("nav");
  const { data, isPending, isError, error, refetch } = useDashboard();
  const photoAllowed = data?.student.allow_photo_upload ?? true;

  return (
    <div className="flex flex-col gap-6">
      <Hero>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink/70">{t("hello")}</p>
            <p className="truncate font-heading text-xl font-extrabold">
              {data?.student.nickname ?? "…"}
            </p>
          </div>
          {data ? (
            <Link
              href="/profile"
              aria-label={tn("profile")}
              className={roundButtonClass("size-12 overflow-hidden p-0")}
            >
              <ChildAvatar avatar={data.student.avatar} size="md" />
            </Link>
          ) : (
            <LogoMark size={44} />
          )}
        </div>
        <h1 className="mt-5 font-heading text-[32px] leading-[1.1] font-extrabold text-teal">
          {t("heroTitle")}
        </h1>
        <p className="mt-2 text-base text-ink/75">{t("heroText")}</p>

        <Button
          size="xl"
          className="mt-5 w-full"
          render={
              <Link
                href={
                  photoAllowed
                    ? "/assignments/new?source=camera"
                    : "/assignments/new?source=text"
                }
              />
            }
          >
          {photoAllowed ? <Camera /> : <Keyboard />}{" "}
          {photoAllowed ? t("takePhoto") : t("typeTask")}
        </Button>
        {photoAllowed ? (
          <div className="mt-3 flex gap-2">
            <Link
              href="/assignments/new?source=text"
              className="flex h-13 min-w-0 flex-1 items-center gap-3 rounded-full bg-white/90 px-5 text-base text-muted-foreground ring-1 ring-teal/10 transition hover:bg-white"
            >
              <Keyboard className="size-5 shrink-0 text-teal" />
              <span className="truncate">{t("typeHere")}</span>
            </Link>
            <Link
              href="/assignments/new?source=gallery"
              aria-label={t("uploadPhoto")}
              title={t("uploadPhoto")}
              className={roundButtonClass("size-13")}
            >
              <ImageUp className="size-6!" />
            </Link>
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink/70">{t("photoDisabled")}</p>
        )}
      </Hero>

      <DemoBanner />

      {isPending && (
        <>
          <CardSkeleton className="h-24" />
          <div className="grid grid-cols-2 gap-3">
            <CardSkeleton className="aspect-[0.92]" />
            <CardSkeleton className="aspect-[0.92]" />
          </div>
        </>
      )}
      {isError && <ErrorState error={error} onRetry={() => refetch()} />}

      {data && (
        <>
          <section className="rise-in">
            <h2 className="sr-only">{t("quickTitle")}</h2>
            <ul className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
              {QUICK.filter(
                ({ key }) =>
                  data.student.allow_free_questions ||
                  (key !== "askQuestion" && key !== "checkAnswer"),
              ).map(({ key, href, icon: Icon }) => (
                <li key={key} className="shrink-0">
                  <Link
                    href={href}
                    className="flex h-11 items-center gap-2 rounded-full bg-white pr-4 pl-1.5 text-sm font-bold shadow-tile ring-1 ring-line transition hover:bg-lime-pale"
                  >
                    <span className="flex size-8 items-center justify-center rounded-full bg-lime text-teal">
                      <Icon className="size-4" />
                    </span>
                    {t(key)}
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          {data.continue_session && (
            <section className="rise-in rise-in-delay-1">
              <h2 className="mb-3 font-heading text-lg font-extrabold">
                {t("continueTitle")}
              </h2>
              <SessionCard session={data.continue_session} highlight />
            </section>
          )}

          <section className="rise-in rise-in-delay-1">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-lg font-extrabold">
                {t("subjectsTitle")}
              </h2>
              <Link
                href="/subjects"
                className="flex items-center text-sm font-bold text-teal"
              >
                {t("allSubjects")} <ChevronRight className="size-4" />
              </Link>
            </div>
            <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {data.subjects.slice(0, 4).map((subject, i) => (
                <li key={subject.id}>
                  <SubjectTile
                    subject={subject}
                    index={i}
                    caption={t("topicsCount", { count: subject.topics_count })}
                  />
                </li>
              ))}
            </ul>
          </section>

          <section className="rise-in rise-in-delay-2">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-heading text-lg font-extrabold">
                {t("recentTitle")}
              </h2>
              {data.recent_sessions.length > 0 && (
                <Link
                  href="/history"
                  className="flex items-center text-sm font-bold text-teal"
                >
                  {t("allHistory")} <ChevronRight className="size-4" />
                </Link>
              )}
            </div>
            {data.recent_sessions.length === 0 ? (
              <EmptyState icon={<Camera />} text={t("recentEmpty")} />
            ) : (
              <ul className="flex flex-col gap-3">
                {data.recent_sessions.map((s) => (
                  <li key={s.id}>
                    <SessionCard session={s} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}
