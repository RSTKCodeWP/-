"use client";

/**
 * The unified overview layout primitives shared by every profile's Overview.
 * A 12-column dense bento grid (`OverviewGrid`) of semantic-span tiles
 * (`OverviewTile`), optionally chunked into labelled bands (`OverviewSection`).
 * `grid-auto-flow: dense` backfills gaps so columns never ragged-end.
 *
 * @module OverviewGrid
 * @license GPL-3.0-only
 */

import type { CSSProperties, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function OverviewGrid({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "grid grid-cols-2 gap-3 [grid-auto-flow:dense] auto-rows-[minmax(112px,auto)] xl:grid-cols-12",
        className,
      )}
    >
      {children}
    </div>
  );
}

type Span = "quarter" | "third" | "half" | "full";

const spanCol: Record<Span, string> = {
  quarter: "col-span-2 xl:col-span-3",
  third: "col-span-2 xl:col-span-4",
  half: "col-span-2 xl:col-span-6",
  full: "col-span-2 xl:col-span-12",
};

export function OverviewTile({
  span = "third",
  rowSpan,
  children,
  className,
}: {
  span?: Span;
  rowSpan?: number;
  children: ReactNode;
  className?: string;
}) {
  const style: CSSProperties | undefined = rowSpan
    ? { gridRow: `span ${rowSpan} / span ${rowSpan}` }
    : undefined;
  return (
    <div className={cn(spanCol[span], className)} style={style}>
      {children}
    </div>
  );
}

export function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h3 className="text-[11px] font-semibold uppercase tracking-wider text-text-tertiary">
      {children}
    </h3>
  );
}

export function OverviewSection({
  title,
  children,
  className,
}: {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-2", className)}>
      {title && <SectionHeading>{title}</SectionHeading>}
      <OverviewGrid>{children}</OverviewGrid>
    </section>
  );
}
