"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { SettingRow } from "@/components/parent/SettingRow";
import { useAuth } from "@/features/auth/AuthProvider";
import { disablePush, enablePush, readPushState, resyncPush } from "@/features/parent/push";
import { getErrorMessage } from "@/lib/api/client";
import { detectPushSupport } from "@/lib/push";

type State = "loading" | "unsupported" | "needs-install" | "denied" | "server-off" | "error" | "on" | "off";

const HINT_KEYS: Record<Exclude<State, "on" | "off" | "loading">, string> = {
  unsupported: "pushUnsupported",
  "needs-install": "pushNeedsInstall",
  denied: "pushDenied",
  "server-off": "pushServerOff",
  error: "pushError",
};

/**
 * «Push on this device» switch. The server knows which endpoints belong to which parent, so the switch is
 * on only when *this* parent registered *this* browser — a subscription left by someone else on a shared
 * phone shows as off and is taken over only by an explicit toggle.
 */
export function PushToggle() {
  const t = useTranslations("parent.family");
  const { user } = useAuth();
  const userId = user?.id ?? "";
  const [state, setState] = useState<State>("loading");
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const detect = async (): Promise<State> => {
      const support = detectPushSupport();
      if (support !== "ready") return support;
      const pushState = await readPushState();
      if (!cancelled) setPublicKey(pushState.config.public_key);
      if (!pushState.config.enabled) return "server-off";
      if (pushState.subscription && pushState.config.subscribed) return "on";
      return (await resyncPush(pushState, userId)) ? "on" : "off";
    };
    detect()
      .then((next) => {
        if (!cancelled) setState(next);
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [userId]);

  async function toggle(value: boolean) {
    setBusy(true);
    try {
      if (value) {
        if (!publicKey) {
          setState("server-off");
          return;
        }
        const result = await enablePush(publicKey, userId);
        if (result === "dismissed") return; // the browser prompt was closed without an answer: nothing changes
        if (result === "denied") {
          setState("denied");
          return;
        }
        if (result === "no-worker") {
          setState("unsupported");
          return;
        }
        setState("on");
        toast.success(t("pushEnabled"));
      } else {
        await disablePush();
        setState("off");
        toast.success(t("pushDisabled"));
      }
    } catch (error) {
      toast.error(getErrorMessage(error, t("pushError")));
    } finally {
      setBusy(false);
    }
  }

  const interactive = state === "on" || state === "off";
  const hint = interactive || state === "loading" ? t("pushNotifyHint") : t(HINT_KEYS[state]);

  return (
    <SettingRow
      label={t("pushNotify")}
      hint={hint}
      checked={state === "on"}
      disabled={!interactive || busy}
      onChange={(value) => void toggle(value)}
    />
  );
}
