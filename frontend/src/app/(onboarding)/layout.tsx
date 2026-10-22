import { RequireRole } from "@/features/auth/RequireRole";

/** Onboarding runs before the student shell: no tab bar until the child has set language and grade. */
export default function OnboardingLayout({ children }: LayoutProps<"/">) {
  return (
    <RequireRole role="student" requireOnboarding={false}>
      <main className="mx-auto w-full max-w-md px-4 py-6">{children}</main>
    </RequireRole>
  );
}
