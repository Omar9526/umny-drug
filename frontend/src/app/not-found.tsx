import Link from "next/link";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/brand/Logo";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
      <LogoMark size={64} />
      <h1 className="text-2xl font-extrabold">Такой страницы нет</h1>
      <p className="max-w-sm text-base text-muted-foreground">Возможно, ссылка устарела. Вернись на главную и продолжи оттуда.</p>
      <Button size="lg" render={<Link href="/" />}>
        На главную
      </Button>
    </main>
  );
}
