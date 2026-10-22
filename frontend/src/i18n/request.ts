import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

export const LOCALES = ["ru", "ky"] as const;
export type Locale = (typeof LOCALES)[number];
export const LOCALE_COOKIE = "ud_locale";

export default getRequestConfig(async () => {
  const store = await cookies();
  const raw = store.get(LOCALE_COOKIE)?.value;
  const locale: Locale = raw === "ky" ? "ky" : "ru";
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
    timeZone: "Asia/Bishkek",
    now: new Date(),
  };
});
