"use client";

import { use } from "react";
import { ChangelogDetail } from "@/components/community/ChangelogDetail";

export default function ChangelogDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <ChangelogDetail id={id} />;
}
