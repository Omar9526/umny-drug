import type { CSSProperties } from "react";
import { cn } from "@/lib/utils";

const COLORS = ["#dff28c", "#0b4b4b", "#ffe4bf", "#ffffff", "#c6e45c", "#7fb8b2"];

/** Deterministic pseudo-random in [0, 1) so server and client render the same burst. */
function noise(seed: number) {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/** A short confetti burst (pure CSS, hidden under prefers-reduced-motion). Parent must be `relative`. */
export function Confetti({ count = 30, className }: { count?: number; className?: string }) {
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      {Array.from({ length: count }, (_, i) => {
        const style = {
          left: `${noise(i + 1) * 100}%`,
          background: COLORS[i % COLORS.length],
          width: 6 + Math.round(noise(i + 11) * 6),
          height: 10 + Math.round(noise(i + 23) * 8),
          borderRadius: i % 3 === 0 ? "9999px" : "3px",
          "--dx": `${Math.round((noise(i + 37) - 0.5) * 160)}px`,
          "--rot": `${Math.round(360 + noise(i + 41) * 540)}deg`,
          "--dur": `${(1.3 + noise(i + 53) * 1.1).toFixed(2)}s`,
          "--delay": `${(noise(i + 67) * 0.5).toFixed(2)}s`,
        } as CSSProperties;
        return <span key={i} className="confetti-piece absolute -top-4 block" style={style} />;
      })}
    </div>
  );
}
