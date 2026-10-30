"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { AvatarPicker, GradePicker, LanguageToggle } from "@/components/forms/pickers";
import { Hero } from "@/components/layout/Hero";
import { useAuth } from "@/features/auth/AuthProvider";
import { useCurricula } from "@/features/curriculum/api";
import { useUpdateStudent, type StudentUpdateInput } from "@/features/dashboard/api";
import { getErrorMessage } from "@/lib/api/client";

export default function ProfilePage() {
  const t = useTranslations("profile");
  const th = useTranslations("home");
  const ta = useTranslations("app");
  const router = useRouter();
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

  async function onLogout() {
    await logout();
    router.replace("/");
  }

  if (!student) return null;

  return (
    <div className="flex flex-col gap-6">
      <Hero>
        <p className="text-sm font-semibold text-ink/70">{t("title")}</p>
        <div className="mt-3 flex items-center gap-4">
          <ChildAvatar avatar={student.avatar} size="xl" className="pop-in ring-4 ring-white shadow-tile" />
          <div className="min-w-0">
            <h1 className="truncate font-heading text-[30px] leading-tight font-extrabold text-teal">{student.nickname}</h1>
            <p className="text-base font-semibold text-ink/75">{th("grade", { grade: student.grade.number })}</p>
          </div>
        </div>
      </Hero>

      <section className="flex flex-col gap-3">
        <h3 className="font-heading text-lg font-extrabold">{t("avatar")}</h3>
        <AvatarPicker value={student.avatar} onChange={(avatar) => save({ avatar })} />
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="font-heading text-lg font-extrabold">{t("language")}</h3>
        <LanguageToggle name={t("language")} value={student.language} onChange={(language) => save({ language })} />
      </section>

      <section className="flex flex-col gap-3">
        <h3 className="font-heading text-lg font-extrabold">{t("grade")}</h3>
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
