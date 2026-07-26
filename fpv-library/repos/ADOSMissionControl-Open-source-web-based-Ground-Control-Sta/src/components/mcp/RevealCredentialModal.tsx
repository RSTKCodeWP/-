/**
 * @module components/mcp/RevealCredentialModal
 * @description Shows a freshly minted machine credential EXACTLY ONCE, with the
 * connect recipe and copy buttons. The plaintext is never stored; once this
 * closes it cannot be shown again (only the hash is on the backend).
 * @license GPL-3.0-only
 */

"use client";

import { useState, useRef, useEffect } from "react";
import { Copy, Check } from "lucide-react";
import { useTranslations } from "next-intl";
import { Modal } from "@/components/ui/modal";
import { Button } from "@/components/ui/button";
import { useMcpTabStore } from "@/stores/mcp-tab-store";
import { connectRecipe } from "./mcp-shared";

export function RevealCredentialModal() {
  const revealed = useMcpTabStore((s) => s.revealed);
  const clear = useMcpTabStore((s) => s.clearRevealed);
  const t = useTranslations("mcp");
  const [copied, setCopied] = useState<"cred" | "recipe" | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

  if (!revealed) return null;
  const recipe = connectRecipe(revealed.credential);

  async function copy(what: "cred" | "recipe", text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(what);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied((c) => (c === what ? null : c)), 2000);
    } catch {
      /* clipboard unavailable (insecure context) — the value is still selectable */
    }
  }

  return (
    <Modal
      open
      onClose={clear}
      title={t("reveal.title")}
      size="lg"
      footer={<Button onClick={clear}>{t("reveal.done")}</Button>}
    >
      <div className="flex flex-col gap-4">
        <p className="text-sm text-text-secondary">{t("reveal.body")}</p>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-text-tertiary">{t("reveal.credentialLabel")}</span>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded-md border border-border-default bg-bg-tertiary px-3 py-2 font-mono text-xs text-text-primary">
              {revealed.credential}
            </code>
            <Button
              variant="secondary"
              size="sm"
              icon={copied === "cred" ? <Check size={14} /> : <Copy size={14} />}
              onClick={() => copy("cred", revealed.credential)}
            >
              {copied === "cred" ? t("reveal.copied") : t("reveal.copy")}
            </Button>
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-text-tertiary">{t("reveal.recipeLabel")}</span>
          <div className="flex items-start gap-2">
            <pre className="flex-1 overflow-x-auto rounded-md border border-border-default bg-bg-tertiary px-3 py-2 font-mono text-xs text-text-primary">
              {recipe}
            </pre>
            <Button
              variant="secondary"
              size="sm"
              icon={copied === "recipe" ? <Check size={14} /> : <Copy size={14} />}
              onClick={() => copy("recipe", recipe)}
            >
              {copied === "recipe" ? t("reveal.copied") : t("reveal.copy")}
            </Button>
          </div>
        </div>

        <p className="text-xs text-text-tertiary">{t("selfHostNote")}</p>
        <p className="text-xs text-status-warning">{t("reveal.warning")}</p>
      </div>
    </Modal>
  );
}
