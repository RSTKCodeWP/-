"use client";

import { Star } from "lucide-react";
import { useSettingsStore } from "@/stores/settings-store";
import { cn } from "@/lib/utils";

/**
 * Small star icon that toggles a parameter as favorite.
 * Reusable across specialized FC panels (FailsafePanel, PowerPanel, etc.)
 * to match the ParameterGrid star behavior.
 */
export function ParamStar({ name }: { name: string }) {
  const toggleFavorite = useSettingsStore((s) => s.toggleFavorite);
  const isFav = useSettingsStore((s) => s.favoriteParams.includes(name));

  return (
    <button
      onClick={() => toggleFavorite(name)}
      className={cn(
        "flex-shrink-0 p-0.5 transition-colors cursor-pointer",
        isFav ? "text-status-warning" : "text-text-tertiary hover:text-text-secondary"
      )}
      title={isFav ? `Unfavorite ${name}` : `Favorite ${name}`}
    >
      <Star size={10} fill={isFav ? "currentColor" : "none"} />
    </button>
  );
}

/**
 * Wraps a param control with a star icon aligned to the top-right.
 * Use around Select/Input components to add favorite toggling.
 */
export function StarredParam({ param, children }: { param: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-1 items-start">
      <div className="flex-1 min-w-0">{children}</div>
      <div className="pt-0.5">
        <ParamStar name={param} />
      </div>
    </div>
  );
}
