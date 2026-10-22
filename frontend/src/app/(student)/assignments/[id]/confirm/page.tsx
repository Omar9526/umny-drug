"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Check, Pencil, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { Markdown } from "@/components/tutor/Markdown";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAssignment, useConfirmAssignment, useImageObjectUrl } from "@/features/assignments/api";
import { useSubjects } from "@/features/curriculum/api";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

function Thumb({ imageId }: { imageId?: string }) {
  const [large, setLarge] = useState(false);
  const url = useImageObjectUrl(imageId);
  if (!url) return null;
  return (
    <button type="button" onClick={() => setLarge((v) => !v)} className="block w-full" aria-expanded={large}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt=""
        className={cn("mx-auto rounded-3xl object-contain ring-1 ring-line transition-all", large ? "max-h-[70vh]" : "max-h-40")}
      />
    </button>
  );
}

export default function ConfirmPage({ params }: PageProps<"/assignments/[id]/confirm">) {
  const { id } = use(params);
  const t = useTranslations("confirm");
  const router = useRouter();
  const assignment = useAssignment(id);
  const subjects = useSubjects();
  const confirm = useConfirmAssignment(id);
  // null / undefined mean «not edited yet»: the server value is shown until the child types or taps.
  const [textDraft, setTextDraft] = useState<string | null>(null);
  const [subjectDraft, setSubjectDraft] = useState<string | null | undefined>(undefined);
  const text = textDraft ?? assignment.data?.text ?? "";
  const subjectSlug = subjectDraft === undefined ? (assignment.data?.subject?.slug ?? null) : subjectDraft;
  const touched = textDraft !== null || subjectDraft !== undefined;

  // Already being worked on: jump straight into the session.
  useEffect(() => {
    const data = assignment.data;
    if (data?.session_id && (data.status === "in_progress" || data.status === "completed")) {
      router.replace(`/sessions/${data.session_id}`);
    }
  }, [assignment.data, router]);

  async function submit() {
    if (!text.trim()) {
      toast.error(t("empty"));
      return;
    }
    try {
      const result = await confirm.mutateAsync({ confirmed_text: text.trim(), subject_slug: subjectSlug });
      router.replace(`/sessions/${result.session.id}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  const data = assignment.data;
  const edited = data ? text.trim() !== data.recognized_text.trim() : false;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={t("title")} backHref={data?.upload_id ? `/assignments/uploads/${data.upload_id}` : "/home"} />
      {assignment.isPending && <CardSkeleton lines={5} />}
      {assignment.isError && <ErrorState error={assignment.error} onRetry={() => assignment.refetch()} />}
      {data && (
        <>
          <p className="text-base text-muted-foreground">{t("hint")}</p>
          {data.images[0] && <Thumb imageId={data.images[0].id} />}

          <section className="rounded-3xl bg-white p-4 shadow-card ring-1 ring-line">
            <p className="text-sm font-bold text-teal">{t("preview")}</p>
            <Markdown className="mt-1 rounded-2xl bg-lime-pale px-4 py-3 text-base">{text.trim() || "…"}</Markdown>
            <div className="mt-4 flex items-center justify-between">
              <label htmlFor="task-text" className="text-sm font-bold text-teal">
                {t("textLabel")} {data.label && <span className="text-muted-foreground">· {data.label}</span>}
              </label>
              {edited && (
                <span className="inline-flex items-center gap-1 rounded-full bg-lime px-2 py-0.5 text-xs font-bold">
                  <Pencil className="size-3" /> {t("edited")}
                </span>
              )}
            </div>
            <textarea
              id="task-text"
              value={text}
              onChange={(e) => setTextDraft(e.target.value)}
              rows={6}
              className="mt-2 w-full resize-y rounded-2xl border border-line bg-ivory px-4 py-3 text-base leading-snug outline-none focus-visible:ring-4 focus-visible:ring-teal/20"
            />
          </section>

          <section>
            <div className="mb-2 flex items-center gap-2">
              <h2 className="text-base font-bold">{t("subject")}</h2>
              {data.subject && !touched && (
                <span className="inline-flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                  <Sparkles className="size-3" /> {t("subjectAuto")}
                </span>
              )}
            </div>
            {subjects.isPending && <CardSkeleton lines={1} />}
            {subjects.data && (
              <ul className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 pb-1">
                {subjects.data.map((subject) => {
                  const selected = subject.slug === subjectSlug;
                  return (
                    <li key={subject.id}>
                      <button
                        type="button"
                        aria-pressed={selected}
                        onClick={() => setSubjectDraft(selected ? null : subject.slug)}
                        className={cn(
                          "tap-target flex shrink-0 items-center gap-2 rounded-full py-1.5 pr-4 pl-1.5 text-sm font-semibold ring-1 transition-colors",
                          selected ? "bg-teal text-white ring-teal" : "bg-white text-foreground ring-line hover:bg-muted",
                        )}
                      >
                        <SubjectIcon icon={subject.icon} color={selected ? "lime" : subject.color} size="sm" className="size-8 rounded-full [&_svg]:size-4" />
                        {subject.name}
                        {selected && <Check className="size-4" />}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <Button size="xl" className="w-full" onClick={submit} disabled={confirm.isPending || !text.trim()}>
            <Check /> {t("start")}
          </Button>
          {data.siblings.length > 0 && data.upload_id && (
            <Button variant="ghost" size="lg" render={<Link href={`/assignments/uploads/${data.upload_id}`} />}>
              {t("otherTask")}
            </Button>
          )}
        </>
      )}
    </div>
  );
}
