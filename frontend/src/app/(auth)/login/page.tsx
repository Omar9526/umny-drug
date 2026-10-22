"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/forms/Field";
import { AuthCard } from "@/components/layout/AuthCard";
import { authApi } from "@/features/auth/api";
import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, getErrorMessage } from "@/lib/api/client";
import { homePathFor } from "@/lib/locale";

export default function LoginPage() {
  const t = useTranslations("auth");
  const te = useTranslations("errors");
  const router = useRouter();
  const { setSession } = useAuth();

  const schema = z.object({
    email: z.email(te("email")),
    password: z.string().min(1, te("required")),
  });
  type FormValues = z.infer<typeof schema>;

  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const result = await authApi.login(values.email, values.password);
      setSession(result.access, result.user);
      router.replace(homePathFor(result.user.role, result.user.student?.onboarding_completed));
    } catch (error) {
      if (error instanceof ApiError) {
        const fields = error.fieldErrors();
        const message = fields.non_field_errors ?? error.message;
        form.setError("password", { message });
        return;
      }
      toast.error(getErrorMessage(error));
    }
  });

  return (
    <AuthCard
      title={t("loginTitle")}
      subtitle={t("loginSubtitle")}
      footer={
        <div className="flex flex-col gap-2">
          <p>
            {t("noAccount")}{" "}
            <Link href="/register" className="font-semibold text-teal underline-offset-4 hover:underline">
              {t("register")}
            </Link>
          </p>
          <Link href="/child-login" className="font-semibold text-teal underline-offset-4 hover:underline">
            {t("childEntrance")}
          </Link>
        </div>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <Field label={t("email")} error={form.formState.errors.email?.message}>
          {(props) => <Input {...props} type="email" autoComplete="email" inputMode="email" {...form.register("email")} />}
        </Field>
        <Field label={t("password")} error={form.formState.errors.password?.message}>
          {(props) => <Input {...props} type="password" autoComplete="current-password" {...form.register("password")} />}
        </Field>
        <Button type="submit" size="xl" className="mt-2 w-full" disabled={form.formState.isSubmitting}>
          {t("login")}
        </Button>
      </form>
    </AuthCard>
  );
}
