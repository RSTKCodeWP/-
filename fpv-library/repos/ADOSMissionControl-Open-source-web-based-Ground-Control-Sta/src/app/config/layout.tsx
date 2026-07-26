import { ConfigNav } from "@/components/config/ConfigNav";

export default function ConfigLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex-1 flex h-full overflow-hidden">
      <ConfigNav />
      <div className="flex-1 flex flex-col overflow-hidden">
        {children}
      </div>
    </div>
  );
}
