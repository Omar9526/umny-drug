import {
  Atom,
  BookMarked,
  BookOpen,
  Calculator,
  FlaskConical,
  Globe,
  Landmark,
  Languages,
  Laptop,
  Leaf,
  Map as MapIcon,
  Microscope,
  PencilLine,
  Sigma,
  Sprout,
  Triangle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

/** Icon names are stored in the Subject catalogue (admin-editable); unknown names fall back to a book. */
const ICONS: Record<string, LucideIcon> = {
  calculator: Calculator,
  sigma: Sigma,
  triangle: Triangle,
  "pencil-line": PencilLine,
  languages: Languages,
  globe: Globe,
  "book-open": BookOpen,
  "book-marked": BookMarked,
  landmark: Landmark,
  map: MapIcon,
  leaf: Leaf,
  atom: Atom,
  "flask-conical": FlaskConical,
  laptop: Laptop,
  sprout: Sprout,
  microscope: Microscope,
};

const COLORS: Record<string, string> = {
  lime: "bg-lime text-ink",
  teal: "bg-teal text-white",
  sage: "bg-sage/60 text-ink",
  ivory: "bg-white text-teal ring-1 ring-line",
};

export function SubjectIcon({
  icon,
  color = "lime",
  className,
  size = "md",
}: {
  icon: string;
  color?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const Icon = ICONS[icon] ?? BookOpen;
  const sizes = { sm: "size-9 [&_svg]:size-4", md: "size-12 [&_svg]:size-6", lg: "size-16 [&_svg]:size-8" };
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-2xl",
        COLORS[color] ?? COLORS.lime,
        sizes[size],
        className,
      )}
    >
      <Icon strokeWidth={1.75} />
    </span>
  );
}
