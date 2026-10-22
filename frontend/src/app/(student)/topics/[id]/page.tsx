"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useFormatter, useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  ArrowLeft,
  BookOpenCheck,
  GraduationCap,
  Lightbulb,
  Map,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubjectArt } from "@/components/brand/SubjectArt";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { Hero, roundButtonClass } from "@/components/layout/Hero";
import { SessionCard } from "@/components/cards/SessionCard";
import { useTopic } from "@/features/curriculum/api";
import { useStartQuiz } from "@/features/learning/api";
import { useCreateSession } from "@/features/tutor/api";
import { ApiError, getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { ProgressStatus } from "@/lib/api/types";

const STATUS_CHIP: Record<ProgressStatus, string> = {
  not_started: "bg-white/80 text-ink/70",
  learning: "bg-lime-pale text-ink ring-1 ring-lime-deep",
  completed: "bg-teal text-white",
  needs_review: "bg-peach text-[#8a4b00]",
  mastered: "bg-teal text-lime",
};

export default function TopicPage({ params }: PageProps<"/topics/[id]">) {
  const { id } = use(params);
  const topicId = Number(id);
  const t = useTranslations("topic");
  const ts = useTranslations("subjects");
  const ta = useTranslations("app");
  const format = useFormatter();
  const router = useRouter();
  const topic = useTopic(Number.isFinite(topicId) ? topicId : null);
  const createSession = useCreateSession();
  const startQuiz = useStartQuiz();
  const [quizNotice, setQuizNotice] = useState<string | null>(null);

  async function explain() {
    if (!topic.data) return;
    try {
      const session = await createSession.mutateAsync({
        mode: "explain_topic",
        subject_slug: topic.data.subject.slug,
        topic_id: topic.data.id,
        question: "",
      });
      router.push(`/sessions/${session.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function quiz() {
    if (!topic.data) return;
    setQuizNotice(null);
    try {
      const attempt = await startQuiz.mutateAsync(topic.data.id);
      router.push(`/quizzes/${attempt.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        // demo_mode, budget_exceeded, family_budget_exceeded, student_limit_exceeded, quiz_generating
        setQuizNotice(error.message);
        return;
      }
      toast.error(getErrorMessage(error));
    }
  }

  const data = topic.data;
  const backHref = data ? `/subjects/${data.subject.slug}` : "/subjects";
  const busy = createSession.isPending || startQuiz.isPending;

  return (
    <div className="flex flex-col gap-5">
      <Hero>
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label={ta("back")}
            onClick={() => router.push(backHref)}
            className={roundButtonClass()}
          >
            <ArrowLeft />
          </button>
          <p className="min-w-0 flex-1 truncate text-xs font-bold tracking-wide text-ink/60 uppercase">
            {data ? `${data.subject.name} · ${data.section.name}` : "…"}
          </p>
          {data && (
            <SubjectArt
              icon={data.subject.icon}
              className="float-slow size-14 text-teal"
            />
          )}
        </div>
        <h1 className="mt-4 font-heading text-[28px] leading-[1.15] font-extrabold text-teal">
          {data?.name ?? "…"}
        </h1>
        {data && (
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
            <span
              className={cn(
                "rounded-full px-3 py-1.5",
                STATUS_CHIP[data.progress_status],
              )}
            >
              {ts(`topicStatus.${data.progress_status}`)}
            </span>
            <span className="rounded-full bg-white/80 px-3 py-1.5 text-ink/70">
              {t(`difficulty.${data.difficulty}`)}
            </span>
            {data.last_quiz && (
              <span className="rounded-full bg-white/80 px-3 py-1.5 text-ink/70">
                {t("lastQuiz")}: {data.last_quiz.correct_count}/
                {data.last_quiz.total_count}
              </span>
            )}
          </div>
        )}
      </Hero>

      {topic.isLoading && <CardSkeleton lines={4} />}
      {(topic.isError || !Number.isFinite(topicId)) && (
        <ErrorState error={topic.error} onRetry={() => topic.refetch()} />
      )}

      {data && (
        <>
          <section className="rise-in rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
            <h2 className="font-heading text-base font-extrabold">
              {t("about")}
            </h2>
            {data.description ? (
              <p className="mt-2 text-base leading-relaxed">{data.description}</p>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                {t("noDescription")}
              </p>
            )}
            <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <div className="rounded-2xl bg-lime-pale px-4 py-3">
                <dt className="text-xs font-semibold text-muted-foreground">
                  {t("sessions")}
                </dt>
                <dd className="font-heading text-2xl font-extrabold text-teal">
                  {data.progress?.sessions_count ?? 0}
                </dd>
              </div>
              <div className="rounded-2xl bg-lime-pale px-4 py-3">
                <dt className="text-xs font-semibold text-muted-foreground">
                  {t("lastQuiz")}
                </dt>
                <dd className="font-heading text-2xl font-extrabold text-teal">
                  {data.last_quiz
                    ? `${data.last_quiz.correct_count}/${data.last_quiz.total_count}`
                    : "—"}
                </dd>
                {data.last_quiz?.finished_at && (
                  <dd className="text-[11px] text-muted-foreground">
                    {format.relativeTime(new Date(data.last_quiz.finished_at))}
                  </dd>
                )}
              </div>
            </dl>
          </section>

          <section className="rise-in rise-in-delay-1 flex flex-col gap-2">
            <Button
              size="xl"
              className="w-full"
              onClick={explain}
              disabled={busy}
            >
              <Lightbulb /> {t("explain")}
            </Button>
            <Button
              size="xl"
              variant="lime"
              className="w-full"
              onClick={quiz}
              disabled={busy}
            >
              <BookOpenCheck /> {t("quiz")}
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="w-full bg-white"
              render={<Link href={`/ask?mode=exam_prep&topic=${data.id}`} />}
            >
              <GraduationCap /> {t("exam")}
            </Button>
            {quizNotice && (
              <p className="rounded-2xl bg-peach px-4 py-3 text-sm font-semibold text-[#8a4b00]">
                {quizNotice}
              </p>
            )}
          </section>

          <section className="rise-in rise-in-delay-2">
            <h2 className="mb-3 font-heading text-lg font-extrabold">
              {t("recent")}
            </h2>
            {data.recent_sessions.length === 0 ? (
              <p className="rounded-3xl border border-dashed border-line px-4 py-6 text-center text-sm text-muted-foreground">
                {t("noActivity")}
              </p>
            ) : (
              <ul className="flex flex-col gap-3">
                {data.recent_sessions.map((session) => (
                  <li key={session.id}>
                    <SessionCard session={session} />
                  </li>
                ))}
              </ul>
            )}
          </section>

          <Button
            variant="ghost"
            className="self-center"
            render={<Link href={backHref} />}
          >
            <Map /> {t("toMap")}
          </Button>
        </>
      )}
    </div>
  );
}
