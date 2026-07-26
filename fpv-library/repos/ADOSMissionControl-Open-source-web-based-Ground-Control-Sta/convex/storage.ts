import { mutation } from "./_generated/server";
import { getAuthUserId } from "@convex-dev/auth/server";

export const generateUploadUrl = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");

    const profile = await ctx.db
      .query("profiles")
      .withIndex("by_userId", (q) => q.eq("userId", userId))
      .first();
    if (!profile || profile.role !== "admin") {
      throw new Error("Admin access required");
    }

    return await ctx.storage.generateUploadUrl();
  },
});

// There is intentionally no generic `getUrl(storageId)` resolver here.
// A query that mints a signed download URL for any storage id to any
// authenticated user is a more-permissive resolver than the audience the
// blobs belong to (on a shared deployment a generic resolver could hand out
// another tenant's blob to anyone who can guess a storage id). Every blob
// download instead flows through a dedicated resolver that re-checks
// ownership against the owning row before calling ctx.storage.getUrl:
// cmdLogdWindows.getLogdWindow, cmdPluginArchives, cmdPluginInstallJobs.
