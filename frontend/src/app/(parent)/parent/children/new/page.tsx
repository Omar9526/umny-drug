"use client";

import { useState } from "react";
import Link from "next/link";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ChildAvatar } from "@/components/brand/ChildAvatar";
import { Field } from "@/components/forms/Field";
import { AvatarPicker, GradePicker, LanguageToggle, PinInput } from "@/components/forms/pickers";
import { CardSkeleton, ErrorState } from "@/components/feedback/States";
import { PageHeader } from "@/components/layout/PageHeader";
import { useCurricula } from "@/features/curriculum/api";
import { useCreateChild } from "@/features/parent/api";
import { ApiError, getErrorMessage } from "@/lib/api/client";
import type { StudentProfile } from "@/lib/api/types";

export default function NewChildPage() {
  const t = useTranslations("parent.childForm");
  const te = useTranslations("errors");
  const curricula = useCurricula();
  const create = useCreateChild();
  const [created, setCreated] = useState<StudentProfile | null>(null);

  const schema = z.object({
    nickname: z.string().trim().min(2, te("nameMin")).max(40),
    grade_id: z.number({ error: te("required") }).int().positive(),
    language: z.enum(["ru", "ky"]),
    avatar: z.string(),
    pin: z
      .string()
      .regex(/^\d{4,6}$/, te("pin"))
      .refine((v) => new Set(v).size > 1, { message: te("pinSame") }),
    consent_confirmed: z.boolean().refine((v) => v, { message: te("consent") }),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      nickname: "",
      grade_id: undefined,
      language: "ru",
      avatar: "fox",
      pin: "",
      consent_confirmed: false,
    },
  });
  const { errors, isSubmitting } = form.formState;
  const grades = curricula.data?.find((c) => c.code === "kg")?.grades ?? curricula.data?.[0]?.grades ?? [];

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const child = await create.mutateAsync({ ...values, avatar: values.avatar });
      setCreated(child);
    } catch (error) {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors();
        let handled = false;
        for (const key of ["nickname", "grade_id", "pin", "consent_confirmed"] as const) {
          if (fields[key]) {
            form.setError(key, { message: fields[key] });
            handled = true;
          }
        }
        if (handled) return;
      }
      toast.error(getErrorMessage(error));
    }
  });

  if (created) {
    return (
      <div className="mx-auto max-w-md">
        <section className="rise-in flex flex-col items-center gap-4 rounded-[28px] bg-lime p-8 text-center">
          <ChildAvatar avatar={created.avatar} size="xl" />
          <h1 className="text-2xl font-extrabold text-teal">{t("successTitle", { name: created.nickname })}</h1>
          <p className="text-base text-ink/80">{t("successText")}</p>
          <Button size="lg" render={<Link href="/parent" />} className="mt-2">
            {t("toCabinet")}
          </Button>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <PageHeader title={t("title")} backHref="/parent" />
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
        <Field label={t("nickname")} hint={t("nicknameHint")} error={errors.nickname?.message}>
          {(props) => <Input {...props} autoComplete="off" {...form.register("nickname")} />}
        </Field>

        <Field label={t("grade")} error={errors.grade_id?.message}>
          {() => (
            <>
              {curricula.isPending && <CardSkeleton lines={1} />}
              {curricula.isError && <ErrorState error={curricula.error} onRetry={() => curricula.refetch()} />}
              {grades.length > 0 && (
                <Controller
                  control={form.control}
                  name="grade_id"
                  render={({ field }) => <GradePicker grades={grades} value={field.value ?? null} onChange={field.onChange} />}
                />
              )}
            </>
          )}
        </Field>

        <Field label={t("language")} hint={t("languageHint")}>
          {() => (
            <Controller
              control={form.control}
              name="language"
              render={({ field }) => <LanguageToggle name={t("language")} value={field.value} onChange={field.onChange} />}
            />
          )}
        </Field>

        <Field label={t("avatar")}>
          {() => (
            <Controller
              control={form.control}
              name="avatar"
              render={({ field }) => <AvatarPicker value={field.value as "fox"} onChange={field.onChange} />}
            />
          )}
        </Field>

        <Field label={t("pin")} hint={t("pinHint")} error={errors.pin?.message}>
          {(props) => (
            <Controller
              control={form.control}
              name="pin"
              render={({ field }) => (
                <PinInput id={props.id} value={field.value} onChange={field.onChange} invalid={props["aria-invalid"]} describedBy={props["aria-describedby"]} />
              )}
            />
          )}
        </Field>

        <label className="flex cursor-pointer items-start gap-3 rounded-2xl bg-muted p-4 text-base">
          <input type="checkbox" className="mt-1 size-5 shrink-0 accent-teal" {...form.register("consent_confirmed")} />
          <span>{t("consent")}</span>
        </label>
        {errors.consent_confirmed && (
          <p role="alert" className="-mt-3 text-sm font-medium text-destructive">
            {errors.consent_confirmed.message}
          </p>
        )}

        <Button type="submit" size="xl" className="w-full" disabled={isSubmitting || create.isPending}>
          {t("create")}
        </Button>
      </form>
    </div>
  );
}
