"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import type { AnswerKind } from "@/lib/api/types";

export function AnswerPanel({
  question,
  kind,
  busy,
  onSubmit,
  onCancel,
}: {
  question: string;
  kind: AnswerKind;
  busy: boolean;
  onSubmit: (answer: string) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useTranslations("tutor");
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);
  const numeric = kind === "number";

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim() || busy) return;
    await onSubmit(value.trim());
    setValue("");
  };

  return (
    <form onSubmit={submit} className="rise-in rounded-3xl bg-lime p-4 shadow-card">
      <p className="text-xs font-bold tracking-wide text-teal uppercase">{t("answerTitle")}</p>
      {question && <p className="mt-1 text-base font-semibold text-ink">{question}</p>}
      <div className="mt-3 flex gap-2">
        {numeric || kind === "expression" ? (
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            inputMode={numeric ? "decimal" : "text"}
            autoComplete="off"
            placeholder={t("answerPlaceholder")}
            className="h-14 min-w-0 flex-1 rounded-2xl border border-line bg-white px-4 font-heading text-2xl font-bold outline-none focus-visible:ring-4 focus-visible:ring-teal/20"
          />
        ) : (
          <textarea
            ref={inputRef as React.RefObject<HTMLTextAreaElement>}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            rows={3}
            placeholder={t("answerPlaceholder")}
            className="min-w-0 flex-1 resize-none rounded-2xl border border-line bg-white px-4 py-3 text-base outline-none focus-visible:ring-4 focus-visible:ring-teal/20"
          />
        )}
      </div>
      <div className="mt-3 flex gap-2">
        <Button type="submit" size="lg" className="flex-1" disabled={busy || !value.trim()}>
          {t("answerCheck")}
        </Button>
        <Button type="button" variant="ghost" size="lg" onClick={onCancel} disabled={busy}>
          {t("answerCancel")}
        </Button>
      </div>
    </form>
  );
}
