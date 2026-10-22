import { cn } from "@/lib/utils";

/** Brand mark: a friendly lime face on a teal tile (same art as the PWA icon). */
export function LogoMark({ className, size = 40 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      role="img"
      aria-label="Умный друг"
      className={cn("shrink-0", className)}
    >
      <rect width="100" height="100" rx="24" fill="#005359" />
      <circle cx="50" cy="50" r="34" fill="#E3F596" />
      <circle cx="37" cy="43" r="4.5" fill="#005359" />
      <circle cx="63" cy="43" r="4.5" fill="#005359" />
      <path d="M35 55c4 9 9 13 15 13s11-4 15-13" stroke="#005359" strokeWidth="6" strokeLinecap="round" fill="none" />
    </svg>
  );
}

export function Logo({ className, compact = false }: { className?: string; compact?: boolean }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <LogoMark size={compact ? 32 : 40} />
      {!compact && <span className="font-heading text-lg font-extrabold tracking-tight text-teal">Умный друг</span>}
    </span>
  );
}
