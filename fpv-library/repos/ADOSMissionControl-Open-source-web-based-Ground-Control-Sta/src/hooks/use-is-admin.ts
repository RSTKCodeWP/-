"use client";

import { communityApi } from "@/lib/community-api";
import { useAuthStore } from "@/stores/auth-store";
import { useConvexSkipQuery } from "./use-convex-skip-query";

export function useIsAdmin(): boolean {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const profile = useConvexSkipQuery(communityApi.profiles.getMyProfile, {
    enabled: isAuthenticated,
  });
  return profile?.role === "admin";
}
