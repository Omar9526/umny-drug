"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import Link from "next/link";
import { Check, ShieldCheck, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/feedback/States";
import { FullScreenLoader } from "@/components/feedback/FullScreenLoader";
import { PageHeader } from "@/components/layout/PageHeader";
import { useSubjects, useTopic } from "@/features/curriculum/api";
import { useDashboard } from "@/features/dashboard/api";
import {
  useCreateSession,
  type CreateSessionInput,
} from "@/features/tutor/api";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const MODES = [
  "question",
  "explain_topic",
  "check_answer",
  "exam_prep",
] as const;
type Mode = (typeof MODES)[number];

function AskScreen() {
  const t = useTranslations("ask");
  const router = useRouter();
  const search = useSearchParams();
  const modeParam = search.get("mode");
  const mode: Mode = (MODES as readonly string[]).includes(modeParam ?? "")
    ? (modeParam as Mode)
    : "question";
  const topicParam = Number(search.get("topic"));
  const topicId =
    Number.isFinite(topicParam) && topicParam > 0 ? topicParam : null;

  const subjects = useSubjects();
  const topic = useTopic(topicId);
  const create = useCreateSession();
  const [subjectSlug, setSubjectSlug] = useState<string | null>(null);
  const [question, setQuestion] = useState("");

  const dashboard = useDashboard();
  const freeQuestionsAllowed =
    dashboard.data?.student.allow_free_questions ?? true;

  const effectiveSubject = topic.data?.subject.slug ?? subjectSlug;
  const requiresText = mode === "question" || mode === "check_answer";
  // with free questions switched off by the parent, topic-based modes need a concrete topic
  const topicRequired = !freeQuestionsAllowed && !requiresText && !topicId;
  const canStart = requiresText
    ? question.trim().length >= 3
    : topicRequired
      ? false
      : Boolean(effectiveSubject || topicId);

  async function start() {
    const body: CreateSessionInput = {
      mode,
      subject_slug: effectiveSubject,
      topic_id: topicId,
      question: question.trim(),
    };
    try {
      const session = await create.mutateAsync(body);
      const params = question.trim()
        ? `?start=${encodeURIComponent(question.trim())}`
        : "";
      router.replace(`/sessions/${session.id}${params}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  if (requiresText && !freeQuestionsAllowed) {
    return (
      <div className="flex flex-col gap-4">
        <PageHeader title={t(`${mode}.title`)} backHref="/home" />
        <EmptyState
          icon={<ShieldCheck />}
          text={t("disabledByParent")}
          action={
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button render={<Link href="/assignments/new?source=text" />}>
                {t("goHomework")}
              </Button>
              <Button
                variant="soft"
                render={<Link href="/ask?mode=explain_topic" />}
              >
                {t("goExplain")}
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t(`${mode}.title`)} backHref="/home" />
      <p className="text-base text-muted-foreground">{t(`${mode}.hint`)}</p>

      {topicId && (
        <section className="rounded-3xl bg-lime p-4">
          <p className="text-xs font-bold tracking-wide text-teal uppercase">
            {t("topicChosen")}
          </p>
          {topic.isPending && (
            <CardSkeleton lines={1} className="mt-2 bg-white/70" />
          )}
          {topic.isError && (
            <ErrorState error={topic.error} onRetry={() => topic.refetch()} />
          )}
          {topic.data && (
            <div className="mt-1 flex items-center gap-3">
              <SubjectIcon
                icon={topic.data.subject.icon}
                color="ivory"
                size="sm"
              />
              <div>
                <p className="text-lg font-extrabold">{topic.data.name}</p>
                <p className="text-sm text-ink/70">
                  {topic.data.subject.name} · {topic.data.section.name}
                </p>
              </div>
            </div>
          )}
        </section>
      )}

      {topicRequired && (
        <section className="rounded-3xl bg-peach px-4 py-3 text-sm font-semibold text-[#8a4b00]">
          {t("topicRequired")}{" "}
          <Link href="/subjects" className="font-bold text-teal underline">
            {t("pickTopic")}
          </Link>
        </section>
      )}

      {!topicId && (
        <section>
          <h2 className="mb-2 text-base font-bold">{t("subject")}</h2>
          {subjects.isPending && <CardSkeleton lines={1} />}
          {subjects.isError && (
            <ErrorState
              error={subjects.error}
              onRetry={() => subjects.refetch()}
            />
          )}
          {subjects.data && (
            <ul className="flex flex-wrap gap-2">
              <li>
                <button
                  type="button"
                  aria-pressed={subjectSlug === null}
                  onClick={() => setSubjectSlug(null)}
                  className={cn(
                    "tap-target rounded-full px-4 text-sm font-semibold ring-1 transition-colors",
                    subjectSlug === null
                      ? "bg-teal text-white ring-teal"
                      : "bg-white ring-line hover:bg-muted",
                  )}
                >
                  {t("anySubject")}
                </button>
              </li>
              {subjects.data.map((subject) => {
                const selected = subject.slug === subjectSlug;
                return (
                  <li key={subject.id}>
                    <button
                      type="button"
                      aria-pressed={selected}
                      onClick={() =>
                        setSubjectSlug(selected ? null : subject.slug)
                      }
                      className={cn(
                        "tap-target flex items-center gap-2 rounded-full py-1.5 pr-4 pl-1.5 text-sm font-semibold ring-1 transition-colors",
                        selected
                          ? "bg-teal text-white ring-teal"
                          : "bg-white ring-line hover:bg-muted",
                      )}
                    >
                      <SubjectIcon
                        icon={subject.icon}
                        color={selected ? "lime" : subject.color}
                        size="sm"
                        className="size-8 rounded-full [&_svg]:size-4"
                      />
                      {subject.name}
                      {selected && <Check className="size-4" />}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      )}

      <textarea
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        rows={5}
        autoFocus={requiresText}
        placeholder={t(`${mode}.placeholder`)}
        className="w-full resize-y rounded-3xl border border-line bg-white px-4 py-3 text-base outline-none focus-visible:ring-4 focus-visible:ring-teal/20"
      />

      <Button
        size="xl"
        className="w-full"
        onClick={start}
        disabled={!canStart || create.isPending}
      >
        <Sparkles /> {t("start")}
      </Button>
    </div>
  );
}

export default function AskPage() {
  return (
    <Suspense fallback={<FullScreenLoader />}>
      <AskScreen />
    </Suspense>
  );
}
