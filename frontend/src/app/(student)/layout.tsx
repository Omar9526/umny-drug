import { RequireRole } from "@/features/auth/RequireRole";
import { AppShell } from "@/components/layout/AppShell";

export default function StudentLayout({ children }: LayoutProps<"/">) {
  return (
    <RequireRole role="student">
      <AppShell>{children}</AppShell>
    </RequireRole>
  );
}
