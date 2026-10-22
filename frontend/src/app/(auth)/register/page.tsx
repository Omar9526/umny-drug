"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/forms/Field";
import { LanguageToggle } from "@/components/forms/pickers";
import { AuthCard } from "@/components/layout/AuthCard";
import { authApi } from "@/features/auth/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, getErrorMessage } from "@/lib/api/client";
import { setLocaleCookie } from "@/lib/locale";

export default function RegisterPage() {
  const t = useTranslations("auth");
  const te = useTranslations("errors");
  const router = useRouter();
  const { setSession } = useAuth();

  const schema = z.object({
    display_name: z.string().trim().min(2, te("nameMin")).max(80),
    email: z.email(te("email")),
    password: z.string().min(8, te("passwordMin")).max(128),
    preferred_language: z.enum(["ru", "ky"]),
    terms: z.boolean().refine((v) => v, { message: te("consent") }),
    privacy: z.boolean().refine((v) => v, { message: te("consent") }),
    marketing: z.boolean(),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      display_name: "",
      email: "",
      password: "",
      preferred_language: "ru",
      terms: false,
      privacy: false,
      marketing: false,
    },
  });
  const { errors, isSubmitting } = form.formState;

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const result = await authApi.registerParent({
        display_name: values.display_name,
        email: values.email,
        password: values.password,
        preferred_language: values.preferred_language,
        consents: { terms: values.terms, privacy: values.privacy, marketing: values.marketing },
      });
      setSession(result.access, result.user);
      setLocaleCookie(values.preferred_language);
      router.replace("/parent");
      router.refresh();
    } catch (error) {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors();
        let handled = false;
        for (const key of ["display_name", "email", "password"] as const) {
          if (fields[key]) {
            form.setError(key, { message: fields[key] });
            handled = true;
          }
        }
        if (fields.consents) {
          form.setError("terms", { message: fields.consents });
          handled = true;
        }
        if (fields.non_field_errors) {
          toast.error(fields.non_field_errors);
          handled = true;
        }
        if (handled) return;
      }
      toast.error(getErrorMessage(error));
    }
  });

  const checkbox = (name: "terms" | "privacy" | "marketing", label: React.ReactNode) => (
    <label className="flex cursor-pointer items-start gap-3 text-base">
      <input type="checkbox" className="mt-1 size-5 shrink-0 accent-teal" {...form.register(name)} />
      <span>{label}</span>
    </label>
  );

  return (
    <AuthCard
      title={t("registerTitle")}
      subtitle={t("registerSubtitle")}
      footer={
        <p>
          {t("haveAccount")}{" "}
          <Link href="/login" className="font-semibold text-teal underline-offset-4 hover:underline">
            {t("login")}
          </Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <Field label={t("displayName")} error={errors.display_name?.message}>
          {(props) => (
            <Input {...props} autoComplete="given-name" placeholder={t("displayNamePlaceholder")} {...form.register("display_name")} />
          )}
        </Field>
        <Field label={t("email")} error={errors.email?.message}>
          {(props) => <Input {...props} type="email" autoComplete="email" inputMode="email" {...form.register("email")} />}
        </Field>
        <Field label={t("password")} hint={t("passwordHint")} error={errors.password?.message}>
          {(props) => <Input {...props} type="password" autoComplete="new-password" {...form.register("password")} />}
        </Field>
        <Field label={t("language")}>
          {() => (
            <Controller
              control={form.control}
              name="preferred_language"
              render={({ field }) => <LanguageToggle name={t("language")} value={field.value} onChange={field.onChange} />}
            />
          )}
        </Field>

        <div className="flex flex-col gap-3 rounded-2xl bg-muted p-4">
          {checkbox(
            "terms",
            t.rich("consentTerms", {
              terms: (chunks) => (
                <Link href="/legal/terms" target="_blank" className="font-semibold text-teal underline">
                  {chunks}
                </Link>
              ),
            }),
          )}
          {checkbox(
            "privacy",
            t.rich("consentPrivacy", {
              privacy: (chunks) => (
                <Link href="/legal/privacy" target="_blank" className="font-semibold text-teal underline">
                  {chunks}
                </Link>
              ),
            }),
          )}
          {checkbox("marketing", t("consentMarketing"))}
          {(errors.terms || errors.privacy) && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {errors.terms?.message ?? errors.privacy?.message}
            </p>
          )}
        </div>

        <Button type="submit" size="xl" className="mt-2 w-full" disabled={isSubmitting}>
          {t("createAccount")}
        </Button>
      </form>
    </AuthCard>
  );
}
