"use client";

import { cn } from "@/lib/utils";
import type { InputHTMLAttributes, ReactNode } from "react";

interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: ReactNode;
  error?: string;
  unit?: string;
}

export function Input({ label, error, unit, className, id, ...props }: InputProps) {
  const inputId = id || (typeof label === "string" ? label.toLowerCase().replace(/\s+/g, "-") : undefined);
  return (
    <div className="flex flex-col gap-1">
      {label && (
        <label htmlFor={inputId} className="text-xs text-text-secondary">
          {label}
        </label>
      )}
      <div className="relative">
        <input
          id={inputId}
          className={cn(
            "w-full h-8 px-2 bg-bg-tertiary border text-sm font-mono text-text-primary placeholder:text-text-tertiary",
            "focus:outline-none focus:border-accent-primary transition-colors",
            error ? "border-status-error" : "border-border-default",
            unit && "pr-8",
            className
          )}
          {...props}
        />
        {unit && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-text-tertiary font-mono">
            {unit}
          </span>
        )}
      </div>
      {error && <span className="text-[10px] text-status-error">{error}</span>}
    </div>
  );
}
