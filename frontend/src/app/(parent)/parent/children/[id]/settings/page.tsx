"use client";

import { use, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { KeyRound, ShieldCheck, Trash2, UserRoundX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { Field } from "@/components/forms/Field";
import { AvatarPicker, GradePicker, LanguageToggle } from "@/components/forms/pickers";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { useCurricula } from "@/features/curriculum/api";
import { useChild, useDeactivateChild, useEraseChild, useUpdateChild, type ChildUpdateInput } from "@/features/parent/api";
import { getErrorMessage } from "@/lib/api/client";
import type { StudentProfile } from "@/lib/api/types";

type ControlKey = "share_conversations_with_parent" | "allow_photo_upload" | "allow_free_questions";

const CONTROLS: Array<{ key: ControlKey; label: string; hint: string }> = [
  { key: "share_conversations_with_parent", label: "shareConversations", hint: "shareConversationsHint" },
  { key: "allow_photo_upload", label: "allowPhoto", hint: "allowPhotoHint" },
  { key: "allow_free_questions", label: "allowQuestions", hint: "allowQuestionsHint" },
];

function ControlRow({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-4 py-3">
      <span className="min-w-0 flex-1">
        <span className="block text-base font-semibold">{label}</span>
        <span className="block text-sm text-muted-foreground">{hint}</span>
      </span>
      <Switch checked={checked} disabled={disabled} onCheckedChange={(value) => onChange(Boolean(value))} />
    </label>
  );
}

function SettingsForm({ child, id }: { child: StudentProfile; id: string }) {
  const t = useTranslations("parent.childSettings");
  const tf = useTranslations("parent.childForm");
  const ta = useTranslations("app");
  const router = useRouter();
  const curricula = useCurricula();
  const update = useUpdateChild(id);
  const deactivate = useDeactivateChild(id);
  const erase = useEraseChild(id);
  const [nickname, setNickname] = useState<string | null>(null);
  const [eraseOpen, setEraseOpen] = useState(false);
  const [erasePassword, setErasePassword] = useState("");
  const grades = curricula.data?.find((c) => c.code === child.curriculum.code)?.grades ?? [];
  const nicknameValue = nickname ?? child.nickname;
  const nicknameDirty = nicknameValue.trim() !== child.nickname;

  async function save(input: ChildUpdateInput) {
    try {
      await update.mutateAsync(input);
      toast.success(t("saved"));
      return true;
    } catch (error) {
      toast.error(getErrorMessage(error));
      return false;
    }
  }

  async function onDeactivate() {
    if (!window.confirm(t("deactivateConfirm", { name: child.nickname }))) return;
    try {
      await deactivate.mutateAsync();
      toast.success(t("deactivated"));
      router.replace("/parent");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function onErase() {
    if (!erasePassword) return;
    try {
      await erase.mutateAsync(erasePassword);
      toast.success(t("erased"));
      router.replace("/parent");
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <div className="flex items-center gap-4">
          <ChildAvatar avatar={child.avatar} size="xl" />
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-extrabold">{t("profile")}</h2>
            <Button variant="soft" size="sm" className="mt-2" render={<Link href={`/parent/children/${id}/pin`} />}>
              <KeyRound /> {t("changePin")}
            </Button>
          </div>
        </div>

        <form
          className="mt-5 flex flex-col gap-5"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!nicknameDirty) return;
            if (await save({ nickname: nicknameValue.trim() })) setNickname(null);
          }}
        >
          <Field label={tf("nickname")} hint={tf("nicknameHint")}>
            {(props) => (
              <div className="flex gap-2">
                <Input {...props} value={nicknameValue} minLength={2} maxLength={40} onChange={(e) => setNickname(e.target.value)} />
                <Button type="submit" disabled={!nicknameDirty || update.isPending}>
                  {ta("save")}
                </Button>
              </div>
            )}
          </Field>

          <Field label={tf("grade")}>
            {() =>
              curricula.isPending ? (
                <CardSkeleton lines={1} />
              ) : (
                <GradePicker grades={grades} value={child.grade.id} onChange={(grade_id) => void save({ grade_id })} />
              )
            }
          </Field>

          <Field label={tf("language")} hint={tf("languageHint")}>
            {() => <LanguageToggle name={tf("language")} value={child.language} onChange={(language) => void save({ language })} />}
          </Field>
          <Field label={tf("avatar")}>
            {() => <AvatarPicker value={child.avatar} onChange={(avatar) => void save({ avatar })} />}
          </Field>
        </form>
      </section>

      <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <h2 className="flex items-center gap-2 text-lg font-extrabold">
          <ShieldCheck className="size-5 text-teal" /> {t("controls")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("controlsHint")}</p>
        <div className="mt-2 divide-y divide-line">
          {CONTROLS.map((control) => (
            <ControlRow
              key={control.key}
              label={t(control.label)}
              hint={t(control.hint)}
              checked={child[control.key]}
              disabled={update.isPending}
              onChange={(value) => void save({ [control.key]: value })}
            />
          ))}
        </div>
      </section>

      <section className="rounded-[28px] border-2 border-destructive/30 bg-white p-5">
        <h2 className="text-lg font-extrabold text-destructive">{t("danger")}</h2>
        <div className="mt-3 flex flex-col gap-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-base font-semibold">{t("deactivate")}</p>
              <p className="text-sm text-muted-foreground">{t("deactivateHint")}</p>
            </div>
            <Button variant="outline" onClick={onDeactivate} disabled={deactivate.isPending}>
              <UserRoundX /> {t("deactivate")}
            </Button>
          </div>
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-base font-semibold">{t("erase")}</p>
                <p className="text-sm text-muted-foreground">{t("eraseHint")}</p>
              </div>
              {!eraseOpen && (
                <Button variant="destructive" onClick={() => setEraseOpen(true)}>
                  <Trash2 /> {t("erase")}
                </Button>
              )}
            </div>
            {eraseOpen && (
              <form
                className="rise-in flex flex-col gap-3 rounded-2xl bg-destructive/5 p-4 ring-1 ring-destructive/20"
                onSubmit={(e) => {
                  e.preventDefault();
                  void onErase();
                }}
              >
                <p className="text-sm font-semibold text-destructive">
                  {t("eraseConfirm", { name: child.nickname })}
                </p>
                <Field label={t("erasePassword")}>
                  {(props) => (
                    <Input
                      {...props}
                      type="password"
                      autoComplete="current-password"
                      value={erasePassword}
                      onChange={(e) => setErasePassword(e.target.value)}
                    />
                  )}
                </Field>
                <div className="flex gap-2">
                  <Button
                    type="submit"
                    variant="destructive"
                    disabled={!erasePassword || erase.isPending}
                  >
                    <Trash2 /> {t("eraseNow")}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setEraseOpen(false);
                      setErasePassword("");
                    }}
                  >
                    {ta("cancel")}
                  </Button>
                </div>
              </form>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export default function ChildSettingsPage({ params }: PageProps<"/parent/children/[id]/settings">) {
  const { id } = use(params);
  const t = useTranslations("parent.childSettings");
  const child = useChild(id);

  return (
    <div>
      <PageHeader title={t("title")} backHref={`/parent/children/${id}`} />
      {child.isPending && <CardSkeleton lines={4} />}
      {child.isError && <ErrorState error={child.error} onRetry={() => child.refetch()} />}
      {child.data && <SettingsForm child={child.data} id={id} />}
    </div>
  );
}
