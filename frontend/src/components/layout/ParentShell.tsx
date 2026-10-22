"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { motion } from "motion/react";
import { Bell, Home, LogOut, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/brand/Logo";
import { useAuth } from "@/features/auth/AuthProvider";
import { useOverview } from "@/features/parent/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/parent", key: "parentHome", icon: Home },
  { href: "/parent/notifications", key: "notifications", icon: Bell },
  { href: "/parent/settings", key: "family", icon: Settings },
] as const;

/**
 * Parent shell: the same visual language as the student app — a floating dark-teal pill bar on
 * phones (active tab slides into a white pill with its label) and a left rail on desktop — plus an
 * unread-notifications badge.
 */
export function ParentShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("nav");
  const ta = useTranslations("app");
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const overview = useOverview();
  const unread = overview.data?.unread_notifications ?? 0;

  const isActive = (href: string) =>
    href === "/parent"
      ? pathname === "/parent" || pathname.startsWith("/parent/children")
      : pathname === href || pathname.startsWith(`${href}/`);

  async function onLogout() {
    await logout();
    router.replace("/");
  }

  function Badge({ className }: { className?: string }) {
    if (unread === 0) return null;
    return (
      <span
        aria-label={`${unread}`}
        className={cn(
          "absolute flex min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[11px] leading-5 font-bold text-white ring-2 ring-teal",
          className,
        )}
      >
        {unread > 9 ? "9+" : unread}
      </span>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 md:gap-8 md:px-6 md:py-6">
      <aside className="sticky top-6 hidden h-[calc(100dvh-3rem)] w-60 shrink-0 flex-col rounded-3xl bg-white p-4 shadow-card md:flex">
        <Logo className="px-2 py-2" />
        <nav className="mt-6 flex flex-col gap-1" aria-label={t("parentMenu")}>
          {NAV.map(({ href, key, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={isActive(href) ? "page" : undefined}
              className={cn(
                "relative flex h-12 items-center gap-3 rounded-2xl px-3 text-base font-semibold transition-colors",
                isActive(href) ? "bg-teal text-white" : "text-foreground/80 hover:bg-lime-pale",
              )}
            >
              <Icon className="size-5" />
              {t(key)}
              {key === "notifications" && <Badge className="right-3 ring-white" />}
            </Link>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-2 px-1">
          <p className="truncate text-sm font-semibold text-muted-foreground">{user?.display_name}</p>
          <Button variant="ghost" size="sm" className="justify-start" onClick={onLogout}>
            <LogOut /> {ta("logout")}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-2xl flex-1 px-4 pt-4 pb-32 md:px-0 md:pb-8">{children}</main>
      </div>

      <nav
        aria-label={t("parentMenu")}
        className="pointer-events-none fixed inset-x-0 bottom-0 z-40 px-4 pb-[max(env(safe-area-inset-bottom),12px)] md:hidden"
      >
        <ul className="pointer-events-auto mx-auto flex max-w-md items-center gap-1 rounded-full bg-teal p-1.5 shadow-float">
          {NAV.map(({ href, key, icon: Icon }) => {
            const active = isActive(href);
            return (
              <li key={href} className={cn("min-w-0", active ? "flex-1" : "w-16 shrink-0")}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  aria-label={t(key)}
                  className="relative flex h-12 items-center justify-center rounded-full"
                >
                  {active && (
                    <motion.span
                      layoutId="parent-nav-pill"
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
                    <span className="relative">
                      <Icon className="size-5" />
                      {key === "notifications" && <Badge className="-top-2 -right-3" />}
                    </span>
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
