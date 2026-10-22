"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Search, X } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import {
  CardSkeleton,
  EmptyState,
  ErrorState,
} from "@/components/feedback/States";
import { Hero } from "@/components/layout/Hero";
import { SubjectTile } from "@/components/learning/SubjectTile";
import { useAuth } from "@/features/auth/AuthProvider";
import { useSubjects } from "@/features/curriculum/api";

export default function SubjectsPage() {
  const t = useTranslations("subjects");
  const th = useTranslations("home");
  const { user } = useAuth();
  const { data, isPending, isError, error, refetch } = useSubjects();
  const [query, setQuery] = useState("");
  const needle = query.trim().toLocaleLowerCase();
  const shown = data?.filter((s) =>
    needle ? s.name.toLocaleLowerCase().includes(needle) : true,
  );

  return (
    <div className="flex flex-col gap-5">
      <Hero>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-ink/70">
              {user?.student
                ? t("subtitle", { grade: user.student.grade.number })
                : t("title")}
            </p>
            <h1 className="mt-1 font-heading text-[30px] leading-[1.1] font-extrabold text-teal">
              {t("heroTitle")}
            </h1>
          </div>
          <LogoMark size={44} />
        </div>
        <label className="mt-5 flex h-13 items-center gap-3 rounded-full bg-white/90 px-5 ring-1 ring-teal/10 focus-within:ring-2 focus-within:ring-teal/40">
          <Search className="size-5 shrink-0 text-teal" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("search")}
            aria-label={t("search")}
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground"
          />
          {query && (
            <button
              type="button"
              aria-label={t("clear")}
              onClick={() => setQuery("")}
              className="flex size-7 items-center justify-center rounded-full bg-muted text-muted-foreground"
            >
              <X className="size-4" />
            </button>
          )}
        </label>
      </Hero>

      {isPending && (
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} className="aspect-[0.92]" lines={1} />
          ))}
        </div>
      )}
      {isError && <ErrorState error={error} onRetry={() => refetch()} />}
      {data && data.length === 0 && <EmptyState text={t("empty")} />}
      {shown && data && data.length > 0 && shown.length === 0 && (
        <EmptyState text={t("noMatches")} />
      )}
      {shown && shown.length > 0 && (
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {shown.map((subject, i) => (
            <li key={subject.id}>
              <SubjectTile
                subject={subject}
                index={i}
                caption={th("topicsCount", { count: subject.topics_count })}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
