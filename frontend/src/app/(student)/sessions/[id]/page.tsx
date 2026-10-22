"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { ChevronDown, ChevronUp, Flag, SendHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { AnswerPanel } from "@/components/tutor/AnswerPanel";
import { ChatMessage, StreamingBubble } from "@/components/tutor/ChatMessage";
import { QuickCommands } from "@/components/tutor/QuickCommands";
import { ResultCard } from "@/components/tutor/ResultCard";
import { useImageObjectUrl } from "@/features/assignments/api";
import { streamTurn, tutorApi, useInvalidateSessionLists, useSession } from "@/features/tutor/api";
import { getErrorMessage } from "@/lib/api/client";
import type { AIMessage, AnswerKind, QuickCommand, SessionDetail, SessionState } from "@/lib/api/types";

function TaskCard({ text, label, imageId }: { text: string; label: string; imageId?: string }) {
  const t = useTranslations("tutor");
  const [open, setOpen] = useState(true);
  const url = useImageObjectUrl(imageId);
  return (
    <section className="rounded-3xl bg-white shadow-card ring-1 ring-line">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="text-sm font-bold text-teal">
          {t("assignment")} {label && <span className="text-muted-foreground">· {label}</span>}
        </span>
        {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
      </button>
      {open && (
        <div className="flex gap-3 px-4 pb-4">
          {url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={url} alt="" className="size-20 shrink-0 rounded-2xl object-cover ring-1 ring-line" />
          )}
          <p className="text-base leading-snug whitespace-pre-wrap">{text}</p>
        </div>
      )}
    </section>
  );
}

function localMessage(command: string, content: string): AIMessage {
  return {
    id: `local-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    role: "user",
    command,
    content,
    payload: {},
    flagged: false,
    created_at: new Date().toISOString(),
  };
}

export default function SessionPage({ params }: PageProps<"/sessions/[id]">) {
  const { id } = use(params);
  const t = useTranslations("tutor");
  const search = useSearchParams();
  const queryClient = useQueryClient();
  const invalidateLists = useInvalidateSessionLists();
  const session = useSession(id);

  // The TanStack cache is the single source of truth; streaming text is the only local copy.
  const patch = useCallback(
    (updater: (prev: SessionDetail) => SessionDetail) =>
      queryClient.setQueryData<SessionDetail>(["session", id], (prev) => (prev ? updater(prev) : prev)),
    [queryClient, id],
  );

  const [streamText, setStreamText] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState<{ message: string; retryable?: boolean } | null>(null);
  const [lastTurn, setLastTurn] = useState<{ command: QuickCommand; content: string } | null>(null);
  const [answerOpen, setAnswerOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const [draft, setDraft] = useState("");
  const startedRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const data = session.data;
  const messages = useMemo(() => data?.messages ?? [], [data?.messages]);
  const state: SessionState | null = data?.state ?? null;
  const lastAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant" && m.command !== "check"),
    [messages],
  );
  const checkQuestion = lastAssistant?.payload?.check_question ?? "";
  const answerKind: AnswerKind = lastAssistant?.payload?.answer_kind ?? data?.answer_kind ?? "none";
  const suggested = lastAssistant?.payload?.suggested_commands ?? data?.suggested_commands ?? [];
  const active = state?.status === "active";

  const sendTurn = useCallback(
    async (command: QuickCommand, content = "", options: { retry?: boolean; silent?: boolean } = {}) => {
      setStreamError(null);
      setLastTurn({ command, content });
      // A refetch landing mid-stream must not overwrite the optimistic cache.
      await queryClient.cancelQueries({ queryKey: ["session", id] });
      const showsUserBubble = content || (command !== "start" && command !== "" && command !== "next_step");
      if (showsUserBubble && !options.retry && !options.silent) {
        const label = content || t(`commands.${command as "hint"}`);
        patch((prev) => ({ ...prev, messages: [...prev.messages, localMessage(command, label)] }));
      }
      setStreaming(true);
      setStreamText("");
      const controller = new AbortController();
      abortRef.current = controller;
      await streamTurn(
        id,
        { command, content },
        {
          onDelta: (text) => setStreamText((prev) => (prev ?? "") + text),
          onReset: () => setStreamText(""),
          onFinal: ({ message, session: nextState }) => {
            patch((prev) => ({ ...prev, messages: [...prev.messages, message], state: nextState, status: nextState.status }));
            setStreamText(null);
          },
          onError: (error) => {
            setStreamError(error);
            setStreamText(null);
          },
        },
        controller.signal,
      );
      setStreaming(false);
      invalidateLists();
    },
    [id, t, patch, invalidateLists, queryClient],
  );

  // The first explanation starts by itself; ?start= carries the question typed on the «Ask» screen.
  // Scheduled through a timer so the effect body stays free of synchronous state updates.
  useEffect(() => {
    if (!data || data.messages.length > 0 || data.status !== "active") return;
    const timer = setTimeout(() => {
      if (startedRef.current) return;
      startedRef.current = true;
      void sendTurn("start", search.get("start") ?? "");
    }, 0);
    return () => clearTimeout(timer);
  }, [data, sendTurn, search]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, streamText, answerOpen, state?.status]);

  async function submitAnswer(answer: string) {
    setChecking(true);
    try {
      const result = await tutorApi.checkAnswer(id, answer);
      await queryClient.cancelQueries({ queryKey: ["session", id] });
      patch((prev) => ({
        ...prev,
        messages: [...prev.messages, localMessage("check", answer), result.message],
        state: result.session,
        status: result.session.status,
        attempts: [...prev.attempts, result.attempt],
      }));
      setAnswerOpen(false);
      invalidateLists();
      if (result.continue_with === "next_step") {
        setChecking(false);
        void sendTurn("next_step", "", { silent: true });
        return;
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setChecking(false);
    }
  }

  async function finish() {
    try {
      const next = await tutorApi.complete(id);
      patch((prev) => ({ ...prev, state: next, status: next.status }));
      invalidateLists();
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function flag(messageId: string) {
    try {
      await tutorApi.flag(id, messageId);
      patch((prev) => ({
        ...prev,
        messages: prev.messages.map((m) => (m.id === messageId ? { ...m, flagged: true } : m)),
      }));
      toast.success(t("flagged"));
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  if (session.isPending) {
    return (
      <div className="flex flex-col gap-3">
        <CardSkeleton />
        <CardSkeleton lines={4} />
      </div>
    );
  }
  if (session.isError || !data) {
    return <ErrorState error={session.error} onRetry={() => session.refetch()} />;
  }

  return (
    <div className="flex min-h-[calc(100dvh-8rem)] flex-col gap-4">
      <PageHeader
        title={data.title || data.mode_label}
        subtitle={data.subject && data.subject.name !== data.title ? data.subject.name : data.mode_label}
        backHref="/home"
        action={data.subject && <SubjectIcon icon={data.subject.icon} color={data.subject.color} size="sm" />}
      />

      {data.demo_mode && (
        <p className="rounded-2xl bg-warning/10 px-4 py-2 text-sm font-medium text-warning ring-1 ring-warning/30">
          {t("demoNotice")}
        </p>
      )}

      {data.assignment && (
        <TaskCard text={data.assignment.text} label={data.assignment.label} imageId={data.assignment.images[0]?.id} />
      )}

      <div className="flex flex-1 flex-col gap-3">
        {messages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            canAnswer={active && !streaming && message.id === lastAssistant?.id}
            onAnswer={() => setAnswerOpen(true)}
            onFlag={message.role === "assistant" && !message.id.startsWith("local") ? flag : undefined}
          />
        ))}
        {streamText !== null && <StreamingBubble text={streamText} />}
        {streamError && (
          <div role="alert" className="rounded-3xl bg-destructive/5 p-4 ring-1 ring-destructive/20">
            <p className="text-sm font-bold text-destructive">{t("errorTitle")}</p>
            <p className="text-sm">{streamError.message}</p>
            {lastTurn && (
              <Button size="sm" variant="outline" className="mt-2" onClick={() => sendTurn(lastTurn.command, lastTurn.content, { retry: true })}>
                {t("retryTurn")}
              </Button>
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {state && !active && <ResultCard state={state} siblings={data.siblings} topicId={data.topic_id} />}

      {active && (
        <div className="sticky bottom-20 z-10 flex flex-col gap-3 bg-ivory/95 pt-2 pb-1 backdrop-blur md:bottom-0">
          {answerOpen ? (
            <AnswerPanel
              question={checkQuestion}
              kind={answerKind}
              busy={checking}
              onSubmit={submitAnswer}
              onCancel={() => setAnswerOpen(false)}
            />
          ) : (
            <>
              <QuickCommands
                suggested={suggested}
                disabled={streaming || checking}
                onCommand={(command) => void sendTurn(command)}
                onCheck={() => setAnswerOpen(true)}
              />
              <form
                className="flex items-end gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  const text = draft.trim();
                  if (!text || streaming) return;
                  setDraft("");
                  void sendTurn("", text);
                }}
              >
                <textarea
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  rows={1}
                  placeholder={t("askPlaceholder")}
                  disabled={streaming}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      e.currentTarget.form?.requestSubmit();
                    }
                  }}
                  className="max-h-32 min-h-12 flex-1 resize-none rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none focus-visible:ring-4 focus-visible:ring-teal/20 disabled:opacity-60"
                />
                <Button type="submit" size="icon" aria-label={t("send")} disabled={streaming || !draft.trim()}>
                  <SendHorizontal />
                </Button>
              </form>
              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={finish}
                  disabled={streaming || checking}
                  className="text-sm font-semibold text-muted-foreground underline-offset-4 hover:underline disabled:opacity-50"
                >
                  {t("finish")}
                </button>
                <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                  <Flag className="size-3" /> {t("hintsUsed", { count: state?.hints_used ?? 0 })}
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
