/**
 * @module SilentErrorBoundary
 * @description Reusable React class error boundary that catches render-phase errors,
 * logs a warning, and renders a fallback (defaults to null). Use this to wrap
 * components that call Convex useQuery — which throws synchronously during render
 * when the server returns an error.
 * @license GPL-3.0-only
 */

"use client";

import { Component, type ReactNode } from "react";

interface SilentErrorBoundaryProps {
  children: ReactNode;
  /** Rendered when an error is caught. Defaults to null (render nothing). */
  fallback?: ReactNode;
  /** Called when an error is caught — useful for setting state in a parent. */
  onError?: (error: Error) => void;
  /** Label for the console warning. Defaults to "SilentErrorBoundary". */
  label?: string;
}

interface SilentErrorBoundaryState {
  hasError: boolean;
}

export class SilentErrorBoundary extends Component<
  SilentErrorBoundaryProps,
  SilentErrorBoundaryState
> {
  state: SilentErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): SilentErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    const label = this.props.label ?? "SilentErrorBoundary";
    console.warn(`[${label}] Silently caught error:`, error.message);
    this.props.onError?.(error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? null;
    }
    return this.props.children;
  }
}
