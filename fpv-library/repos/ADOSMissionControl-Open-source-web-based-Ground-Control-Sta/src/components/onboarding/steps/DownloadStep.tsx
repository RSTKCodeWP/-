"use client";

/**
 * @module DownloadStep
 * @description Desktop app download step. Skipped entirely when the modal
 * is rendered inside Electron. Three platform tiles linking to the GitHub
 * latest release.
 * @license GPL-3.0-only
 */

import { Monitor } from "lucide-react";
import { useTranslations } from "next-intl";
import { GITHUB_RELEASES_URL, PRIMARY_CTA_CLASS } from "../constants";
import { StepDots } from "../parts/StepDots";
import { BackButton } from "./BackButton";

interface Props {
  next: () => void;
  back: () => void;
  dotStep: number;
  totalSteps: number;
}

export function DownloadStep({ next, back, dotStep, totalSteps }: Props) {
  const t = useTranslations("welcome");

  return (
    <>
      <BackButton onClick={back} />

      <div className="w-full max-w-xl text-center">
        <Monitor size={32} className="text-accent-primary mx-auto mb-4" />
        <h2 className="text-xl font-display font-semibold text-text-primary mb-2">
          {t("download.title")}
        </h2>
        <p className="text-sm text-text-secondary leading-relaxed mb-8 max-w-md mx-auto">
          {t("download.description")}
        </p>

        {/* Platform boxes */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {/* macOS */}
          <div className="border border-border-default bg-bg-secondary rounded-lg p-5 flex flex-col items-center gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="currentColor" className="text-text-primary">
              <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
            </svg>
            <span className="text-sm font-medium text-text-primary">{t("download.macos")}</span>
            <div className="flex flex-col sm:flex-row gap-2 w-full">
              <a
                href={GITHUB_RELEASES_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="h-11 px-4 text-xs font-semibold rounded-sm border border-border-default text-text-secondary hover:text-text-primary hover:border-accent-primary/50 transition-all inline-flex items-center justify-center w-full sm:w-auto"
              >
                {t("download.appleSilicon")}
              </a>
              <a
                href={GITHUB_RELEASES_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="h-11 px-4 text-xs font-semibold rounded-sm border border-border-default text-text-secondary hover:text-text-primary hover:border-accent-primary/50 transition-all inline-flex items-center justify-center w-full sm:w-auto"
              >
                {t("download.intel")}
              </a>
            </div>
          </div>

          {/* Windows */}
          <div className="border border-border-default bg-bg-secondary rounded-lg p-5 flex flex-col items-center gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="currentColor" className="text-text-primary">
              <path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/>
            </svg>
            <span className="text-sm font-medium text-text-primary">{t("download.windows")}</span>
            <a
              href={GITHUB_RELEASES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="h-11 px-4 text-xs font-semibold rounded-sm border border-border-default text-text-secondary hover:text-text-primary hover:border-accent-primary/50 transition-all inline-flex items-center justify-center w-full sm:w-auto"
            >
              {t("download.download")} .exe
            </a>
          </div>

          {/* Linux */}
          <div className="border border-border-default bg-bg-secondary rounded-lg p-5 flex flex-col items-center gap-3">
            <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="currentColor" className="text-text-primary">
              <path d="M12.504 0c-.155 0-.315.008-.48.021-4.226.333-3.105 4.807-3.17 6.298-.076 1.092-.3 1.953-1.05 3.02-.885 1.051-2.127 2.75-2.716 4.521-.278.832-.41 1.684-.287 2.489a.424.424 0 00-.11.135c-.26.268-.45.6-.663.839-.199.199-.485.267-.797.4-.313.136-.658.269-.864.68-.09.189-.136.394-.132.602 0 .199.027.4.055.536.058.399.116.728.04.97-.249.68-.28 1.145-.106 1.484.174.334.535.47.94.601.81.2 1.91.135 2.774.6.926.466 1.866.67 2.616.47.526-.116.97-.464 1.208-.946.587-.003 1.23-.269 2.26-.334.699-.058 1.574.267 2.577.2.025.134.063.198.114.333l.003.003c.391.778 1.113 1.368 1.884 1.43.39.033.77-.396 1.164-.664.29-.2.608-.382.737-.71.264-.68-.12-.862-.21-1.78a2.25 2.25 0 01.037-.994c.082-.272.2-.418.384-.673.156-.21.29-.46.31-.728.015-.212-.057-.42-.14-.6-.085-.18-.176-.355-.269-.54-.185-.365-.206-.6-.112-.89.146-.46.196-.762.086-1.066a.786.786 0 00-.266-.366c-.159-.134-.375-.26-.635-.37-.26-.11-.528-.207-.792-.404-.15-.13-.26-.25-.37-.39-.11-.14-.22-.3-.31-.45-.09-.16-.18-.32-.27-.47-.1-.16-.2-.33-.32-.48l-.03-.04c-.42-.55-.89-1-.89-1.93 0-.88.34-1.96.34-3.27 0-2.78-1.895-5.19-5.22-5.19l-.14.002zm-1.005 17.244c-.003.073 0 .136.013.2l-.01.025c.006.034.011.074.011.115 0 .146-.072.28-.196.37-.124.09-.27.14-.43.14a.61.61 0 01-.38-.12c-.137-.1-.278-.21-.425-.265a1.34 1.34 0 00-.463-.075c-.073 0-.138.007-.2.02-.152-.223-.32-.455-.527-.608-.159-.12-.381-.247-.584-.302-.206-.055-.398-.073-.513-.264-.12-.25-.07-.61.015-.858.063-.185.143-.355.233-.504a.86.86 0 01.065-.112c.03-.04.06-.08.083-.12.122-.14.277-.243.48-.301a.96.96 0 01.284-.033c.148 0 .287.031.432.051a2.65 2.65 0 00.478.025c.278-.013.482-.083.677-.13l.004.001.008-.001c.067-.016.137-.029.218-.036.11-.01.216 0 .32.033.104.034.2.088.28.166.073.071.141.154.2.244.056.086.098.163.128.225.018.04.03.075.046.115a.54.54 0 01.034.138c.014.11-.015.224-.06.32z"/>
            </svg>
            <span className="text-sm font-medium text-text-primary">{t("download.linux")}</span>
            <a
              href={GITHUB_RELEASES_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="h-11 px-4 text-xs font-semibold rounded-sm border border-border-default text-text-secondary hover:text-text-primary hover:border-accent-primary/50 transition-all inline-flex items-center justify-center w-full sm:w-auto"
            >
              {t("download.download")} .AppImage
            </a>
          </div>
        </div>

        <p className="text-[10px] text-text-tertiary mb-4">{t("download.releasesNote")}</p>

        {/* Continue */}
        <button
          type="button"
          onClick={next}
          className={`${PRIMARY_CTA_CLASS} mb-3`}
        >
          {t("download.continue")}
        </button>

        <div>
          <button
            type="button"
            onClick={next}
            className="text-[11px] text-text-tertiary hover:text-text-secondary transition-colors"
          >
            {t("download.skip")}
          </button>
        </div>

        <div className="mt-4">
          <StepDots step={dotStep} total={totalSteps} />
        </div>
      </div>
    </>
  );
}
