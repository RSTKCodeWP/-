import { NotificationsSection } from "@/components/config/NotificationsSection";

export default function NotificationsPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-xl">
        <NotificationsSection />
      </div>
    </div>
  );
}
