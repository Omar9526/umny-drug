import { LogoMark } from "@/components/brand/Logo";

export function FullScreenLoader() {
  return (
    <div className="flex min-h-dvh flex-1 flex-col items-center justify-center gap-4 bg-background" aria-busy="true">
      <LogoMark size={56} className="animate-pulse" />
      <span className="sr-only">Загружаем…</span>
    </div>
  );
}
