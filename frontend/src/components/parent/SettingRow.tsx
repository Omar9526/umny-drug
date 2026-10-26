import type { ReactNode } from "react";
import { Switch } from "@/components/ui/switch";

/** A labelled switch row for the family settings screen. */
export function SettingRow({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint?: ReactNode;
  checked: boolean;
  disabled?: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-4 py-3">
      <span className="min-w-0 flex-1">
        <span className="block text-base font-semibold">{label}</span>
        {hint && <span className="block text-sm text-muted-foreground">{hint}</span>}
      </span>
      <Switch checked={checked} disabled={disabled} onCheckedChange={(value) => onChange(Boolean(value))} />
    </label>
  );
}
