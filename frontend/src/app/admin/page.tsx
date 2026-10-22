"use client";

import { ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthCard } from "@/components/layout/AuthCard";
import { RequireRole } from "@/features/auth/RequireRole";
import { API_URL } from "@/lib/api/client";

/** Administrators manage the catalogue, AI settings and quality queue in the Django admin. */
export default function AdminPage() {
  return (
    <RequireRole role="admin">
      <AuthCard title="Панель администратора" subtitle="Каталог предметов, темы, пользователи, контроль качества AI.">
        <Button size="lg" className="w-full" render={<a href={`${API_URL}/admin/`} rel="noopener" />}>
          Открыть панель <ExternalLink />
        </Button>
      </AuthCard>
    </RequireRole>
  );
}
