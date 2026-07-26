// HTTP request context, error class, and shared fetch helper for ground station API modules.

export class GroundStationApiError extends Error {
  public readonly status: number;
  public readonly body: string;

  constructor(status: number, body: string, message?: string) {
    super(message ?? `Ground station API ${status}: ${body}`);
    this.status = status;
    this.body = body;
    this.name = "GroundStationApiError";
  }
}

export interface RequestContext {
  baseUrl: string;
  apiKey: string | null;
}

export async function gsRequest<T>(
  ctx: RequestContext,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
  };
  if (ctx.apiKey) {
    headers["X-ADOS-Key"] = ctx.apiKey;
  }
  const res = await fetch(`${ctx.baseUrl}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text().catch(() => "Unknown error");
    throw new GroundStationApiError(res.status, text);
  }
  return res.json() as Promise<T>;
}
