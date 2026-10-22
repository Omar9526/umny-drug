"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { motion } from "motion/react";
import { Camera, History, Home, LayoutGrid, UserRound } from "lucide-react";
import { Logo } from "@/components/brand/Logo";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/home", key: "home", icon: Home },
  { href: "/subjects", key: "subjects", icon: LayoutGrid },
  { href: "/assignments/new", key: "photo", icon: Camera, primary: true },
  { href: "/history", key: "history", icon: History },
  { href: "/profile", key: "profile", icon: UserRound },
] as const;

/**
 * Student shell: a phone-width column with a floating dark-teal pill bar on small screens
 * (the active tab slides into a white pill with its label) and a left rail on desktop.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const t = useTranslations("nav");

  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 md:gap-8 md:px-6 md:py-6">
      <aside className="sticky top-6 hidden h-[calc(100dvh-3rem)] w-60 shrink-0 flex-col rounded-3xl bg-white p-4 shadow-card md:flex">
        <Logo className="px-2 py-2" />
        <nav className="mt-6 flex flex-col gap-1" aria-label="Основная навигация">
          {NAV.map(({ href, key, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href) ? "page" : undefined}
              className={cn(
                "flex h-12 items-center gap-3 rounded-2xl px-3 text-base font-semibold transition-colors",
                isActive(href) ? "bg-teal text-white" : "text-foreground/80 hover:bg-lime-pale",
              )}
            >
              <Icon className="size-5" />
              {t(key)}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-32 md:px-0 md:pb-8">{children}</main>
      </div>

      <nav
        aria-label="Основная навигация"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-[max(env(safe-area-inset-bottom),12px)] md:hidden"
      >
        <ul className="pointer-events-auto mx-auto flex max-w-md items-center gap-1 rounded-full bg-teal p-1.5 shadow-float">
          {NAV.map(({ href, key, icon: Icon, ...rest }) => {
            const active = isActive(href);
            const primary = "primary" in rest && rest.primary;
            return (
              <li key={href} className={cn("min-w-0", active ? "flex-1" : "w-12 shrink-0")}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  aria-label={t(key)}
                  className="relative flex h-12 items-center justify-center rounded-full"
                >
                  {active && (
                    <motion.span
                      layoutId="student-nav-pill"
                      className="absolute inset-0 rounded-full bg-white"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                  <span
                    className={cn(
                      "relative flex min-w-0 items-center gap-2 px-2",
                      active ? "text-teal" : "text-white/85",
                    )}
                  >
                    {primary && !active ? (
                      <span className="flex size-9 items-center justify-center rounded-full bg-lime text-teal">
                        <Icon className="size-5" />
                      </span>
                    ) : (
                      <Icon className="size-5" />
                    )}
                    {active && <span className="truncate text-sm font-bold">{t(key)}</span>}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
