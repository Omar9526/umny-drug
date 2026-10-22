"use client";

import { useTranslations } from "next-intl";
import { CircleHelp, Lightbulb, ListChecks, MessageCircleQuestion, RefreshCw, Shuffle, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { QuickCommand } from "@/lib/api/types";

type Item = { key: Exclude<QuickCommand, "" | "start" | "next_step"> | "check"; icon: React.ComponentType<{ className?: string }> };

const ITEMS: Item[] = [
  { key: "hint", icon: Lightbulb },
  { key: "check", icon: ListChecks },
  { key: "simpler", icon: Sparkles },
  { key: "example", icon: Shuffle },
  { key: "why", icon: CircleHelp },
  { key: "dont_understand", icon: MessageCircleQuestion },
  { key: "repeat", icon: RefreshCw },
];

export function QuickCommands({
  suggested,
  disabled,
  onCommand,
  onCheck,
}: {
  suggested: string[];
  disabled: boolean;
  onCommand: (command: QuickCommand) => void;
  onCheck: () => void;
}) {
  const t = useTranslations("tutor.commands");
  const ordered = [...ITEMS].sort((a, b) => Number(suggested.includes(b.key)) - Number(suggested.includes(a.key)));
  return (
    <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1" role="toolbar" aria-label={t("hint")}>
      {ordered.map(({ key, icon: Icon }) => {
        const highlighted = suggested.includes(key) || key === "check";
        return (
          <button
            key={key}
            type="button"
            disabled={disabled}
            onClick={() => (key === "check" ? onCheck() : onCommand(key))}
            className={cn(
              "tap-target inline-flex shrink-0 items-center gap-1.5 rounded-full px-4 text-sm font-semibold transition-colors disabled:opacity-50",
              key === "check"
                ? "bg-teal text-white"
                : highlighted
                  ? "bg-lime text-ink"
                  : "bg-white text-foreground ring-1 ring-line hover:bg-muted",
            )}
          >
            <Icon className="size-4" />
            {t(key)}
          </button>
        );
      })}
    </div>
  );
}
