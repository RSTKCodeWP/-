# Deploying fpv-sim-mcp as a remote MCP server

The stdio entry point (`dist/src/server/index.js`) is for clients that launch
the server as a local subprocess. This guide deploys the **Streamable HTTP**
entry point (`dist/src/server/http.js`) on a VPS so any MCP client can connect
over HTTPS — no local install required.

Architecture on the VPS:

```
client ──HTTPS──▶ Caddy (TLS, :443) ──HTTP──▶ node http.js (127.0.0.1:8080)
```

The Node process binds to localhost only; Caddy terminates TLS and is the only
thing exposed. Auth is a static bearer token checked by the Node process.

## 1. Prerequisites

- A VPS with a public IP (any recent Debian/Ubuntu assumed below).
- A DNS A record pointing a hostname at it, e.g. `mcp.example.com`.
  TLS certificates require a real hostname; claude.ai connectors require HTTPS.
- Node.js 20+ (`node --version`). On Debian/Ubuntu:
  `curl -fsSL https://deb.nodesource.com/setup_20.x | sudo bash - && sudo apt install -y nodejs`

## 2. Install the server

```sh
sudo useradd --system --home /opt/fpv-sim-mcp --shell /usr/sbin/nologin fpvsim
sudo git clone https://github.com/wasomma/fpv-sim-mcp.git /opt/fpv-sim-mcp
cd /opt/fpv-sim-mcp
sudo npm ci
sudo npm run build
sudo chown -R fpvsim:fpvsim /opt/fpv-sim-mcp
```

## 3. Configure the secret

```sh
sudo mkdir -p /etc/fpv-sim-mcp
openssl rand -hex 32   # this is your bearer token; save it somewhere safe
sudo tee /etc/fpv-sim-mcp/env >/dev/null <<'EOF'
MCP_AUTH_TOKEN=<paste the token here>
PORT=8080
HOST=127.0.0.1
EOF
sudo chmod 600 /etc/fpv-sim-mcp/env
```

The server refuses to start with no token unless you explicitly set
`MCP_NO_AUTH=1` — an open endpoint must be a decision, not a default.

## 4. Run it under systemd

```sh
sudo cp deploy/fpv-sim-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fpv-sim-mcp
systemctl status fpv-sim-mcp        # expect "ready on http://127.0.0.1:8080/mcp"
curl -s localhost:8080/healthz      # expect {"ok":true,...}
```

## 5. Put Caddy in front (TLS)

```sh
sudo apt install -y caddy
```

**If apt says Caddy is already installed, stop and look before touching its
config** — an existing Caddy is almost certainly already serving something,
and its Caddyfile is that service's only route to the internet. Check first:

```sh
cat /etc/caddy/Caddyfile
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak   # cheap insurance either way
```

Then **append** this server's site block to `/etc/caddy/Caddyfile`, keeping
any existing blocks — Caddy routes each request by hostname, so sites coexist
freely:

```
mcp.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

```sh
sudo systemctl reload caddy
```

That's the whole TLS story — Caddy obtains and renews the Let's Encrypt
certificate automatically. Verify from anywhere:

```sh
curl -s https://mcp.example.com/healthz
```

## 6. Connect a client

Claude Code:

```sh
claude mcp add --transport http fpv-sim https://mcp.example.com/mcp \
  --header "Authorization: Bearer <token>"
```

Or in a project `.mcp.json`:

```json
{
  "mcpServers": {
    "fpv-sim": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Smoke test without any client (the `Accept` header matters — Streamable HTTP
requires clients to accept both JSON and SSE):

```sh
curl -s https://mcp.example.com/mcp \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## 7. Updating

```sh
cd /opt/fpv-sim-mcp
sudo -u fpvsim git pull
sudo npm ci && sudo npm run build
sudo chown -R fpvsim:fpvsim /opt/fpv-sim-mcp
sudo systemctl restart fpv-sim-mcp
```

## Notes and limits

- **Stateless by design.** Each request gets a fresh server instance;
  `GET /mcp` (the server-push notification stream) and `DELETE /mcp` return
  405. Nothing this server does needs sessions — every tool call is
  self-contained and deterministic.
- **claude.ai custom connectors** can't send custom headers, so the bearer
  token doesn't work there; the spec'd path is OAuth. For a notional-data demo
  server, running a separate `MCP_NO_AUTH=1` instance behind rate limiting is
  a pragmatic alternative; add OAuth if it graduates beyond that.
- **Threat model.** The server exposes CPU, not data (all outputs are
  notional). Worst-case abuse is someone running thousand-seed sweeps on your
  VPS — which is what the token, the unit file's `MemoryMax`/`CPUQuota`, and
  Caddy rate limiting (if desired) are for.
