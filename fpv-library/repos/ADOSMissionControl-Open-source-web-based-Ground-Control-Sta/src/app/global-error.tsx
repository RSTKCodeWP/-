/**
 * @module GlobalError
 * @description Last-resort error boundary for root layout errors (Next.js App Router).
 * Must provide its own <html> + <body> since the root layout may have failed.
 * @license GPL-3.0-only
 */

"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[global-error-boundary]", error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ margin: 0, backgroundColor: "#0A0A0F", color: "#E0E0E0", fontFamily: "system-ui, sans-serif" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", padding: "2rem" }}>
          <div style={{ maxWidth: "28rem", width: "100%", textAlign: "center" }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>⚠</div>
            <h2 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "0.5rem" }}>
              Something went wrong
            </h2>
            <p style={{ fontSize: "0.875rem", color: "#888", marginBottom: "1.5rem" }}>
              {error.message || "An unexpected error occurred."}
            </p>
            <button
              onClick={reset}
              style={{
                padding: "0.5rem 1rem",
                fontSize: "0.875rem",
                fontWeight: 500,
                backgroundColor: "#3A82FF",
                color: "#0A0A0F",
                border: "none",
                borderRadius: "0.375rem",
                cursor: "pointer",
              }}
            >
              Try Again
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
