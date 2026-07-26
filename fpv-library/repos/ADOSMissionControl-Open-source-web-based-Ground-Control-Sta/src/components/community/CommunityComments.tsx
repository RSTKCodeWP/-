"use client";

import { useState } from "react";
import { useMutation } from "convex/react";
import { Trash2 } from "lucide-react";
import { communityApi } from "@/lib/community-api";
import { useConvexSkipQuery } from "@/hooks/use-convex-skip-query";
import { useAuthStore } from "@/stores/auth-store";
import { useIsAdmin } from "@/hooks/use-is-admin";
import { formatDate } from "@/lib/utils";
import { AuthGate } from "./AuthGate";
import type { CommunityComment } from "@/lib/community-types";

interface CommunityCommentsProps {
  targetType: "community_item" | "changelog";
  targetId: string;
}

export function CommunityComments({ targetType, targetId }: CommunityCommentsProps) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isAdmin = useIsAdmin();
  const comments = useConvexSkipQuery(communityApi.comments.list, {
    args: { targetType, targetId },
    enabled: !!targetId,
  });
  const createComment = useMutation(communityApi.comments.create);
  const removeComment = useMutation(communityApi.comments.remove);
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!body.trim() || submitting) return;
    setSubmitting(true);
    try {
      await createComment({ targetType, targetId, body: body.trim() });
      setBody("");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg.includes("Not authenticated")) {
        console.error("Comment failed: not authenticated");
      } else {
        console.error("Failed to create comment:", err);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = (commentId: string) => {
    removeComment({ id: commentId as never });
  };

  if (comments === undefined) {
    return (
      <div className="py-4 text-sm text-text-tertiary">Loading comments...</div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-text-secondary uppercase tracking-wider">
        Comments ({comments.length})
      </h3>

      {comments.length === 0 && (
        <p className="text-sm text-text-tertiary py-2">No comments yet.</p>
      )}

      <div className="space-y-2">
        {comments.map((comment: CommunityComment) => (
          <div
            key={comment._id}
            className="bg-bg-secondary border border-border-default rounded p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-text-primary">
                  {comment.authorName}
                </span>
                <span className="text-xs text-text-tertiary">
                  {formatDate(comment._creationTime)}
                </span>
              </div>
              {isAdmin && (
                <button
                  onClick={() => handleDelete(comment._id)}
                  className="text-text-tertiary hover:text-status-error transition-colors"
                  title="Delete comment"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
            <p className="text-sm text-text-secondary whitespace-pre-wrap">
              {comment.body}
            </p>
          </div>
        ))}
      </div>

      <AuthGate action="comment">
        {isAuthenticated && (
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Add a comment..."
              maxLength={2000}
              className="flex-1 bg-bg-secondary border border-border-default rounded px-3 py-1.5 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent-primary"
            />
            <button
              type="submit"
              disabled={!body.trim() || submitting}
              className="px-3 py-1.5 text-sm font-medium bg-accent-primary text-bg-primary rounded hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Post
            </button>
          </form>
        )}
      </AuthGate>
    </div>
  );
}
