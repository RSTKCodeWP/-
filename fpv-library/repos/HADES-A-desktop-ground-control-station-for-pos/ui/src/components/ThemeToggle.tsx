import { Moon, Sun } from "lucide-react";

import { useThemeStore, type Theme } from "../store/theme";

/* Day/Night theme toggle (DESIGN-SYSTEM §2.5). A two-segment instrument switch, not an OS-style
 * toggle — it names the modes (DAY / NIGHT) so an operator knows exactly which palette is live.
 * The active segment carries the steel accent (the one selection language, §11.1). */

const OPTIONS: { value: Theme; label: string; Icon: typeof Sun }[] = [
  { value: "day", label: "DAY", Icon: Sun },
  { value: "night", label: "NIGHT", Icon: Moon },
];

export function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);

  return (
    <div
      role="radiogroup"
      aria-label="Console theme"
      data-testid="theme-toggle"
      className="inline-flex overflow-hidden rounded-sm border border-hairline"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            data-testid={`theme-${value}`}
            onClick={() => setTheme(value)}
            className={`flex items-center gap-1.5 px-3 py-1.5 font-mono text-2xs font-medium outline-none transition-colors duration-micro focus-visible:shadow-focus ${
              active ? "bg-surface-3 text-text-hi" : "bg-surface-1 text-text-lo hover:bg-surface-2 hover:text-text-mid"
            }`}
          >
            <Icon size={12} aria-hidden /> {label}
          </button>
        );
      })}
    </div>
  );
}
