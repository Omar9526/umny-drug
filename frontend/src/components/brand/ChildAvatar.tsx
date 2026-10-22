import { cn } from "@/lib/utils";
import type { AvatarKey } from "@/lib/api/types";

/** Preset avatars only: children never upload photos of themselves. */
export const AVATARS: Record<AvatarKey, { emoji: string; bg: string; label: string }> = {
  fox: { emoji: "🦊", bg: "bg-[#FFE4C7]", label: "Лисёнок" },
  owl: { emoji: "🦉", bg: "bg-[#E6E1F7]", label: "Сова" },
  cat: { emoji: "🐱", bg: "bg-[#FBE3E3]", label: "Котик" },
  panda: { emoji: "🐼", bg: "bg-[#E8EEF2]", label: "Панда" },
  robot: { emoji: "🤖", bg: "bg-[#DDF1F0]", label: "Робот" },
  rocket: { emoji: "🚀", bg: "bg-[#E3F596]", label: "Ракета" },
  star: { emoji: "⭐", bg: "bg-[#FFF3C4]", label: "Звезда" },
  dino: { emoji: "🦕", bg: "bg-[#DDF5D6]", label: "Динозаврик" },
  whale: { emoji: "🐳", bg: "bg-[#D9EBFA]", label: "Кит" },
  bee: { emoji: "🐝", bg: "bg-[#FDF0BF]", label: "Пчёлка" },
};

export const AVATAR_KEYS = Object.keys(AVATARS) as AvatarKey[];

export function ChildAvatar({
  avatar,
  size = "md",
  className,
  selected,
}: {
  avatar: AvatarKey;
  size?: "sm" | "md" | "lg" | "xl";
  className?: string;
  selected?: boolean;
}) {
  const preset = AVATARS[avatar] ?? AVATARS.fox;
  const sizes = {
    sm: "size-9 text-lg",
    md: "size-12 text-2xl",
    lg: "size-16 text-3xl",
    xl: "size-24 text-5xl",
  };
  return (
    <span
      aria-label={preset.label}
      role="img"
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full leading-none select-none",
        preset.bg,
        sizes[size],
        selected && "ring-4 ring-teal ring-offset-2 ring-offset-background",
        className,
      )}
    >
      {preset.emoji}
    </span>
  );
}
