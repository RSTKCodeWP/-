import { ThemeSection } from "@/components/config/ThemeSection";

export default function ThemePage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-xl">
        <ThemeSection />
      </div>
    </div>
  );
}
