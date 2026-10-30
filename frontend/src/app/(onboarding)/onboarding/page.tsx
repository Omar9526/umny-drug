"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { LogoMark } from "@/components/brand/Logo";
import { AvatarPicker, GradePicker, LanguageToggle } from "@/components/forms/pickers";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { useAuth } from "@/features/auth/AuthProvider";
import { useCurricula } from "@/features/curriculum/api";
import { useUpdateStudent } from "@/features/dashboard/api";
import { getErrorMessage } from "@/lib/api/client";
import type { AvatarKey, Language } from "@/lib/api/types";

export default function OnboardingPage() {
  const t = useTranslations("onboarding");
  const tp = useTranslations("profile");
  const router = useRouter();
  const { user } = useAuth();
  const student = user?.student;
  const curricula = useCurricula();
  const update = useUpdateStudent();

  const [language, setLanguage] = useState<Language>(student?.language ?? "ru");
  const [gradeId, setGradeId] = useState<number | null>(student?.grade.id ?? null);
  const [avatar, setAvatar] = useState<AvatarKey>(student?.avatar ?? "fox");

  const grades = curricula.data?.find((c) => c.code === student?.curriculum.code)?.grades ?? [];

  async function finish() {
    if (!gradeId) return;
    try {
      await update.mutateAsync({ language, grade_id: gradeId, avatar, onboarding_completed: true });
      router.replace("/home");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rise-in rounded-[28px] bg-lime p-6">
        <LogoMark size={56} />
        <h1 className="mt-4 text-2xl font-extrabold text-teal">{t("hello")}</h1>
        <p className="mt-2 text-base text-ink/80">{t("intro")}</p>
      </section>

      <section className="rise-in rise-in-delay-1 flex flex-col gap-3">
        <h2 className="text-lg font-extrabold">{t("languageTitle")}</h2>
        <LanguageToggle name={tp("language")} value={language} onChange={setLanguage} />
      </section>

      <section className="rise-in rise-in-delay-2 flex flex-col gap-3">
        <h2 className="text-lg font-extrabold">{t("gradeTitle")}</h2>
        {curricula.isPending && <CardSkeleton />}
        {curricula.isError && <ErrorState error={curricula.error} onRetry={() => curricula.refetch()} />}
        {grades.length > 0 && <GradePicker grades={grades} value={gradeId} onChange={setGradeId} />}
      </section>

      <section className="rise-in rise-in-delay-3 flex flex-col gap-3">
        <h2 className="text-lg font-extrabold">{t("avatarTitle")}</h2>
        <AvatarPicker value={avatar} onChange={setAvatar} />
      </section>

      <Button size="xl" className="w-full" onClick={finish} disabled={!gradeId || update.isPending}>
        {t("start")}
      </Button>
    </div>
  );
}
