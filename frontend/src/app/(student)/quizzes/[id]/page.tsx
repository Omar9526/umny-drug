"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import {
  ArrowRight,
  Check,
  CircleHelp,
  Lightbulb,
  Map,
  RotateCcw,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { Confetti } from "@/components/feedback/Confetti";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { Contours } from "@/components/layout/Hero";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  QuizLegend,
  QuizProgressGrid,
} from "@/components/learning/QuizProgressGrid";
import { useDashboard } from "@/features/dashboard/api";
import {
  useAnswerQuestion,
  useFinishQuiz,
  useQuizAttempt,
  useStartQuiz,
} from "@/features/learning/api";
import { useCreateSession } from "@/features/tutor/api";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { QuizAttempt, QuizQuestion, QuizResult } from "@/lib/api/types";

/** «Разбор:» — the explanation as steps (one per line) and the verdict line, like the reference. */
function Explanation({ result }: { result: QuizResult }) {
  const t = useTranslations("quiz");
  const lines = result.explanation
    .split(/\n+/)
    .map((s) => s.trim())
    .filter(Boolean);
  return (
    <div className="rise-in mt-4 px-1">
      <p className="text-base font-extrabold">{t("explanation")}</p>
      {lines.length > 0 && (
        <ol className="mt-2 flex flex-col gap-1.5">
          {lines.map((line, i) => (
            <li key={i} className="flex gap-3 text-[15px] leading-snug">
              {lines.length > 1 && (
                <span className="w-14 shrink-0 text-sm font-semibold text-muted-foreground">
                  {t("step", { n: i + 1 })}
                </span>
              )}
              <span className="font-medium">{line}</span>
            </li>
          ))}
        </ol>
      )}
      <p
        className={cn(
          "mt-3 flex items-center gap-2 text-base font-bold",
          result.correct ? "text-teal" : "text-warning",
        )}
      >
        {result.correct ? (
          <span className="pop-in flex size-6 shrink-0 items-center justify-center rounded-full bg-teal text-white">
            <Check className="size-3.5" strokeWidth={3} />
          </span>
        ) : (
          <CircleHelp className="size-5 shrink-0" />
        )}
        {result.correct
          ? t("yourAnswerCorrect")
          : t("correctAnswer", { answer: result.correct_answer })}
      </p>
    </div>
  );
}

function QuestionCard({
  attempt,
  question,
  index,
  onAdvance,
}: {
  attempt: QuizAttempt;
  question: QuizQuestion;
  index: number;
  onAdvance: () => void;
}) {
  const t = useTranslations("quiz");
  const answer = useAnswerQuestion(attempt.id);
  const [draft, setDraft] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [showHint, setShowHint] = useState(false);
  const result: QuizResult | undefined = attempt.results[String(question.id)];
  const isChoice = question.type === "single" || question.type === "multiple";
  const given = attempt.answers[String(question.id)];
  const isLast = index + 1 >= attempt.total_count;
  const canSubmit = isChoice ? selected.length > 0 : draft.trim().length > 0;

  async function submit() {
    if (!canSubmit || result || answer.isPending) return;
    const value = isChoice
      ? question.type === "single"
        ? selected[0]
        : selected
      : draft.trim();
    try {
      await answer.mutateAsync({ questionId: question.id, answer: value });
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <section className="rise-in">
      <div className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <p className="text-sm font-semibold text-muted-foreground">
          {t("question", { n: index + 1, total: attempt.total_count })}
        </p>
        <h2 data-question-prompt className="mt-1 font-heading text-[22px] leading-snug font-extrabold text-teal">
          {question.prompt}
        </h2>
        {question.type === "multiple" && !result && (
          <p className="mt-1 text-sm text-muted-foreground">
            {t("multipleHint")}
          </p>
        )}

        {isChoice ? (
          <ul className="mt-4 flex flex-col gap-2.5">
            {question.options.map((option) => {
              const picked = result
                ? Array.isArray(given)
                  ? given.includes(option.key)
                  : given === option.key
                : selected.includes(option.key);
              const isCorrectOption =
                result &&
                result.correct_answer.split(", ").includes(option.text);
              return (
                <li key={option.key}>
                  <button
                    type="button"
                    disabled={Boolean(result) || answer.isPending}
                    aria-pressed={picked}
                    onClick={() =>
                      setSelected((prev) =>
                        question.type === "single"
                          ? [option.key]
                          : prev.includes(option.key)
                            ? prev.filter((k) => k !== option.key)
                            : [...prev, option.key],
                      )
                    }
                    className={cn(
                      "relative flex min-h-14 w-full items-center justify-center rounded-full px-12 py-3 text-center text-lg font-bold transition-[background-color,transform,box-shadow] active:scale-[0.99]",
                      !result &&
                        (picked
                          ? "bg-lime text-ink ring-2 ring-lime-deep"
                          : "bg-white text-ink ring-1 ring-teal/25 hover:bg-lime-pale"),
                      result &&
                        isCorrectOption &&
                        "bg-lime text-ink ring-2 ring-lime-deep",
                      result &&
                        picked &&
                        !isCorrectOption &&
                        "bg-peach text-[#8a4b00] ring-1 ring-warning/40",
                      result &&
                        !picked &&
                        !isCorrectOption &&
                        "bg-white text-muted-foreground ring-1 ring-line",
                    )}
                  >
                    <span className="absolute left-5 text-xs font-bold text-ink/35 uppercase">
                      {option.key}
                    </span>
                    <span data-option-text>{option.text}</span>
                    {result && isCorrectOption && (
                      <Check
                        className="absolute right-5 size-5 text-teal"
                        strokeWidth={3}
                      />
                    )}
                    {result && picked && !isCorrectOption && (
                      <X className="absolute right-5 size-5" />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <form
            className="mt-4"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <input
              value={result ? String(given ?? "") : draft}
              onChange={(e) => setDraft(e.target.value)}
              disabled={Boolean(result) || answer.isPending}
              inputMode={question.type === "numeric" ? "decimal" : "text"}
              autoComplete="off"
              placeholder={t(
                question.type === "numeric"
                  ? "placeholderNumber"
                  : "placeholderText",
              )}
              aria-label={t("yourAnswer")}
              className={cn(
                "h-14 w-full rounded-full px-5 text-center font-heading text-xl font-extrabold outline-none transition placeholder:font-sans placeholder:text-base placeholder:font-medium placeholder:text-muted-foreground focus:ring-2 focus:ring-teal/40 disabled:opacity-100",
                result
                  ? result.correct
                    ? "bg-lime text-ink ring-2 ring-lime-deep"
                    : "bg-peach text-[#8a4b00] ring-1 ring-warning/40"
                  : "bg-white ring-1 ring-teal/25",
              )}
            />
          </form>
        )}

        {!result && question.hint && (
          <div className="mt-4">
            {showHint ? (
              <p className="rise-in rounded-2xl bg-lime-pale px-4 py-3 text-sm">
                <Lightbulb className="mr-1 inline size-4 text-teal" />{" "}
                {question.hint}
              </p>
            ) : (
              <button
                type="button"
                onClick={() => setShowHint(true)}
                className="inline-flex items-center gap-1.5 text-sm font-bold text-teal hover:underline"
              >
                <Lightbulb className="size-4" /> {t("hint")}
              </button>
            )}
          </div>
        )}
      </div>

      {result && <Explanation result={result} />}

      <div className="mt-4 flex gap-3">
        {result ? (
          <Button size="xl" className="w-full" onClick={onAdvance}>
            {isLast ? t("finish") : t("next")} <ArrowRight />
          </Button>
        ) : (
          <>
            <Button
              variant="outline"
              size="xl"
              className="flex-1 bg-white"
              onClick={onAdvance}
              disabled={answer.isPending}
            >
              {isLast ? t("finish") : t("skip")}
            </Button>
            <Button
              size="xl"
              className="flex-[1.4]"
              onClick={() => void submit()}
              disabled={!canSubmit || answer.isPending}
            >
              {t("answer")}
            </Button>
          </>
        )}
      </div>
    </section>
  );
}

function ResultScreen({ attempt }: { attempt: QuizAttempt }) {
  const t = useTranslations("quiz");
  const ts = useTranslations("subjects");
  const router = useRouter();
  const startQuiz = useStartQuiz();
  const createSession = useCreateSession();
  const dashboard = useDashboard();
  const score = attempt.total_count
    ? attempt.correct_count / attempt.total_count
    : 0;
  const tone = score >= 0.8 ? "great" : score >= 0.5 ? "ok" : "review";
  const student = dashboard.data?.student;

  async function again() {
    try {
      const next = await startQuiz.mutateAsync(attempt.topic.id);
      router.replace(`/quizzes/${next.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function explain() {
    try {
      const session = await createSession.mutateAsync({
        mode: "explain_topic",
        subject_slug: attempt.topic.subject.slug,
        topic_id: attempt.topic.id,
        question: "",
      });
      router.push(`/sessions/${session.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <>
      <section className="rise-in relative overflow-hidden rounded-[32px] bg-lime p-6 text-center shadow-card">
        <Contours className="-top-16 -right-20 h-80 w-80" />
        {tone === "great" && <Confetti />}
        <div className="relative flex flex-col items-center">
          {student && (
            <ChildAvatar
              avatar={student.avatar}
              size="xl"
              className={cn(
                "pop-in ring-4 ring-white shadow-tile",
                tone === "great" && "wiggle",
              )}
            />
          )}
          <p className="mt-4 text-xs font-bold tracking-wide text-ink/60 uppercase">
            {t("resultTitle")}
          </p>
          {student && tone !== "review" && (
            <p className="font-heading text-2xl font-extrabold text-teal">
              {t("well", { name: student.nickname })}
            </p>
          )}
          <p
            className="pop-in mt-1 font-heading text-[64px] leading-none font-extrabold text-teal"
            style={{ animationDelay: "150ms" }}
          >
            {attempt.correct_count}
            <span className="text-2xl text-ink/50"> / {attempt.total_count}</span>
          </p>
          <p className="mt-3 max-w-xs text-base text-ink/80">
            {t(`result.${tone}`)}
          </p>
          {attempt.progress_status && (
            <span className="mt-3 rounded-full bg-white/80 px-3 py-1.5 text-xs font-bold text-teal">
              {t("statusNow", {
                status: ts(`topicStatus.${attempt.progress_status}`),
              })}
            </span>
          )}
        </div>
      </section>

      <section className="rise-in rise-in-delay-1 rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <h3 className="font-heading text-base font-extrabold">
          {t("answersTitle")}
        </h3>
        <QuizProgressGrid attempt={attempt} size="lg" className="mt-3" />
        <QuizLegend items={["correct", "wrong", "open"]} className="mt-4" />
      </section>

      <div className="rise-in rise-in-delay-2 flex flex-col gap-2">
        {tone === "review" ? (
          <Button
            size="xl"
            onClick={explain}
            disabled={createSession.isPending}
          >
            <Lightbulb /> {t("explain")}
          </Button>
        ) : (
          <Button size="xl" onClick={again} disabled={startQuiz.isPending}>
            <RotateCcw /> {t("again")}
          </Button>
        )}
        {tone === "review" ? (
          <Button
            variant="lime"
            size="lg"
            onClick={again}
            disabled={startQuiz.isPending}
          >
            <RotateCcw /> {t("again")}
          </Button>
        ) : (
          <Button
            variant="lime"
            size="lg"
            onClick={explain}
            disabled={createSession.isPending}
          >
            <Lightbulb /> {t("explain")}
          </Button>
        )}
        <Button
          variant="ghost"
          size="lg"
          render={<Link href={`/subjects/${attempt.topic.subject.slug}`} />}
        >
          <Map /> {t("toMap")}
        </Button>
      </div>
    </>
  );
}

function QuizRunner({ attempt }: { attempt: QuizAttempt }) {
  const finish = useFinishQuiz(attempt.id);
  // The index moves only on «Дальше»/«Пропустить» or a tap on a progress tile — never because an
  // answer arrived, otherwise the feedback for the just-answered question would be skipped.
  const [current, setCurrent] = useState(() => {
    const firstOpen = attempt.questions.findIndex(
      (q) => !attempt.results[String(q.id)],
    );
    return firstOpen === -1
      ? Math.max(attempt.questions.length - 1, 0)
      : firstOpen;
  });
  const question = attempt.questions[current];

  async function advance() {
    if (current + 1 < attempt.questions.length) {
      setCurrent(current + 1);
      return;
    }
    try {
      await finish.mutateAsync();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <>
      <QuizProgressGrid
        attempt={attempt}
        current={current}
        onSelect={setCurrent}
      />
      {question && (
        <QuestionCard
          key={question.id}
          attempt={attempt}
          question={question}
          index={current}
          onAdvance={advance}
        />
      )}
    </>
  );
}

export default function QuizPage({ params }: PageProps<"/quizzes/[id]">) {
  const { id } = use(params);
  const t = useTranslations("quiz");
  const attempt = useQuizAttempt(id);

  if (attempt.isPending) {
    return (
      <div>
        <PageHeader title={t("title")} backHref="/subjects" />
        <CardSkeleton lines={4} />
      </div>
    );
  }
  if (attempt.isError) {
    return (
      <div>
        <PageHeader title={t("title")} backHref="/subjects" />
        <ErrorState error={attempt.error} onRetry={() => attempt.refetch()} />
      </div>
    );
  }

  const data = attempt.data;
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("title")}
        subtitle={`${t("questions", { count: data.total_count })} · ${data.topic.name}`}
        backHref={`/topics/${data.topic.id}`}
      />
      {data.status === "finished" ? (
        <ResultScreen attempt={data} />
      ) : (
        <QuizRunner attempt={data} />
      )}
    </div>
  );
}
