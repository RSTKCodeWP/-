"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";
import { LayoutDashboard, Route, Play, History, Bot } from "lucide-react";
import { usePlanLibraryStore } from "@/stores/plan-library-store";
import { cn } from "@/lib/utils";

// Agent management is unified into the Dashboard drone view; there is no
// separate Command tab. /command redirects to the Dashboard for old links.
const tabs = [
  { icon: LayoutDashboard, labelKey: "dashboard", href: "/" },
  { icon: Route, labelKey: "plan", href: "/plan" },
  { icon: Play, labelKey: "simulate", href: "/simulate" },
  { icon: History, labelKey: "history", href: "/flight-logs" },
  { icon: Bot, labelKey: "mcp", href: "/mcp" },
];

export function CommandNav() {
  const pathname = usePathname();
  const t = useTranslations("nav");
  // Surface unsaved planner changes on the Plan tab so the cue is visible from
  // any view, not just the planner panel.
  const planDirty = usePlanLibraryStore((s) => s.isDirty);

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <nav className="flex items-stretch gap-1 h-full">
      {tabs.map(({ icon: Icon, labelKey, href }) => {
        const active = isActive(href);
        const showDirty = href === "/plan" && planDirty;
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-1.5 px-3 text-xs font-medium transition-colors -mb-px border-b-2",
              active
                ? "text-accent-primary border-accent-primary"
                : "text-text-secondary hover:text-text-primary border-transparent"
            )}
          >
            <Icon size={14} />
            {t(labelKey)}
            {showDirty && (
              <span className="w-1.5 h-1.5 rounded-full bg-status-warning shrink-0" title={t("unsaved")} />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
