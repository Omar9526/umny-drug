import { cn } from "@/lib/utils";

/**
 * Line-art illustrations for subject tiles (the catalogue stores the icon key).
 * Drawn on a 96×96 grid with `currentColor`, so the same art works on lime and on dark teal.
 */
const ART: Record<string, React.ReactNode> = {
  // Математика — парабола на осях
  calculator: (
    <>
      <path d="M48 16v64M18 66h60" />
      <path d="M44 20l4-6 4 6M74 62l6 4-6 4" />
      <path d="M22 26c6 34 16 44 26 44s20-10 26-44" />
      <text x="55" y="22" fontSize="11" fontWeight="700" stroke="none" fill="currentColor">
        y
      </text>
      <text x="70" y="79" fontSize="11" fontWeight="700" stroke="none" fill="currentColor">
        x
      </text>
    </>
  ),
  // Алгебра — сигма и икс в квадрате
  sigma: (
    <>
      <path d="M30 22h34l-20 26 20 26H30" />
      <circle cx="70" cy="22" r="2" fill="currentColor" stroke="none" />
      <circle cx="70" cy="74" r="2" fill="currentColor" stroke="none" />
      <path d="M72 42l8 10M80 42l-8 10" />
    </>
  ),
  // Геометрия — изометрический куб
  triangle: (
    <>
      <path d="M48 16l27 15v30L48 76 21 61V31l27-15z" />
      <path d="M48 46L21 31M48 46l27-15M48 46v30" />
      <path d="M48 46L21 31v30l27 15V46z" fill="currentColor" fillOpacity="0.18" stroke="none" />
    </>
  ),
  // Русский язык — «Аа» и перо
  "pencil-line": (
    <>
      <text x="16" y="60" fontSize="44" fontWeight="800" stroke="none" fill="currentColor" fontFamily="inherit">
        Аа
      </text>
      <path d="M18 74c8-6 16-6 24 0s16 6 24 0" />
      <path d="M62 24l10-10 6 6-10 10-7 1 1-7z" />
    </>
  ),
  // Кыргызский язык — реплики с Ө и Ү
  languages: (
    <>
      <path d="M14 22h36a6 6 0 0 1 6 6v16a6 6 0 0 1-6 6H30l-10 8v-8h-6a6 6 0 0 1-6-6V28a6 6 0 0 1 6-6z" />
      <text x="23" y="45" fontSize="20" fontWeight="800" stroke="none" fill="currentColor" fontFamily="inherit">
        Ө
      </text>
      <path d="M46 48h36a6 6 0 0 1 6 6v16a6 6 0 0 1-6 6h-6v8l-10-8H46a6 6 0 0 1-6-6V54a6 6 0 0 1 6-6z" />
      <text x="56" y="71" fontSize="20" fontWeight="800" stroke="none" fill="currentColor" fontFamily="inherit">
        Ү
      </text>
    </>
  ),
  // Английский — глобус
  globe: (
    <>
      <circle cx="48" cy="48" r="30" />
      <ellipse cx="48" cy="48" rx="12" ry="30" />
      <path d="M18 48h60M23 33h50M23 63h50M48 18v60" />
    </>
  ),
  // Литература — открытая книга
  "book-open": (
    <>
      <path d="M48 30c-8-6-20-8-32-4v46c12-4 24-2 32 4 8-6 20-8 32-4V26c-12-4-24-2-32 4z" />
      <path d="M48 30v46" />
      <path d="M24 38c6-1 12-1 18 1M24 48c6-1 12-1 18 1M54 39c6-2 12-2 18-1M54 49c6-2 12-2 18-1" />
    </>
  ),
  // Кыргызская литература — книга с закладкой и орнаментом
  "book-marked": (
    <>
      <path d="M24 18h44a4 4 0 0 1 4 4v56H30a6 6 0 0 1-6-6V18z" />
      <path d="M24 72a6 6 0 0 1 6-6h42" />
      <path d="M54 18v24l6-5 6 5V18" />
      <path d="M32 44c3-6 8-6 10 0s7 6 10 0" />
      <path d="M32 54c3-6 8-6 10 0s7 6 10 0" />
    </>
  ),
  // История — античный храм
  landmark: (
    <>
      <path d="M16 36L48 18l32 18H16z" />
      <path d="M22 36v30M38 36v30M58 36v30M74 36v30" />
      <path d="M14 66h68M18 78h60" />
    </>
  ),
  // География — карта с меткой
  map: (
    <>
      <path d="M14 30l22-8 24 8 22-8v48l-22 8-24-8-22 8V30z" />
      <path d="M36 22v48M60 30v48" />
      <circle cx="48" cy="46" r="5" />
      <path d="M48 51v9" />
    </>
  ),
  // Биология — лист с прожилками
  leaf: (
    <>
      <path d="M22 74C22 42 42 24 78 20c0 36-18 56-56 54z" />
      <path d="M22 74c10-18 26-34 44-44" />
      <path d="M34 60c6 0 12-2 18-6M44 48c6-2 10-6 14-10M30 68c4 0 8-1 12-3" />
    </>
  ),
  // Физика — атом
  atom: (
    <>
      <ellipse cx="48" cy="48" rx="32" ry="12" />
      <ellipse cx="48" cy="48" rx="32" ry="12" transform="rotate(60 48 48)" />
      <ellipse cx="48" cy="48" rx="32" ry="12" transform="rotate(120 48 48)" />
      <circle cx="48" cy="48" r="4" fill="currentColor" stroke="none" />
      <circle cx="16" cy="48" r="2.5" fill="currentColor" stroke="none" />
      <circle cx="64" cy="20" r="2.5" fill="currentColor" stroke="none" />
      <circle cx="64" cy="76" r="2.5" fill="currentColor" stroke="none" />
    </>
  ),
  // Химия — молекула
  "flask-conical": (
    <>
      <path d="M51 49.5 40 43l-11.3 6.5v13L40 69l11.3-6.5v-13z" />
      <path d="M51 49.5 62.6 43l11.3 6.5v13L62.6 69l-11.3-6.5" />
      <path d="M40 43V30M73.9 49.5 84 43M28.7 62.5 18 69M62.6 69v11" />
      <circle cx="40" cy="28" r="2.5" fill="currentColor" stroke="none" />
      <circle cx="86" cy="42" r="2.5" fill="currentColor" stroke="none" />
      <circle cx="16" cy="70" r="2.5" fill="currentColor" stroke="none" />
      <circle cx="62.6" cy="82" r="2.5" fill="currentColor" stroke="none" />
    </>
  ),
  // Информатика — ноутбук с кодом
  laptop: (
    <>
      <rect x="20" y="22" width="56" height="38" rx="5" />
      <path d="M12 70h72M34 70v-4h28v4" />
      <path d="M40 34l-8 7 8 7M56 34l8 7-8 7M51 32l-6 18" />
    </>
  ),
  // Природоведение — росток
  sprout: (
    <>
      <path d="M48 80V46" />
      <path d="M48 60c0-14-12-20-24-18 2 14 12 20 24 18z" />
      <path d="M48 50c0-14 12-20 26-18-2 14-12 20-26 18z" />
      <path d="M30 80h36" />
    </>
  ),
  // Микроскоп
  microscope: (
    <>
      <path d="M24 78h50M44 78v-8" />
      <path d="M50 20l14-8 12 20-14 8z" />
      <path d="M60 40l6 10" />
      <path d="M28 60h40" />
      <path d="M40 60c-6-8-6-18 2-24" />
      <path d="M64 50c8 2 12 10 10 20" />
    </>
  ),
};

export function SubjectArt({
  icon,
  className,
  strokeWidth = 2.4,
}: {
  icon: string;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <svg
      viewBox="0 0 96 96"
      aria-hidden
      className={cn("shrink-0", className)}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {ART[icon] ?? ART["book-open"]}
    </svg>
  );
}
