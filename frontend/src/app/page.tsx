"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Camera, ListChecks, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/brand/Logo";
import { FullScreenLoader } from "@/components/feedback/FullScreenLoader";
import { useAuth } from "@/features/auth/AuthProvider";
import { homePathFor } from "@/lib/locale";

export default function WelcomePage() {
  const t = useTranslations("welcome");
  const { status, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated" && user) {
      router.replace(homePathFor(user.role, user.student?.onboarding_completed));
    }
  }, [status, user, router]);

  if (status !== "anonymous") return <FullScreenLoader />;

  const points = [
    { icon: Camera, text: t("points.photo") },
    { icon: ListChecks, text: t("points.steps") },
    { icon: Users, text: t("points.parents") },
  ];

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-4 py-8 sm:justify-center">
      <section className="rise-in rounded-[32px] bg-lime p-6 sm:p-8">
        <LogoMark size={64} />
        <h1 className="mt-5 text-4xl font-extrabold text-teal">{t("title")}</h1>
        <p className="mt-2 text-lg leading-snug text-ink/80">{t("subtitle")}</p>
        <div className="mt-8 flex flex-col gap-3">
          <Button size="xl" render={<Link href="/child-login" />} className="w-full">
            {t("student")}
          </Button>
          <Button size="xl" variant="soft" render={<Link href="/login" />} className="w-full">
            {t("parent")}
          </Button>
        </div>
      </section>

      <ul className="rise-in rise-in-delay-1 mt-6 flex flex-col gap-3">
        {points.map(({ icon: Icon, text }) => (
          <li key={text} className="flex items-center gap-3 rounded-2xl bg-white px-4 py-3 shadow-card">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-teal-soft text-teal">
              <Icon className="size-5" />
            </span>
            <span className="text-base font-medium">{text}</span>
          </li>
        ))}
      </ul>

      <p className="rise-in rise-in-delay-2 mt-8 text-center text-base text-muted-foreground">
        {t("newHere")}{" "}
        <Link href="/register" className="font-semibold text-teal underline-offset-4 hover:underline">
          {t("createFamily")}
        </Link>
      </p>
    </main>
  );
}
