import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { WifiOff } from "lucide-react";
import { LogoMark } from "@/components/brand/Logo";
import { Contours } from "@/components/layout/Hero";
import { RetryButton } from "./RetryButton";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("offline");
  return { title: t("title"), robots: { index: false, follow: false } };
}

/**
 * Fallback the service worker serves for any navigation made without network (see `public/sw.js`).
 * Precached on install, so it must stay self-contained: no API calls, no user data.
 */
export default async function OfflinePage() {
  const t = await getTranslations("offline");
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-4 py-8 sm:justify-center">
      <section className="rise-in relative overflow-hidden rounded-[32px] bg-lime p-6 sm:p-8">
        <Contours className="-top-10 -right-16 h-72 w-72" />
        <div className="relative">
          <div className="flex items-center justify-between gap-3">
            <span className="flex size-14 items-center justify-center rounded-full bg-white text-teal shadow-tile ring-1 ring-teal/10">
              <WifiOff className="size-7" aria-hidden />
            </span>
            <LogoMark size={44} />
          </div>
          <h1 className="mt-6 font-heading text-[32px] leading-[1.1] font-extrabold text-teal">{t("title")}</h1>
          <p className="mt-3 text-base text-ink/80">{t("text")}</p>
          <RetryButton label={t("retry")} />
        </div>
      </section>
      <p className="rise-in rise-in-delay-1 mt-6 text-center text-base text-muted-foreground">{t("hint")}</p>
    </main>
  );
}
