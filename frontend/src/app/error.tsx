"use client";

import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/brand/Logo";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <LogoMark size={64} />
      <h1 className="text-2xl font-extrabold">Что-то пошло не так</h1>
      <p className="max-w-sm text-base text-muted-foreground">Мы уже знаем об ошибке. Попробуй обновить экран.</p>
      <Button size="lg" onClick={reset}>
        Попробовать снова
      </Button>
    </main>
  );
}
