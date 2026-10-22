"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { PinInput } from "@/components/forms/pickers";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { useChildren, useSetPin } from "@/features/parent/api";
import { getErrorMessage } from "@/lib/api/client";

export default function ChildPinPage({ params }: PageProps<"/parent/children/[id]/pin">) {
  const { id } = use(params);
  const t = useTranslations("parent");
  const te = useTranslations("errors");
  const ta = useTranslations("app");
  const router = useRouter();
  const children = useChildren();
  const setPin = useSetPin(id);
  const [pin, setPinValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const child = children.data?.find((c) => c.id === id);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!/^\d{4,6}$/.test(pin)) return setError(te("pin"));
    if (new Set(pin).size === 1) return setError(te("pinSame"));
    setError(null);
    try {
      await setPin.mutateAsync(pin);
      toast.success(t("pinChanged"));
      router.replace("/parent");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title={t("changePin")} backHref="/parent" />
      {children.isPending && <CardSkeleton />}
      {children.isError && <ErrorState error={children.error} onRetry={() => children.refetch()} />}
      {children.data && !child && <ErrorState error={new Error("Not found")} />}
      {child && (
        <form onSubmit={submit} className="flex flex-col gap-4 rounded-3xl bg-white p-5 shadow-card ring-1 ring-line">
          <div className="flex items-center gap-3">
            <ChildAvatar avatar={child.avatar} size="md" />
            <p className="text-lg font-bold">{child.nickname}</p>
          </div>
          <label htmlFor="new-pin" className="text-base font-semibold">
            {t("newPin")}
          </label>
          <PinInput id="new-pin" value={pin} onChange={setPinValue} invalid={Boolean(error)} autoFocus />
          <p className="text-sm text-muted-foreground">{t("childForm.pinHint")}</p>
          {error && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" disabled={setPin.isPending || pin.length < 4}>
            {ta("save")}
          </Button>
        </form>
      )}
    </div>
  );
}
