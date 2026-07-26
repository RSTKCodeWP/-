import { VideoSection } from "@/components/config/VideoSection";

export default function VideoPage() {
  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-xl">
        <VideoSection />
      </div>
    </div>
  );
}
