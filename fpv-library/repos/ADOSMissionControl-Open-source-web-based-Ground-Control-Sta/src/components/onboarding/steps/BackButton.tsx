"use client";

/**
 * @module BackButton
 * @description Shared top-left back arrow used by every onboarding step
 * after the language picker.
 * @license GPL-3.0-only
 */

import { useTranslations } from "next-intl";

export function BackButton({ onClick }: { onClick: () => void }) {
  const tCommon = useTranslations("common");
  return (
    <button
      type="button"
      onClick={onClick}
      className="absolute top-3 left-3 sm:top-6 sm:left-6 min-h-11 px-2 -ml-1 text-sm text-text-tertiary hover:text-text-primary transition-colors flex items-center gap-1 z-10"
    >
      ← {tCommon("back")}
    </button>
  );
}
