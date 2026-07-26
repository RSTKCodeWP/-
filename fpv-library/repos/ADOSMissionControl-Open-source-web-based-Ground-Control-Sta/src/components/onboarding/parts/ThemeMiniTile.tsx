/**
 * Compact theme card shown in the secondary row of the theme picker.
 *
 * @license GPL-3.0-only
 */

"use client";

import { useTranslations } from "next-intl";
import { useSettingsStore } from "@/stores/settings-store";
import { ACCENT_COLORS, type ThemeCardData } from "../constants";

interface ThemeMiniTileProps {
  theme: ThemeCardData;
  onClick: () => void;
}

export function ThemeMiniTile({ theme, onClick }: ThemeMiniTileProps) {
  const t = useTranslations("welcome.theme");
  const { colors, label } = theme;
  const accentColor = useSettingsStore((s) => s.accentColor);
  const accentHex = ACCENT_COLORS.find((c) => c.value === accentColor)?.hex ?? colors.accent;

  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-md border p-2 text-left transition-all hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-primary focus-visible:ring-offset-1"
      style={{
        backgroundColor: colors.bg,
        borderColor: colors.border,
        boxShadow: `0 0 0 1px ${colors.border}, 0 0 0 2px ${accentHex}22`,
      }}
      aria-label={t("useAsPreviewAria", { name: label })}
    >
      <div className="flex items-center gap-1 mb-1.5">
        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: accentHex }} />
        <span className="w-4 h-1 rounded-full opacity-60" style={{ backgroundColor: colors.text }} />
      </div>
      <div className="h-0.5 rounded-full mb-1.5" style={{ backgroundColor: accentHex }} />
      <span className="block text-[10px] leading-tight truncate" style={{ color: colors.text }}>
        {label}
      </span>
    </button>
  );
}
