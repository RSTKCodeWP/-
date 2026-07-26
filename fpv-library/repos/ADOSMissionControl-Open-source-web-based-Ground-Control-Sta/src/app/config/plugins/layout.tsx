"use client";

import Link from "next/link";

// Plugins are discovered and installed per drone from the dashboard Plugins
// tab (the Convex-served registry grid). This section lists the plugins the
// operator has installed.
const INSTALLED_HREF = "/config/plugins";

export default function PluginsSectionLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border-default bg-bg-tertiary/40 px-4">
        <nav className="flex gap-1" aria-label="Plugins section navigation">
          <Link
            href={INSTALLED_HREF}
            className="border-b-2 border-accent-primary px-3 py-2 text-sm text-text-primary"
          >
            Installed
          </Link>
        </nav>
      </div>
      <div className="flex-1 overflow-auto">{children}</div>
    </div>
  );
}
