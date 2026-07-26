#!/usr/bin/env node
/*
 * fpv-sim-mcp — Streamable HTTP transport entry point (remote hosting).
 *
 * Serves MCP over HTTP at POST /mcp, in stateless mode: every request gets a
 * fresh server + transport pair, then both are torn down when the response
 * closes. That is safe here because every tool call is self-contained (seed +
 * config in, deterministic result out) — there is no session state to lose —
 * and it means the process needs no session bookkeeping, survives client
 * disconnects trivially, and could be load-balanced without affinity.
 *
 * Auth is a static bearer token, deliberately simple: this server exposes
 * CPU, not data (everything it returns is notional), so the threat model is
 * resource abuse. Set MCP_AUTH_TOKEN and send "Authorization: Bearer <token>".
 * To run open (e.g. behind some other gate), set MCP_NO_AUTH=1 explicitly —
 * refusing to default to unauthenticated is the point.
 *
 * Environment:
 *   MCP_AUTH_TOKEN  shared secret for the Authorization header
 *   MCP_NO_AUTH=1   explicit opt-out of auth (mutually exclusive with token)
 *   PORT            listen port (default 8080)
 *   HOST            bind address (default 127.0.0.1 — put a TLS-terminating
 *                   reverse proxy in front; do not expose plain HTTP publicly)
 */

import http from "node:http";
import { timingSafeEqual } from "node:crypto";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { buildServer, SERVER_VERSION } from "./build.js";

const PORT = Number(process.env.PORT ?? 8080);
const HOST = process.env.HOST ?? "127.0.0.1";
const TOKEN = process.env.MCP_AUTH_TOKEN;
const NO_AUTH = process.env.MCP_NO_AUTH === "1";
const BODY_LIMIT_BYTES = 1024 * 1024;

if (!TOKEN && !NO_AUTH) {
  console.error(
    "fpv-sim-mcp http: refusing to start without auth.\n" +
    "Set MCP_AUTH_TOKEN=<secret>, or set MCP_NO_AUTH=1 to run open on purpose.",
  );
  process.exit(1);
}
if (TOKEN && NO_AUTH) {
  console.error("fpv-sim-mcp http: MCP_AUTH_TOKEN and MCP_NO_AUTH=1 are mutually exclusive.");
  process.exit(1);
}

function authorized(req: http.IncomingMessage): boolean {
  if (NO_AUTH) return true;
  const header = req.headers.authorization ?? "";
  const expected = `Bearer ${TOKEN}`;
  // Constant-time comparison; length check first because timingSafeEqual throws on mismatch.
  const a = Buffer.from(header);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

function sendJson(res: http.ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(text);
}

function jsonRpcError(res: http.ServerResponse, status: number, code: number, message: string): void {
  sendJson(res, status, { jsonrpc: "2.0", error: { code, message }, id: null });
}

function readBody(req: http.IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let size = 0;
    const chunks: Buffer[] = [];
    req.on("data", (chunk: Buffer) => {
      size += chunk.length;
      if (size > BODY_LIMIT_BYTES) {
        reject(new Error("body too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

const httpServer = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://${req.headers.host ?? "localhost"}`);

  if (req.method === "GET" && url.pathname === "/healthz") {
    sendJson(res, 200, { ok: true, name: "fpv-sim-mcp", version: SERVER_VERSION });
    return;
  }

  if (url.pathname !== "/mcp") {
    sendJson(res, 404, { error: "not found; MCP endpoint is POST /mcp" });
    return;
  }

  if (!authorized(req)) {
    jsonRpcError(res, 401, -32000, "Unauthorized: missing or invalid bearer token.");
    return;
  }

  // Stateless mode: sessions are not used, so the GET notification stream and
  // DELETE session teardown have nothing to attach to.
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    jsonRpcError(res, 405, -32000, "Method not allowed: stateless server, use POST.");
    return;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(await readBody(req));
  } catch {
    jsonRpcError(res, 400, -32700, "Parse error: body must be JSON.");
    return;
  }

  const server = buildServer();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined, // stateless
  });
  res.on("close", () => {
    void transport.close();
    void server.close();
  });

  try {
    await server.connect(transport);
    await transport.handleRequest(req, res, parsed);
  } catch (err) {
    console.error("fpv-sim-mcp http: request failed:", err);
    if (!res.headersSent) {
      jsonRpcError(res, 500, -32603, "Internal server error.");
    }
  }
});

httpServer.listen(PORT, HOST, () => {
  console.error(
    `fpv-sim-mcp ${SERVER_VERSION} ready on http://${HOST}:${PORT}/mcp ` +
    `(${NO_AUTH ? "NO AUTH — deliberate" : "bearer auth"}; notional data only)`,
  );
});
