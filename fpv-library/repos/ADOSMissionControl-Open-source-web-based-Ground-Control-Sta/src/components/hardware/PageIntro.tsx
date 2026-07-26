"use client";

/**
 * @module PageIntro
 * @description One-line page-level explainer rendered at the top of every
 * Hardware sub-view. Optional trailing slot for hint chips or actions.
 * @license GPL-3.0-only
 */

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageIntroProps {
  title: string;
  description: string;
  trailing?: ReactNode;
  className?: string;
}

export function PageIntro({ title, description, trailing, className }: PageIntroProps) {
  return (
    <div
      className={cn(
        "mb-5 flex flex-col gap-3 border-b border-border-default pb-4 sm:flex-row sm:items-start sm:justify-between",
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
        <p className="mt-1 text-sm text-text-secondary leading-relaxed">{description}</p>
      </div>
      {trailing ? (
        <div className="flex flex-wrap items-center gap-1.5 sm:pt-1">{trailing}</div>
      ) : null}
    </div>
  );
}
