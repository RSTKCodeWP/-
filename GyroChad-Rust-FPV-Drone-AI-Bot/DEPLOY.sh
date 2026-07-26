#!/bin/bash
set -e

echo "🚀 GyroChad GitHub Deployment Script"
echo "======================================"

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) not found. Install it first:"
    echo "   brew install gh"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    echo "🔐 Authenticating with GitHub..."
    gh auth login
fi

# Initialize git repository
if [ ! -d ".git" ]; then
    echo "📦 Initializing git repository..."
    git init
    git branch -M main
else
    echo "✅ Git repository already initialized"
fi

# Add all files
echo "📝 Adding files to git..."
git add .

# Create initial commit
echo "💾 Creating initial commit..."
git commit -m "🚁 Initial commit: GyroChad - AI-Powered FPV Drone Assistant

Features:
- RAG pipeline with Qdrant vector database
- Computer vision support (llava)
- Blackbox log analysis (.bbl files)
- Voice transcription (Whisper)
- Conversational memory (10 messages)
- Knowledge injection CLI tool

Tech stack: Rust, Tokio, Ollama, Qdrant, Telegram" || echo "⚠️  No changes to commit"

# Create GitHub repository
echo "🌐 Creating GitHub repository..."
gh repo create GyroChad \
    --public \
    --source=. \
    --description="🚁 AI-Powered FPV Drone Assistant - Telegram bot with RAG, Vision, and Blackbox Analysis" \
    --push

echo ""
echo "✅ Deployment complete!"
echo "📍 Repository: https://github.com/$(gh api user -q .login)/GyroChad"
echo ""
echo "Next steps:"
echo "  1. Add topics: gh repo edit --add-topic rust,telegram-bot,ai,fpv,drone,rag,ollama,qdrant"
echo "  2. Enable GitHub Actions (if needed)"
echo "  3. Add LICENSE file"
