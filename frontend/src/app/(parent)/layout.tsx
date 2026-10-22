import { RequireRole } from "@/features/auth/RequireRole";
import { ParentShell } from "@/components/layout/ParentShell";

export default function ParentLayout({ children }: LayoutProps<"/">) {
  return (
    <RequireRole role="parent">
      <ParentShell>{children}</ParentShell>
    </RequireRole>
  );
}
