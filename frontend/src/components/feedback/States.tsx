"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { getErrorMessage } from "@/lib/api/client";

export function EmptyState({
  icon,
  title,
  text,
  action,
  className,
}: {
  icon?: React.ReactNode;
  title?: string;
  text: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-3 rounded-3xl border border-dashed border-line bg-white/60 px-6 py-8 text-center",
        className,
      )}
    >
      {icon && <div className="text-teal [&_svg]:size-10">{icon}</div>}
      {title && <h3 className="text-lg font-bold">{title}</h3>}
      <p className="max-w-sm text-base text-muted-foreground">{text}</p>
      {action}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const t = useTranslations("app");
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 rounded-3xl bg-destructive/5 px-6 py-8 text-center ring-1 ring-destructive/20",
        className,
      )}
    >
      <h3 className="text-lg font-bold text-destructive">{t("errorTitle")}</h3>
      <p className="max-w-sm text-base text-foreground/80">{getErrorMessage(error, t("errorGeneric"))}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          {t("retry")}
        </Button>
      )}
    </div>
  );
}

export function CardSkeleton({ className, lines = 2 }: { className?: string; lines?: number }) {
  return (
    <div className={cn("rounded-3xl bg-white p-5 shadow-card", className)} aria-hidden="true">
      <Skeleton className="mb-3 h-5 w-2/3 rounded-full" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className="mb-2 h-4 w-full rounded-full last:mb-0" />
      ))}
    </div>
  );
}
