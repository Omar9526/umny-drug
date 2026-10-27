import Link from "next/link";
import { SubjectArt } from "@/components/brand/SubjectArt";
import { cn } from "@/lib/utils";
import type { Subject } from "@/lib/api/types";

/**
 * Big illustrated subject tile (2-column grid). The catalogue colour decides the tone:
 * `teal` subjects are dark tiles with white line art, everything else is pale lime with teal art.
 */
export function SubjectTile({
  subject,
  caption,
  index = 0,
  className,
}: {
  subject: Pick<Subject, "slug" | "name" | "icon" | "color">;
  caption?: string;
  index?: number;
  className?: string;
}) {
  const dark = subject.color === "teal";
  return (
    <Link
      href={`/subjects/${subject.slug}`}
      className={cn(
        "pop-in group relative flex aspect-[0.92] flex-col items-center justify-center gap-2 rounded-[28px] p-4 text-center transition-transform duration-200 hover:-translate-y-0.5 active:scale-[0.98]",
        dark
          ? "bg-teal text-white shadow-float"
          : "bg-lime-pale text-teal shadow-tile ring-1 ring-lime-deep/50",
        className,
      )}
      style={{ animationDelay: `${Math.min(index, 8) * 60}ms` }}
    >
      <SubjectArt
        icon={subject.icon}
        className="size-[76px] transition-transform duration-300 group-hover:scale-105 group-hover:rotate-[-2deg]"
      />
      <span
        className={cn(
          "mt-1 leading-tight font-bold",
          subject.name.length > 22 ? "text-[13px]" : "text-[15px]",
          dark ? "text-white" : "text-ink",
        )}
      >
        {subject.name}
      </span>
      {caption && (
        <span className={cn("text-xs font-semibold", dark ? "text-white/70" : "text-muted-foreground")}>
          {caption}
        </span>
      )}
    </Link>
  );
}
