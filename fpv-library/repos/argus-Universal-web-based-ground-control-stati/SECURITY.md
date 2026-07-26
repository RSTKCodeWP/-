# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Argus GCS, please report it responsibly.

**Email:** lsc1476907630@gmail.com

**What to include:**
- Description of the vulnerability
- Steps to reproduce
- Affected version(s)
- Potential impact

**Response timeline:**
- Acknowledgment within 48 hours
- Status update within 7 days
- Fix or mitigation plan within 30 days for confirmed issues

**Please do NOT:**
- Open a public GitHub issue for security vulnerabilities
- Exploit the vulnerability beyond what is necessary to demonstrate it

## Scope

Argus GCS is a ground control station that runs on a local network. Security concerns include:

- **WebSocket/REST API** — authentication bypass, injection, unauthorized command execution
- **MAVLink protocol handling** — malformed message processing, buffer overflows
- **File handling** — path traversal, arbitrary file read/write
- **Network** — SSRF, CORS misconfiguration
- **Dependencies** — known CVEs in third-party packages

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest release | Yes |
| Older releases | Best effort |
