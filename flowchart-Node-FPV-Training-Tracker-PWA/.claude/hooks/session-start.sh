#!/bin/bash
set -euo pipefail

# Only run in remote (Claude Code on the web) environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Install gh CLI if missing
if ! command -v gh &>/dev/null; then
  apt-get install -y gh 2>&1
fi

# Install repo skills into ~/.claude/skills/
bash "${CLAUDE_PROJECT_DIR}/install-skills.sh"
