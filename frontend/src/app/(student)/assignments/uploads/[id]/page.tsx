"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Camera, ChevronRight, Keyboard, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SubjectIcon } from "@/components/brand/SubjectIcon";
import { Markdown } from "@/components/tutor/Markdown";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { assignmentsApi, useImageObjectUrl, useUpload } from "@/features/assignments/api";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { TaskBrief } from "@/lib/api/types";

function Thumb({ imageId }: { imageId?: string }) {
  const url = useImageObjectUrl(imageId);
  if (!url) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="" className="mx-auto max-h-44 rounded-3xl object-contain ring-1 ring-line" />;
}

function ProcessingCard() {
  const t = useTranslations("recognize");
  const tips = [t("tip1"), t("tip2"), t("tip3")];
  const [tip, setTip] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setTip((v) => (v + 1) % tips.length), 1800);
    return () => clearInterval(timer);
  }, [tips.length]);
  return (
    <section className="rise-in rounded-[28px] bg-lime p-6 text-center" aria-busy="true">
      <div className="mx-auto flex size-16 items-center justify-center rounded-full bg-white">
        <span className="size-7 animate-spin rounded-full border-4 border-teal border-t-transparent" />
      </div>
      <h2 className="mt-4 text-xl font-extrabold text-teal">{t("processing")}</h2>
      <p className="mt-1 text-base text-ink/80">{tips[tip]}</p>
      <p className="mt-3 text-sm text-muted-foreground">{t("processingHint")}</p>
    </section>
  );
}

function TaskCard({ task }: { task: TaskBrief }) {
  const t = useTranslations("recognize");
  const href =
    task.session_id && task.status !== "recognized" && task.status !== "confirmed"
      ? `/sessions/${task.session_id}`
      : `/assignments/${task.id}/confirm`;
  const done = task.status === "completed";
  return (
    <Link
      href={href}
      className={cn(
        "flex items-start gap-3 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line transition hover:bg-teal-soft",
        done && "opacity-70",
      )}
    >
      <SubjectIcon icon={task.subject?.icon ?? "book-open"} color={task.subject?.color ?? "sage"} size="sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {task.label && <span className="rounded-full bg-lime px-2 py-0.5 text-xs font-bold text-ink">{task.label}</span>}
          {task.subject && <span className="text-xs font-semibold text-muted-foreground">{task.subject.name}</span>}
        </div>
        <Markdown className="mt-1 line-clamp-3 text-base leading-snug [&_p]:m-0">{task.text || task.excerpt}</Markdown>
        <p className="mt-1 text-xs font-semibold text-teal">
          {done ? t("done") : task.status === "in_progress" ? t("inProgress") : t("open")}
        </p>
      </div>
      <ChevronRight className="mt-1 size-5 shrink-0 text-muted-foreground" />
    </Link>
  );
}

export default function UploadStatusPage({ params }: PageProps<"/assignments/uploads/[id]">) {
  const { id } = use(params);
  const t = useTranslations("recognize");
  const tc = useTranslations("capture");
  const router = useRouter();
  const upload = useUpload(id);
  const [retrying, setRetrying] = useState(false);
  const data = upload.data;

  // One task → straight to confirmation (no extra tap).
  useEffect(() => {
    if (data?.status === "recognized" && data.tasks.length === 1) {
      const task = data.tasks[0];
      router.replace(task.session_id && task.status !== "recognized" ? `/sessions/${task.session_id}` : `/assignments/${task.id}/confirm`);
    }
  }, [data, router]);

  async function retry() {
    setRetrying(true);
    try {
      await assignmentsApi.retryUpload(id);
      await upload.refetch();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title={tc("title")} backHref="/home" />
      {upload.isPending && <CardSkeleton className="h-48" />}
      {upload.isError && <ErrorState error={upload.error} onRetry={() => upload.refetch()} />}

      {data && (data.status === "pending" || data.status === "processing") && <ProcessingCard />}

      {data && data.status === "unreadable" && (
        <section className="rise-in rounded-[28px] bg-white p-6 shadow-card ring-1 ring-line">
          <Thumb imageId={data.images[0]?.id} />
          <h2 className="mt-4 text-xl font-extrabold">{t("unreadableTitle")}</h2>
          <p className="mt-1 text-base text-muted-foreground">{data.error_message}</p>
          <div className="mt-4 flex flex-col gap-2">
            <Button size="lg" render={<Link href="/assignments/new?source=camera" />}>
              <Camera /> {t("retake")}
            </Button>
            <Button size="lg" variant="soft" render={<Link href="/assignments/new?source=text" />}>
              <Keyboard /> {t("typeText")}
            </Button>
          </div>
        </section>
      )}

      {data && data.status === "failed" && (
        <section className="rise-in rounded-[28px] bg-destructive/5 p-6 ring-1 ring-destructive/20">
          <h2 className="text-xl font-extrabold text-destructive">{t("failedTitle")}</h2>
          <p className="mt-1 text-base">{data.error_message}</p>
          <Button size="lg" className="mt-4" onClick={retry} disabled={retrying}>
            <RefreshCw className={retrying ? "animate-spin" : undefined} /> {t("retry")}
          </Button>
        </section>
      )}

      {data && data.status === "recognized" && data.tasks.length > 1 && (
        <>
          <Thumb imageId={data.images[0]?.id} />
          <div>
            <h2 className="text-xl font-extrabold">{t("chooseTitle")}</h2>
            <p className="text-base text-muted-foreground">{t("chooseHint")}</p>
            <p className="mt-1 text-sm font-semibold text-teal">{t("found", { count: data.tasks.length })}</p>
          </div>
          <ul className="flex flex-col gap-3">
            {data.tasks.map((task, i) => (
              <li key={task.id} className="rise-in" style={{ animationDelay: `${i * 50}ms` }}>
                <TaskCard task={task} />
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
