import { GeneralSection } from "@/components/config/GeneralSection";
import { LanguageSection } from "@/components/config/LanguageSection";
import { PluginSettingsSection } from "@/components/config/PluginSettingsSection";

export default function ConfigurationPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-xl space-y-6">
        <GeneralSection />
        <LanguageSection />
        {/* Fleet settings.section slot — a GCS-level plugin's settings iframe
            renders here. Inert until a plugin contributes. */}
        <PluginSettingsSection />
      </div>
    </div>
  );
}
