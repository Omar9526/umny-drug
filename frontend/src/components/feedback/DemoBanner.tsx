"use client";

import { FlaskConical } from "lucide-react";
import { useTranslations } from "next-intl";
import { useAppMeta } from "@/features/auth/useAppMeta";

/** Permanent, unmissable marker whenever the backend runs without a real AI provider. */
export function DemoBanner() {
  const t = useTranslations("app");
  const { data } = useAppMeta();
  if (!data?.demo_mode) return null;
  return (
    <div
      role="status"
      className="flex items-start gap-2 rounded-2xl bg-warning/10 px-4 py-3 text-sm font-medium text-warning ring-1 ring-warning/30"
    >
      <FlaskConical className="mt-0.5 size-4 shrink-0" />
      <span>{t("demoBanner")}</span>
    </div>
  );
}
