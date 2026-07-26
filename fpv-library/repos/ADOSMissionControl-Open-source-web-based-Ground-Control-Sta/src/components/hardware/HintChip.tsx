"use client";

/**
 * @module HintChip
 * @description Inline hint chip used to surface non-obvious behaviour next to
 * a header, button, or input. Keeps copy short. Pair with PageIntro for the
 * page-level explainer.
 * @license GPL-3.0-only
 */

import { Info } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface HintChipProps {
  children: ReactNode;
  className?: string;
}

export function HintChip({ children, className }: HintChipProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full bg-bg-tertiary px-2 py-0.5 text-[11px] text-text-secondary",
        className,
      )}
    >
      <Info size={11} className="text-text-tertiary" />
      {children}
    </span>
  );
}
