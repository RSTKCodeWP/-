"use client";

/**
 * @module DisclaimerBody
 * @description Reusable scrollable disclaimer copy. Six sections covering
 * lawful use, military use restriction, aviation regs, export controls,
 * warranty disclaimer, and the open-source license.
 * @license GPL-3.0-only
 */

import { Shield, Swords, Plane, PackageCheck, AlertTriangle, Scale } from "lucide-react";
import { useTranslations } from "next-intl";

export function DisclaimerBody() {
  const t = useTranslations("welcome");

  return (
    <div className="[max-height:60dvh] overflow-y-auto border border-border-default rounded-sm bg-bg-secondary p-4 space-y-4 mb-6 overscroll-contain">
      {/* 1. Lawful Use */}
      <div className="flex gap-3">
        <Shield size={16} className="text-accent-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-text-primary mb-1">{t("disclaimer.lawfulUse.heading")}</h3>
          <p className="text-xs text-text-secondary leading-relaxed">{t("disclaimer.lawfulUse.body")}</p>
        </div>
      </div>

      <div className="border-t border-border-default" />

      {/* 2. No Unauthorized Military Use */}
      <div className="flex gap-3">
        <Swords size={16} className="text-accent-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-text-primary mb-1">{t("disclaimer.militaryUse.heading")}</h3>
          <p className="text-xs text-text-secondary leading-relaxed">{t("disclaimer.militaryUse.body")}</p>
        </div>
      </div>

      <div className="border-t border-border-default" />

      {/* 3. Aviation Regulations */}
      <div className="flex gap-3">
        <Plane size={16} className="text-accent-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-text-primary mb-1">{t("disclaimer.aviationRegs.heading")}</h3>
          <p className="text-xs text-text-secondary leading-relaxed mb-2">{t("disclaimer.aviationRegs.body")}</p>
          <ul className="list-disc list-inside text-xs text-text-secondary leading-relaxed space-y-1 mb-2">
            <li>{t("disclaimer.aviationRegs.item1")}</li>
            <li>{t("disclaimer.aviationRegs.item2")}</li>
            <li>{t("disclaimer.aviationRegs.item3")}</li>
            <li>{t("disclaimer.aviationRegs.item4")}</li>
          </ul>
          <p className="text-xs text-text-primary font-medium">{t("disclaimer.aviationRegs.footer")}</p>
        </div>
      </div>

      <div className="border-t border-border-default" />

      {/* 4. Export Controls */}
      <div className="flex gap-3">
        <PackageCheck size={16} className="text-accent-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-text-primary mb-1">{t("disclaimer.exportControls.heading")}</h3>
          <p className="text-xs text-text-secondary leading-relaxed">{t("disclaimer.exportControls.body")}</p>
        </div>
      </div>

      <div className="border-t border-border-default" />

      {/* 5. No Warranty / Assumption of Risk */}
      <div className="flex gap-3">
        <AlertTriangle size={16} className="text-status-warning shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-text-primary mb-1">{t("disclaimer.noWarranty.heading")}</h3>
          <p className="text-xs text-text-secondary leading-relaxed mb-2">{t("disclaimer.noWarranty.warranty")}</p>
          <p className="text-xs text-text-secondary leading-relaxed">{t("disclaimer.noWarranty.risk")}</p>
        </div>
      </div>

      <div className="border-t border-border-default" />

      {/* 6. Open Source License */}
      <div className="flex gap-3">
        <Scale size={16} className="text-accent-primary shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-text-primary mb-1">{t("disclaimer.openSource.heading")}</h3>
          <p className="text-xs text-text-secondary leading-relaxed mb-1">{t("disclaimer.openSource.body")}</p>
          <a
            href="https://www.gnu.org/licenses/gpl-3.0.html"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-accent-primary hover:underline"
          >
            {t("disclaimer.openSource.link")} →
          </a>
        </div>
      </div>
    </div>
  );
}
