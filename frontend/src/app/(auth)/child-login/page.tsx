"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { PinInput } from "@/components/forms/pickers";
import { AuthCard } from "@/components/layout/AuthCard";
import { authApi } from "@/features/auth/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, getErrorMessage } from "@/lib/api/client";
import { homePathFor } from "@/lib/locale";
import type { ChildPublic } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type Step = "code" | "child" | "pin";

function formatCode(raw: string): string {
  const clean = raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
  return clean.length > 3 ? `${clean.slice(0, 3)}-${clean.slice(3)}` : clean;
}

export default function ChildLoginPage() {
  const t = useTranslations("auth");
  const te = useTranslations("errors");
  const ta = useTranslations("app");
  const router = useRouter();
  const { setSession } = useAuth();

  const [step, setStep] = useState<Step>("code");
  const [code, setCode] = useState("");
  const [children, setChildren] = useState<ChildPublic[]>([]);
  const [familyLabel, setFamilyLabel] = useState("");
  const [child, setChild] = useState<ChildPublic | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const cleanCode = code.replace(/[^A-Z0-9]/g, "");

  async function lookup() {
    if (cleanCode.length !== 6) {
      setError(te("familyCode"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await authApi.childLookup(cleanCode);
      setChildren(result.children);
      setFamilyLabel(result.family.display_code);
      setStep("child");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function login() {
    if (!child) return;
    if (pin.length < 4) {
      setError(te("pin"));
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await authApi.childLogin(cleanCode, child.id, pin);
      setSession(result.access, result.user);
      router.replace(homePathFor(result.user.role, result.user.student?.onboarding_completed));
    } catch (err) {
      if (err instanceof ApiError && err.code === "account_locked") setError(t("locked"));
      else if (err instanceof ApiError && err.code === "pin_reset_required") setError(t("lockedReset"));
      else setError(getErrorMessage(err));
      setPin("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard
      title={t("childLoginTitle")}
      footer={
        <Link href="/login" className="font-semibold text-teal underline-offset-4 hover:underline">
          {t("iAmParent")}
        </Link>
      }
    >
      {step === "code" && (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void lookup();
          }}
        >
          <div>
            <label htmlFor="family-code" className="text-base font-semibold">
              {t("familyCodeStep")}
            </label>
            <p className="text-sm text-muted-foreground">{t("familyCodeHint")}</p>
          </div>
          <input
            id="family-code"
            value={code}
            onChange={(e) => setCode(formatCode(e.target.value))}
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            autoComplete="off"
            inputMode="text"
            placeholder="ABC-123"
            aria-invalid={Boolean(error)}
            className={cn(
              "h-16 w-full rounded-2xl border border-input bg-white text-center font-heading text-3xl font-extrabold tracking-[0.2em] uppercase outline-none placeholder:text-muted-foreground/40 focus-visible:border-ring focus-visible:ring-4 focus-visible:ring-ring/20",
              error && "border-destructive ring-4 ring-destructive/15",
            )}
          />
          {error && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="xl" className="w-full" disabled={busy}>
            {t("findFamily")}
          </Button>
        </form>
      )}

      {step === "child" && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <p className="text-base font-semibold">{t("chooseChild")}</p>
            <span className="rounded-full bg-muted px-3 py-1 text-sm font-semibold text-muted-foreground">{familyLabel}</span>
          </div>
          {children.length === 0 ? (
            <p className="rounded-2xl bg-muted p-4 text-base">{t("noChildren")}</p>
          ) : (
            <ul className="grid grid-cols-2 gap-3">
              {children.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setChild(c);
                      setError(null);
                      setStep("pin");
                    }}
                    className="flex w-full flex-col items-center gap-2 rounded-3xl bg-white p-4 shadow-card ring-1 ring-line transition hover:bg-lime/40 focus-visible:ring-4 focus-visible:ring-ring/30"
                  >
                    <ChildAvatar avatar={c.avatar} size="lg" />
                    <span className="text-lg font-bold">{c.nickname}</span>
                    <span className="text-sm text-muted-foreground">{t("gradeLabel", { grade: c.grade_number })}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <Button variant="ghost" onClick={() => setStep("code")}>
            <ArrowLeft /> {t("otherFamily")}
          </Button>
        </div>
      )}

      {step === "pin" && child && (
        <form
          className="flex flex-col gap-4"
          onSubmit={(e) => {
            e.preventDefault();
            void login();
          }}
        >
          <div className="flex items-center gap-3">
            <ChildAvatar avatar={child.avatar} size="md" />
            <div>
              <p className="text-lg font-bold">{child.nickname}</p>
              <p className="text-sm text-muted-foreground">{t("pinHint")}</p>
            </div>
          </div>
          <label htmlFor="pin" className="text-base font-semibold">
            {t("enterPin")}
          </label>
          <PinInput id="pin" value={pin} onChange={setPin} invalid={Boolean(error)} autoFocus />
          {error && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="xl" className="w-full" disabled={busy || pin.length < 4}>
            {t("enter")}
          </Button>
          <p className="text-center text-sm text-muted-foreground">{t("forgotPin")}</p>
          <Button variant="ghost" onClick={() => setStep("child")}>
            <ArrowLeft /> {ta("back")}
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
