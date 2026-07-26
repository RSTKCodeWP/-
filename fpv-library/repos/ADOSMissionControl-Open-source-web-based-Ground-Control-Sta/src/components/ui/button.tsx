"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";
import type { ReactNode, ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  loading?: boolean;
}

const variantStyles: Record<string, string> = {
  primary: "bg-accent-primary text-white hover:bg-accent-primary-hover",
  secondary: "bg-bg-tertiary text-text-primary border border-border-default hover:border-border-strong",
  ghost: "text-text-secondary hover:text-text-primary hover:bg-bg-tertiary",
  danger: "bg-status-error/20 text-status-error border border-status-error/30 hover:bg-status-error/30",
};

const sizeStyles: Record<string, string> = {
  sm: "h-7 px-2.5 text-xs gap-1.5",
  md: "h-8 px-3 text-xs gap-2",
  lg: "h-10 px-4 text-sm gap-2",
};

export function Button({
  variant = "primary",
  size = "md",
  icon,
  loading,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center font-medium transition-colors cursor-pointer",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}
