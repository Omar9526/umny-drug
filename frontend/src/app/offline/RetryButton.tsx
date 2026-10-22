"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function RetryButton({ label }: { label: string }) {
  return (
    <Button size="xl" className="mt-6 w-full" onClick={() => window.location.reload()}>
      <RefreshCw /> {label}
    </Button>
  );
}
