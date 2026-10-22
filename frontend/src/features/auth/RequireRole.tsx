"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import { homePathFor } from "@/lib/locale";
import { FullScreenLoader } from "@/components/feedback/FullScreenLoader";
import type { Role } from "@/lib/api/types";

interface Props {
  role: Role;
  children: React.ReactNode;
  /** Students who have not finished onboarding are sent there first (except on the onboarding page). */
  requireOnboarding?: boolean;
}

/** Client-side route guard. The server enforces permissions; this only keeps the UX coherent. */
export function RequireRole({ role, children, requireOnboarding = true }: Props) {
  const { status, user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const onboardingPending = role === "student" && requireOnboarding && user?.student && !user.student.onboarding_completed;

  useEffect(() => {
    if (status === "loading") return;
    if (status === "anonymous" || !user) {
      router.replace(`/?next=${encodeURIComponent(pathname)}`);
      return;
    }
    if (user.role !== role) {
      router.replace(homePathFor(user.role, user.student?.onboarding_completed));
      return;
    }
    if (onboardingPending && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [status, user, role, router, pathname, onboardingPending]);

  if (status !== "authenticated" || !user || user.role !== role || (onboardingPending && pathname !== "/onboarding")) {
    return <FullScreenLoader />;
  }
  return <>{children}</>;
}
