#!/usr/bin/env node
/*
 * fpv-sim-mcp — stdio transport entry point.
 *
 * The client (Claude Code, Claude Desktop, MCP Inspector, ...) launches this
 * as a child process and speaks MCP over stdin/stdout. One server instance
 * lives for the life of the process. See http.ts for the remote entry point,
 * and build.ts for the tools and resources themselves.
 */

import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { buildServer, SERVER_VERSION } from "./build.js";

const server = buildServer();
const transport = new StdioServerTransport();
await server.connect(transport);
// stdout carries the MCP protocol; anything human-facing goes to stderr.
console.error(`fpv-sim-mcp ${SERVER_VERSION} ready on stdio (notional data only)`);
