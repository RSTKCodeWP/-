"use client";

import { cn } from "@/lib/utils";

interface ToggleProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  className?: string;
}

export function Toggle({ label, checked, onChange, disabled, className }: ToggleProps) {
  return (
    <label className={cn("flex items-center justify-between gap-2", disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer", className)}>
      <span className="text-xs text-text-secondary">{label}</span>
      <button
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => { if (!disabled) onChange(!checked) }}
        className={cn(
          "relative w-8 h-4 border transition-colors",
          disabled ? "opacity-50 cursor-not-allowed" : "",
          checked ? "bg-accent-primary border-accent-primary" : "bg-bg-tertiary border-border-default"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 w-2.5 h-2.5 bg-white transition-transform",
            checked ? "left-[14px]" : "left-0.5"
          )}
        />
      </button>
    </label>
  );
}
