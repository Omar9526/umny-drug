"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, CircleHelp, Flag } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Markdown } from "@/components/tutor/Markdown";
import { cn } from "@/lib/utils";
import type { AIMessage, Verdict } from "@/lib/api/types";

const VERDICT_STYLE: Record<Verdict, string> = {
  correct: "bg-success/10 text-success ring-success/30",
  partial: "bg-warning/10 text-warning ring-warning/30",
  incorrect: "bg-destructive/10 text-destructive ring-destructive/30",
  uncertain: "bg-muted text-muted-foreground ring-line",
};

export function ChatMessage({
  message,
  onAnswer,
  onFlag,
  canAnswer,
}: {
  message: AIMessage;
  onAnswer?: () => void;
  onFlag?: (id: string) => Promise<void> | void;
  canAnswer?: boolean;
}) {
  const t = useTranslations("tutor");
  const tc = useTranslations("tutor.commands");
  const [flagging, setFlagging] = useState(false);
  const isUser = message.role === "user";
  const verdict = message.payload?.verdict;
  // Quick commands are stored as tokens («hint»); show the button label the child actually tapped.
  const isCommand =
    isUser && !["ask", "check", "start", ""].includes(message.command);
  const commandLabel =
    isCommand &&
    (!message.content || message.content === message.command) &&
    tc.has(message.command)
      ? tc(message.command)
      : null;

  if (isUser) {
    return (
      <div className="rise-in flex justify-end">
        <div className="max-w-[85%] rounded-3xl rounded-tr-md bg-teal px-4 py-3 text-base text-white shadow-card">
          {message.command === "check" && (
            <span className="mb-1 block text-xs font-semibold text-white/70">
              {t("answerTitle")}
            </span>
          )}
          <p className="whitespace-pre-wrap">
            {commandLabel ?? message.content}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rise-in flex items-end gap-2">
      <LogoMark size={28} className="mb-1 shrink-0" />
      <div className="min-w-0 max-w-[90%] flex-1">
        <div
          className={cn(
            "rounded-3xl rounded-bl-md bg-white px-4 py-3 shadow-card ring-1 ring-line",
            verdict && "ring-2",
            verdict && VERDICT_STYLE[verdict].split(" ").pop(),
          )}
        >
          {verdict && (
            <span
              className={cn(
                "mb-2 inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold ring-1",
                VERDICT_STYLE[verdict],
              )}
            >
              {verdict === "correct" ? (
                <Check className="size-3.5" />
              ) : (
                <CircleHelp className="size-3.5" />
              )}
              {t(`verdict.${verdict}`)}
              {message.payload?.method && (
                <span className="font-medium opacity-70">
                  · {t(`method.${message.payload.method}`)}
                </span>
              )}
            </span>
          )}
          <Markdown>{message.content}</Markdown>
          {message.payload?.check_question && (
            <div className="mt-3 rounded-2xl bg-lime/60 px-3 py-2">
              <p className="text-xs font-bold tracking-wide text-teal uppercase">
                {t("checkQuestion")}
              </p>
              <p className="text-base font-semibold">
                {message.payload.check_question}
              </p>
              {canAnswer && onAnswer && (
                <button
                  type="button"
                  onClick={onAnswer}
                  className="tap-target mt-2 rounded-full bg-teal px-4 py-1.5 text-sm font-bold text-white"
                >
                  {t("answerCheck")}
                </button>
              )}
            </div>
          )}
          {message.payload?.uncertainty_note &&
            !message.payload.uncertainty_note.startsWith("Демо") && (
              <p className="mt-2 text-xs text-muted-foreground">
                ⚠︎ {message.payload.uncertainty_note}
              </p>
            )}
        </div>
        {onFlag && (
          <button
            type="button"
            disabled={message.flagged || flagging}
            onClick={async () => {
              setFlagging(true);
              try {
                await onFlag(message.id);
              } finally {
                setFlagging(false);
              }
            }}
            className="mt-1 ml-2 inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-teal disabled:opacity-60"
          >
            <Flag className="size-3" />{" "}
            {message.flagged ? t("flagSent") : t("flag")}
          </button>
        )}
      </div>
    </div>
  );
}

export function StreamingBubble({ text }: { text: string }) {
  const t = useTranslations("tutor");
  return (
    <div className="flex items-end gap-2">
      <LogoMark size={28} className="mb-1 shrink-0" />
      <div className="min-w-0 max-w-[90%] rounded-3xl rounded-bl-md bg-white px-4 py-3 shadow-card ring-1 ring-line">
        {text ? (
          <Markdown>{text}</Markdown>
        ) : (
          <p className="text-sm text-muted-foreground">{t("thinking")}</p>
        )}
        <span className="mt-1 inline-flex gap-1" aria-hidden>
          <span className="size-1.5 animate-bounce rounded-full bg-teal [animation-delay:-0.3s]" />
          <span className="size-1.5 animate-bounce rounded-full bg-teal [animation-delay:-0.15s]" />
          <span className="size-1.5 animate-bounce rounded-full bg-teal" />
        </span>
      </div>
    </div>
  );
}
