/**
 * @module lib/net/fetch-with-progress
 * @description Fetch a binary artifact into an `ArrayBuffer` while reporting
 * byte-accurate download progress. Streams the response body chunk by chunk
 * (`response.body.getReader()`), deriving the total from `Content-Length` so a
 * caller can render a determinate progress bar; when the header is absent it
 * still reports received bytes and leaves `percent` null (indeterminate). The
 * reusable form of the loop previously embedded only in the firmware-flash hook.
 * @license GPL-3.0-only
 */

/** A download-progress sample. `percent`/`totalBytes` are null when the server
 * sends no `Content-Length` (chunked transfer). */
export interface FetchProgress {
  receivedBytes: number;
  totalBytes: number | null;
  percent: number | null;
}

export interface FetchWithProgressOptions {
  /** Abort the download (e.g. on unmount / url change). */
  signal?: AbortSignal;
  /** Called on every chunk with the running byte + percent totals. */
  onProgress?: (progress: FetchProgress) => void;
}

/**
 * Fetch `url` into an `ArrayBuffer`, invoking `onProgress` as bytes arrive.
 * Throws on a non-2xx response or an aborted signal.
 */
export async function fetchArrayBufferWithProgress(
  url: string,
  { signal, onProgress }: FetchWithProgressOptions = {},
): Promise<ArrayBuffer> {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`fetch ${res.status}`);

  const header = res.headers.get("Content-Length");
  const parsed = header ? Number(header) : NaN;
  const totalBytes =
    Number.isFinite(parsed) && parsed > 0 ? parsed : null;

  const reader = res.body?.getReader();
  if (!reader) {
    // No streaming body (opaque response / older runtime): single read.
    const buffer = await res.arrayBuffer();
    onProgress?.({
      receivedBytes: buffer.byteLength,
      totalBytes,
      percent: totalBytes ? 100 : null,
    });
    return buffer;
  }

  const chunks: Uint8Array[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    if (!value) continue;
    chunks.push(value);
    received += value.byteLength;
    onProgress?.({
      receivedBytes: received,
      totalBytes,
      percent: totalBytes ? Math.min(100, (received / totalBytes) * 100) : null,
    });
  }

  // Concatenate the chunks into one contiguous buffer.
  const out = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    out.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return out.buffer;
}
