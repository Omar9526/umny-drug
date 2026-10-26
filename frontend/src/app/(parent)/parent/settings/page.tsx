"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useFormatter, useLocale, useTranslations } from "next-intl";
import { toast } from "sonner";
import { Check, Copy, FileText, LogOut, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/forms/Field";
import { LanguageToggle } from "@/components/forms/pickers";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PushToggle } from "@/components/parent/PushToggle";
import { SettingRow } from "@/components/parent/SettingRow";
import { PageHeader } from "@/components/layout/PageHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  useChildren,
  useConsents,
  useDeleteFamily,
  useFamily,
  useFamilySettings,
  useRevokeConsent,
  useRotateCode,
  useUpdateFamilySettings,
} from "@/features/parent/api";
import { getErrorMessage } from "@/lib/api/client";
import { setLocaleCookie } from "@/lib/locale";
import type { ConsentRecord, Language } from "@/lib/api/types";

const REVOCABLE: ConsentRecord["consent_type"][] = ["child_data", "ai_processing", "marketing"];

export default function FamilySettingsPage() {
  const t = useTranslations("parent.family");
  const tp = useTranslations("parent");
  const ta = useTranslations("app");
  const tpr = useTranslations("profile");
  const router = useRouter();
  const format = useFormatter();
  const locale = useLocale() as Language;
  const { user, logout } = useAuth();
  const family = useFamily();
  const settings = useFamilySettings();
  const consents = useConsents();
  const children = useChildren();
  const rotate = useRotateCode();
  const updateSettings = useUpdateFamilySettings();
  const revoke = useRevokeConsent();
  const deleteFamily = useDeleteFamily();
  const [copied, setCopied] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [understood, setUnderstood] = useState(false);

  const childName = (studentId: string | null) => children.data?.find((c) => c.id === studentId)?.nickname ?? null;

  async function copyCode() {
    if (!family.data) return;
    try {
      await navigator.clipboard.writeText(family.data.display_code);
      setCopied(true);
      toast.success(ta("copied"));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(ta("errorGeneric"));
    }
  }

  async function rotateCode() {
    if (!window.confirm(tp("rotateConfirm"))) return;
    try {
      await rotate.mutateAsync();
      toast.success(t("codeRotated"));
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function toggle(key: "notify_weekly_report" | "notify_email", value: boolean) {
    try {
      await updateSettings.mutateAsync({ [key]: value });
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  function changeInterfaceLanguage(lang: Language) {
    setLocaleCookie(lang);
    router.refresh();
  }

  async function onRevoke(consent: ConsentRecord) {
    const message = consent.student_id ? t("revokeChildConfirm", { name: childName(consent.student_id) ?? "" }) : t("revokeConfirm");
    if (!window.confirm(message)) return;
    try {
      await revoke.mutateAsync(consent.id);
      toast.success(t("revokedToast"));
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function onDelete(e: React.FormEvent) {
    e.preventDefault();
    if (!understood || !password) return;
    try {
      await deleteFamily.mutateAsync(password);
      toast.success(t("deleted"));
      try {
        await logout();
      } finally {
        router.replace("/");
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }

  async function onLogout() {
    await logout();
    router.replace("/");
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("title")} subtitle={user?.email} back={false} />

      <section className="rounded-[28px] bg-lime p-5">
        <h2 className="text-base font-extrabold text-teal">{tp("familyCodeTitle")}</h2>
        <p className="mt-1 text-sm text-ink/80">{tp("familyCodeText")}</p>
        {family.isPending && <div className="mt-3 h-14 animate-pulse rounded-2xl bg-white/60" />}
        {family.isError && <ErrorState className="mt-3" error={family.error} onRetry={() => family.refetch()} />}
        {family.data && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <span className="rounded-2xl bg-white px-4 py-2.5 font-heading text-2xl font-extrabold tracking-[0.2em] text-teal">
              {family.data.display_code}
            </span>
            <Button variant="soft" size="sm" onClick={copyCode} aria-label={ta("copy")}>
              {copied ? <Check /> : <Copy />} {ta("copy")}
            </Button>
            <Button variant="ghost" size="sm" onClick={rotateCode} disabled={rotate.isPending}>
              <RefreshCw className={rotate.isPending ? "animate-spin" : undefined} /> {tp("rotateCode")}
            </Button>
          </div>
        )}
      </section>

      <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <h2 className="text-lg font-extrabold">{t("notifications")}</h2>
        {settings.isPending && <CardSkeleton className="mt-3" lines={2} />}
        {settings.isError && <ErrorState className="mt-3" error={settings.error} onRetry={() => settings.refetch()} />}
        {settings.data && (
          <div className="mt-1 divide-y divide-line">
            <SettingRow
              label={t("weeklyReport")}
              hint={t("weeklyReportHint")}
              checked={settings.data.notify_weekly_report}
              disabled={updateSettings.isPending}
              onChange={(value) => void toggle("notify_weekly_report", value)}
            />
            <SettingRow
              label={t("emailNotify")}
              hint={t("emailNotifyHint")}
              checked={settings.data.notify_email}
              disabled={updateSettings.isPending}
              onChange={(value) => void toggle("notify_email", value)}
            />
            <PushToggle />
          </div>
        )}
        <Field label={tpr("interfaceLanguage")} className="mt-4">
          {() => <LanguageToggle name={tpr("interfaceLanguage")} value={locale} onChange={changeInterfaceLanguage} />}
        </Field>
      </section>

      <section className="rounded-[28px] bg-white p-5 shadow-card ring-1 ring-line">
        <h2 className="flex items-center gap-2 text-lg font-extrabold">
          <ShieldCheck className="size-5 text-teal" /> {t("consents")}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("consentsHint")}</p>
        {consents.isPending && <CardSkeleton className="mt-3" lines={3} />}
        {consents.isError && <ErrorState className="mt-3" error={consents.error} onRetry={() => consents.refetch()} />}
        {consents.data && (
          <ul className="mt-2 divide-y divide-line">
            {consents.data.map((consent) => {
              const name = childName(consent.student_id);
              return (
                <li key={consent.id} className="flex items-center gap-3 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-base font-semibold">
                      {consent.consent_type_label}
                      {name && <span className="text-muted-foreground"> · {t("forChild", { name })}</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {consent.granted
                        ? t("granted", { date: format.dateTime(new Date(consent.granted_at), { dateStyle: "medium" }) })
                        : t("revoked", {
                            date: format.dateTime(new Date(consent.revoked_at ?? consent.granted_at), { dateStyle: "medium" }),
                          })}
                      {" · v"}
                      {consent.version}
                    </p>
                  </div>
                  {consent.granted && REVOCABLE.includes(consent.consent_type) && (
                    <Button variant="outline" size="sm" onClick={() => onRevoke(consent)} disabled={revoke.isPending}>
                      {t("revoke")}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <div className="mt-4 flex flex-wrap gap-3 text-sm font-bold text-teal">
          <Link href="/legal/privacy" className="inline-flex items-center gap-1 hover:underline">
            <FileText className="size-4" /> {t("privacy")}
          </Link>
          <Link href="/legal/terms" className="inline-flex items-center gap-1 hover:underline">
            <FileText className="size-4" /> {t("terms")}
          </Link>
        </div>
      </section>

      <section className="rounded-[28px] border-2 border-destructive/30 bg-white p-5">
        <h2 className="text-lg font-extrabold text-destructive">{t("deleteTitle")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("deleteText")}</p>
        {!deleteOpen ? (
          <Button variant="outline" className="mt-3" onClick={() => setDeleteOpen(true)}>
            <Trash2 /> {t("deleteButton")}
          </Button>
        ) : (
          <form className="mt-4 flex flex-col gap-4" onSubmit={onDelete}>
            <Field label={t("password")}>
              {(props) => (
                <Input
                  {...props}
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              )}
            </Field>
            <label className="flex items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1 size-4 accent-teal"
                checked={understood}
                onChange={(e) => setUnderstood(e.target.checked)}
              />
              <span>{t("deleteCheckbox")}</span>
            </label>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" variant="destructive" disabled={!understood || !password || deleteFamily.isPending}>
                <Trash2 /> {t("deleteButton")}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setDeleteOpen(false)}>
                {ta("cancel")}
              </Button>
            </div>
          </form>
        )}
      </section>

      <Button variant="ghost" className="self-start" onClick={onLogout}>
        <LogOut /> {ta("logout")}
      </Button>
    </div>
  );
}
