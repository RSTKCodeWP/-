"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface BadgeProps {
  variant?: "success" | "warning" | "serious" | "error" | "info" | "neutral";
  size?: "sm" | "md";
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<string, string> = {
  success: "bg-status-success/20 text-status-success",
  warning: "bg-status-warning/20 text-status-warning",
  serious: "bg-status-serious/20 text-status-serious",
  error: "bg-status-error/20 text-status-error",
  info: "bg-accent-primary/20 text-accent-primary",
  neutral: "bg-bg-tertiary text-text-secondary",
};

const sizeStyles: Record<string, string> = {
  sm: "px-1.5 py-0.5 text-[10px]",
  md: "px-2 py-0.5 text-xs",
};

export function Badge({ variant = "neutral", size = "sm", children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center font-semibold uppercase tracking-wider",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {children}
    </span>
  );
}
