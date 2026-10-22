"use client";

import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { roundButtonClass } from "@/components/layout/Hero";
import { cn } from "@/lib/utils";

/**
 * Screen header. With a back button the title sits centred between the round back control and an
 * optional action (the reference layout); without one it is a big left-aligned display title.
 */
export function PageHeader({
  title,
  subtitle,
  back = true,
  backHref,
  action,
  className,
  tone = "default",
}: {
  title: string;
  subtitle?: string;
  back?: boolean;
  backHref?: string;
  action?: React.ReactNode;
  className?: string;
  tone?: "default" | "onLime";
}) {
  const router = useRouter();
  if (!back) {
    return (
      <header className={cn("mb-5 flex items-end justify-between gap-3", className)}>
        <div className="min-w-0 flex-1">
          <h1 className="font-heading text-[28px] leading-tight font-extrabold">{title}</h1>
          {subtitle && <p className="mt-0.5 text-sm font-semibold text-muted-foreground">{subtitle}</p>}
        </div>
        {action}
      </header>
    );
  }
  return (
    <header className={cn("mb-5 flex items-center gap-3", className)}>
      <button
        type="button"
        aria-label="Назад"
        onClick={() => (backHref ? router.push(backHref) : router.back())}
        className={roundButtonClass()}
      >
        <ArrowLeft />
      </button>
      <div className="min-w-0 flex-1 text-center">
        <h1 className="truncate font-heading text-[22px] leading-tight font-extrabold">{title}</h1>
        {subtitle && (
          <p className={cn("truncate text-sm font-semibold", tone === "onLime" ? "text-ink/70" : "text-muted-foreground")}>
            {subtitle}
          </p>
        )}
      </div>
      <div className="flex min-w-11 shrink-0 items-center justify-end gap-2">{action}</div>
    </header>
  );
}
