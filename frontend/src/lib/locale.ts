import type { Language } from "@/lib/api/types";

export const LOCALE_COOKIE = "ud_locale";

/** Persist the interface language for the server-side next-intl config, then reload the tree. */
export function setLocaleCookie(locale: Language): void {
  const oneYear = 60 * 60 * 24 * 365;
  document.cookie = `${LOCALE_COOKIE}=${locale}; path=/; max-age=${oneYear}; SameSite=Lax`;
}

export function homePathFor(role: string, onboardingCompleted?: boolean): string {
  if (role === "student") return onboardingCompleted ? "/home" : "/onboarding";
  if (role === "parent") return "/parent";
  if (role === "admin") return "/admin";
  return "/";
}
