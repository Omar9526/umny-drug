"use client";

import { useTranslations } from "next-intl";
import { AVATAR_KEYS, ChildAvatar } from "@/components/brand/ChildAvatar";
import { cn } from "@/lib/utils";
import type { AvatarKey, Grade, Language } from "@/lib/api/types";

/** Two big toggles instead of a dropdown — faster for kids and parents alike. */
export function LanguageToggle({
  value,
  onChange,
  name,
  className,
}: {
  value: Language;
  onChange: (lang: Language) => void;
  name: string;
  className?: string;
}) {
  const t = useTranslations("languages");
  return (
    <div role="radiogroup" aria-label={name} className={cn("grid grid-cols-2 gap-2", className)}>
      {(["ru", "ky"] as Language[]).map((lang) => (
        <button
          key={lang}
          type="button"
          role="radio"
          aria-checked={value === lang}
          onClick={() => onChange(lang)}
          className={cn(
            "tap-target h-12 rounded-2xl border text-base font-semibold transition-colors",
            value === lang ? "border-teal bg-teal text-white" : "border-line bg-white text-foreground hover:bg-muted",
          )}
        >
          {t(lang)}
        </button>
      ))}
    </div>
  );
}

export function GradePicker({
  grades,
  value,
  onChange,
  className,
}: {
  grades: Grade[];
  value: number | null;
  onChange: (gradeId: number) => void;
  className?: string;
}) {
  return (
    <div role="radiogroup" className={cn("grid grid-cols-6 gap-2 sm:grid-cols-11", className)}>
      {grades.map((grade) => (
        <button
          key={grade.id}
          type="button"
          role="radio"
          aria-checked={value === grade.id}
          aria-label={grade.name}
          onClick={() => onChange(grade.id)}
          className={cn(
            "tap-target flex h-12 items-center justify-center rounded-2xl border text-lg font-bold transition-colors",
            value === grade.id ? "border-teal bg-lime text-ink" : "border-line bg-white hover:bg-muted",
          )}
        >
          {grade.number}
        </button>
      ))}
    </div>
  );
}

export function AvatarPicker({
  value,
  onChange,
  className,
}: {
  value: AvatarKey;
  onChange: (avatar: AvatarKey) => void;
  className?: string;
}) {
  return (
    <div role="radiogroup" className={cn("grid grid-cols-5 gap-3", className)}>
      {AVATAR_KEYS.map((key) => (
        <button
          key={key}
          type="button"
          role="radio"
          aria-checked={value === key}
          onClick={() => onChange(key)}
          className="flex items-center justify-center rounded-full outline-none focus-visible:ring-4 focus-visible:ring-ring/30"
        >
          <ChildAvatar avatar={key} size="lg" selected={value === key} />
        </button>
      ))}
    </div>
  );
}

export function PinInput({
  value,
  onChange,
  id,
  invalid,
  describedBy,
  autoFocus,
}: {
  value: string;
  onChange: (pin: string) => void;
  id?: string;
  invalid?: boolean;
  describedBy?: string;
  autoFocus?: boolean;
}) {
  return (
    <input
      id={id}
      inputMode="numeric"
      autoComplete="one-time-code"
      pattern="[0-9]*"
      maxLength={6}
      autoFocus={autoFocus}
      aria-invalid={invalid}
      aria-describedby={describedBy}
      value={value}
      onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
      className={cn(
        "h-16 w-full rounded-2xl border border-input bg-white text-center font-heading text-3xl font-extrabold tracking-[0.5em] outline-none focus-visible:border-ring focus-visible:ring-4 focus-visible:ring-ring/20",
        invalid && "border-destructive ring-4 ring-destructive/15",
      )}
    />
  );
}
