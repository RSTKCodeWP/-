/**
 * @module net/fetch-with-timeout
 * @description Abortable fetch wrapper for server-side route handlers.
 *
 * Server-side fetch in Next.js route handlers does not propagate the
 * client's disconnect, so a slow upstream response can keep the request
 * pinned in memory long after the browser has navigated away. Wrap any
 * upstream fetch in fetchWithTimeout so the request is bounded and the
 * caller's AbortSignal (if any) is respected.
 *
 * @license GPL-3.0-only
 */

export interface FetchWithTimeoutOptions extends RequestInit {
  /** Hard upper bound in milliseconds. Default 60_000. */
  timeoutMs?: number;
  /** External abort signal. Combined with the internal timeout. */
  upstreamSignal?: AbortSignal | null;
}

const DEFAULT_TIMEOUT_MS = 60_000;

/**
 * fetch() with a timeout that always cleans up the controller.
 * Throws DOMException("AbortError") when the timeout fires or the
 * upstream signal aborts. Re-throws any underlying network error.
 */
export async function fetchWithTimeout(
  url: string | URL,
  options: FetchWithTimeoutOptions = {},
): Promise<Response> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, upstreamSignal, signal: _ignored, ...rest } = options;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  // If the caller passed their own signal (e.g., NextRequest.signal that
  // tracks the client connection), abort our controller when it fires.
  let upstreamHandler: (() => void) | null = null;
  if (upstreamSignal) {
    if (upstreamSignal.aborted) {
      clearTimeout(timer);
      controller.abort();
    } else {
      upstreamHandler = () => controller.abort();
      upstreamSignal.addEventListener("abort", upstreamHandler, { once: true });
    }
  }

  try {
    return await fetch(url, { ...rest, signal: controller.signal });
  } finally {
    clearTimeout(timer);
    if (upstreamSignal && upstreamHandler) {
      upstreamSignal.removeEventListener("abort", upstreamHandler);
    }
  }
}

export async function readArrayBufferWithLimit(
  response: Response,
  maxBytes: number,
): Promise<ArrayBuffer> {
  const contentLength = response.headers.get("content-length");
  if (contentLength && Number(contentLength) > maxBytes) {
    throw new Error("Upstream response too large");
  }

  if (!response.body) {
    const buffer = await response.arrayBuffer();
    if (buffer.byteLength > maxBytes) {
      throw new Error("Upstream response too large");
    }
    return buffer;
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!value) continue;
      received += value.byteLength;
      if (received > maxBytes) {
        throw new Error("Upstream response too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const out = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out.buffer;
}
