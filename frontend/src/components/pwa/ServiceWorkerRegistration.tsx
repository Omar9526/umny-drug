"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

const UPDATE_TOAST_ID = "sw-update";

/**
 * Registers `/sw.js` in production builds only (in `next dev` a worker would cache hot-reloaded chunks).
 * When a new worker is installed and waiting, offers a quiet "Update" toast; accepting it activates the
 * worker via `SKIP_WAITING` and reloads once it takes control.
 */
export function ServiceWorkerRegistration() {
  const t = useTranslations("pwa");

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;

    const sw = navigator.serviceWorker;
    let reloading = false;
    const onControllerChange = () => {
      if (reloading) return;
      reloading = true;
      window.location.reload();
    };

    const offerUpdate = (worker: ServiceWorker) => {
      toast(t("updateAvailable"), {
        id: UPDATE_TOAST_ID,
        duration: Infinity,
        action: {
          label: t("updateAction"),
          onClick: () => {
            sw.addEventListener("controllerchange", onControllerChange);
            worker.postMessage({ type: "SKIP_WAITING" });
          },
        },
      });
    };

    const register = async () => {
      try {
        const registration = await sw.register("/sw.js", { scope: "/" });
        // A worker already waiting from an earlier visit; without a controller this is the first install.
        if (registration.waiting && sw.controller) offerUpdate(registration.waiting);
        registration.addEventListener("updatefound", () => {
          const installing = registration.installing;
          if (!installing) return;
          installing.addEventListener("statechange", () => {
            if (installing.state === "installed" && sw.controller) offerUpdate(installing);
          });
        });
      } catch (error) {
        // The app works without a worker; just leave a trace for debugging.
        console.error("Service worker registration failed", error);
      }
    };

    if (document.readyState === "complete") {
      void register();
    } else {
      window.addEventListener("load", register, { once: true });
    }
    return () => {
      window.removeEventListener("load", register);
      sw.removeEventListener("controllerchange", onControllerChange);
    };
  }, [t]);

  return null;
}
