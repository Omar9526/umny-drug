"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { useTranslations } from "next-intl";
import { Download, Share, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { isIosSafari, isStandalone } from "@/lib/pwa";

/** Chromium-only event; not in the TS DOM lib. */
interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  readonly userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
}

export const INSTALL_DISMISSED_KEY = "ud_install_dismissed_until";
const DISMISS_FOR_MS = 14 * 24 * 60 * 60 * 1000;

function isDismissed(now = Date.now()): boolean {
  try {
    const until = Number(window.localStorage.getItem(INSTALL_DISMISSED_KEY));
    return Number.isFinite(until) && until > now;
  } catch {
    return false;
  }
}

function rememberDismissal() {
  try {
    window.localStorage.setItem(INSTALL_DISMISSED_KEY, String(Date.now() + DISMISS_FOR_MS));
  } catch {
    // Storage unavailable (private mode, blocked site data): the banner comes back on the next visit.
  }
}

const noopSubscribe = () => () => {};
/** Evaluated on the client only; the server snapshot keeps SSR markup banner-free. */
const iosHintSnapshot = () => isIosSafari() && !isStandalone() && !isDismissed();
const serverSnapshot = () => false;

/** Small "install the app" banner for the student and parent home screens. */
export function InstallPrompt() {
  const t = useTranslations("pwa");
  const iosHint = useSyncExternalStore(noopSubscribe, iosHintSnapshot, serverSnapshot);
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    if (isStandalone() || isDismissed()) return;
    const onBeforeInstall = (event: Event) => {
      event.preventDefault();
      setDeferred(event as BeforeInstallPromptEvent);
    };
    const onInstalled = () => setHidden(true);
    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const mode = hidden ? null : deferred ? "native" : iosHint ? "ios" : null;
  if (!mode) return null;

  const later = () => {
    rememberDismissal();
    setHidden(true);
  };

  const install = async () => {
    if (!deferred) return;
    try {
      await deferred.prompt();
      const { outcome } = await deferred.userChoice;
      if (outcome === "dismissed") rememberDismissal();
    } finally {
      // A deferred prompt can be used only once.
      setDeferred(null);
      setHidden(true);
    }
  };

  return (
    <aside
      aria-label={t("installTitle")}
      className="rise-in flex items-start gap-3 rounded-2xl bg-white p-3 shadow-card ring-1 ring-line"
    >
      <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-lime text-teal">
        {mode === "ios" ? <Share className="size-5" /> : <Download className="size-5" />}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-base font-bold">{t("installTitle")}</p>
        <p className="text-sm text-muted-foreground">
          {mode === "ios" ? t("installIosHint") : t("installText")}
        </p>
        {mode === "native" && (
          <div className="mt-2 flex flex-wrap gap-2">
            <Button size="sm" className="h-11" onClick={install}>
              {t("install")}
            </Button>
            <Button size="sm" variant="ghost" className="h-11" onClick={later}>
              {t("later")}
            </Button>
          </div>
        )}
      </div>
      {mode === "ios" && (
        <Button size="icon" variant="ghost" aria-label={t("later")} onClick={later}>
          <X />
        </Button>
      )}
    </aside>
  );
}
