import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { Logo } from "@/components/brand/Logo";

export async function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  const t = await getTranslations("legal");
  return (
    <div className="mx-auto w-full max-w-2xl px-4 py-8">
      <Link href="/" className="inline-block" aria-label="На главную">
        <Logo />
      </Link>
      <p className="mt-6 rounded-2xl bg-warning/10 px-4 py-3 text-sm font-semibold text-warning ring-1 ring-warning/30">
        {t("draftNotice")}
      </p>
      <article className="mt-6 rounded-[28px] bg-white p-6 shadow-card sm:p-8 [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-extrabold [&_p]:mt-2 [&_p]:text-base [&_p]:leading-relaxed">
        <h1 className="text-2xl font-extrabold">{title}</h1>
        {children}
      </article>
    </div>
  );
}
