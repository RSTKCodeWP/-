"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  padding?: boolean;
  className?: string;
  children: ReactNode;
  onClick?: () => void;
}

export function Card({ title, padding = true, className, children, onClick }: CardProps) {
  return (
    <div
      className={cn(
        "bg-bg-secondary border border-border-default",
        onClick && "cursor-pointer hover:border-border-strong transition-colors",
        className
      )}
      onClick={onClick}
    >
      {title && (
        <div className="px-3 py-2 border-b border-border-default">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">{title}</h3>
        </div>
      )}
      <div className={cn(padding && "p-3")}>{children}</div>
    </div>
  );
}
