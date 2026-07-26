import { DataSection } from "@/components/config/DataSection";

export default function DataPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-xl">
        <DataSection />
      </div>
    </div>
  );
}
