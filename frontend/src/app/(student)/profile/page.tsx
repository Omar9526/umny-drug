"use client";

import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { toast } from "sonner";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { AvatarPicker, GradePicker, LanguageToggle } from "@/components/forms/pickers";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import { useCurricula } from "@/features/curriculum/api";
import { useUpdateStudent, type StudentUpdateInput } from "@/features/dashboard/api";
import { getErrorMessage } from "@/lib/api/client";
import { setLocaleCookie } from "@/lib/locale";
import type { Language } from "@/lib/api/types";

export default function ProfilePage() {
  const t = useTranslations("profile");
  const th = useTranslations("home");
  const ta = useTranslations("app");
  const router = useRouter();
  const locale = useLocale() as Language;
  const { user, logout } = useAuth();
  const student = user?.student;
  const curricula = useCurricula();
  const update = useUpdateStudent();
  const grades = curricula.data?.find((c) => c.code === student?.curriculum.code)?.grades ?? [];

  async function save(input: StudentUpdateInput) {
    try {
      await update.mutateAsync(input);
      toast.success(t("saved"));
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  function changeInterfaceLanguage(lang: Language) {
    setLocaleCookie(lang);
    router.refresh();
  }

  async function onLogout() {
    await logout();
    router.replace("/");
  }

  if (!student) return null;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} back={false} />

      <section className="flex items-center gap-4 rounded-[28px] bg-lime p-5">
        <ChildAvatar avatar={student.avatar} size="xl" />
        <div>
          <h2 className="text-2xl font-extrabold text-teal">{student.nickname}</h2>
          <p className="text-base font-semibold text-ink/80">{th("grade", { grade: student.grade.number })}</p>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-lg font-extrabold">{t("avatar")}</h3>
        <AvatarPicker value={student.avatar} onChange={(avatar) => save({ avatar })} />
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-lg font-extrabold">{t("explanationLanguage")}</h3>
        <LanguageToggle
          name={t("explanationLanguage")}
          value={student.explanation_language}
          onChange={(explanation_language) => save({ explanation_language })}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-lg font-extrabold">{t("interfaceLanguage")}</h3>
        <LanguageToggle name={t("interfaceLanguage")} value={locale} onChange={changeInterfaceLanguage} />
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="text-lg font-extrabold">{t("grade")}</h3>
        {grades.length > 0 && (
          <GradePicker grades={grades} value={student.grade.id} onChange={(grade_id) => save({ grade_id })} />
        )}
      </section>

      <section className="rounded-3xl bg-white p-5 shadow-card ring-1 ring-line">
        <h3 className="text-base font-extrabold">{t("forParents")}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{t("forParentsText")}</p>
      </section>

      <Button variant="outline" size="lg" onClick={onLogout} className="w-full">
        <LogOut /> {ta("logout")}
      </Button>
    </div>
  );
}
