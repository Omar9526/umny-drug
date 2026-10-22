import { cn } from "@/lib/utils";

/** Faint contour rings, like a topographic map — the brand texture behind lime heroes. */
export function Contours({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 320 320"
      className={cn("pointer-events-none absolute text-teal/[0.08]", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.2"
    >
      {[40, 70, 100, 130, 160, 190, 220].map((r) => (
        <ellipse key={r} cx="200" cy="120" rx={r * 1.15} ry={r} />
      ))}
    </svg>
  );
}

/**
 * Full-bleed lime block at the top of a student screen (greeting, subject header, topic header).
 * It escapes the 16px page gutter on phones and becomes a rounded card on wider screens.
 */
export function Hero({
  children,
  className,
  tone = "lime",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "lime" | "teal";
}) {
  return (
    <section
      className={cn(
        "relative -mx-4 -mt-4 overflow-hidden rounded-b-[36px] px-5 pt-5 pb-7 md:mx-0 md:mt-0 md:rounded-[36px]",
        tone === "lime" ? "bg-lime text-ink" : "bg-teal text-white",
        className,
      )}
    >
      <Contours className={cn("-top-10 -right-16 h-72 w-72", tone === "teal" && "text-white/10")} />
      <div className="relative">{children}</div>
    </section>
  );
}

/** Round white control used in heroes and headers (back, avatar, menu). */
export function roundButtonClass(extra?: string) {
  return cn(
    "inline-flex size-11 shrink-0 items-center justify-center rounded-full bg-white text-teal shadow-tile ring-1 ring-teal/10 transition active:scale-95 hover:bg-lime-pale [&_svg]:size-5",
    extra,
  );
}
