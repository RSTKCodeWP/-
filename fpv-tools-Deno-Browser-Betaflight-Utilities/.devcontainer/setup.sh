#!/bin/bash

set -e

echo "🚀 Setting up Val.town development environment..."

# Install Deno
echo "📦 Installing Deno..."
curl -fsSL https://deno.land/install.sh | sh
export DENO_INSTALL="/home/node/.deno"
export PATH="$DENO_INSTALL/bin:$PATH"

# Add Deno to PATH permanently
echo 'export DENO_INSTALL="/home/node/.deno"' >> ~/.bashrc
echo 'export PATH="$DENO_INSTALL/bin:$PATH"' >> ~/.bashrc

# Install Val CLI
echo "📦 Installing Val CLI..."
npm install -g @valtown/cli

# Install Claude Code CLI
echo "📦 Installing Claude Code..."
npm install -g @anthropic-ai/claude-code

# Verify installations
echo ""
echo "✅ Installation complete!"
echo ""
echo "Installed versions:"
echo "  - Deno: $(deno --version | head -n 1)"
echo "  - Val CLI: $(val --version)"
echo "  - GitHub CLI: $(gh --version | head -n 1)"
echo "  - Claude Code: $(claude-code --version || echo 'installed')"
echo ""
echo "🎉 Ready to build Val.town vals with Claude Code!"
echo ""
echo "Next steps:"
echo "  1. Authenticate with Val.town: val login"
echo "  2. Authenticate with GitHub: gh auth login"
echo "  3. Start building!"
