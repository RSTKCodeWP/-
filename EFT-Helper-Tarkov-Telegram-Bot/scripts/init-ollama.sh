#!/bin/bash
# Initialize Ollama with Qwen3-Coder-480B-Cloud model

echo "🔄 Checking Ollama service..."

# Wait for Ollama to be ready
until curl -sf http://localhost:11434/api/tags > /dev/null; do
    echo "⏳ Waiting for Ollama to start..."
    sleep 2
done

echo "✅ Ollama is ready"

# Check if model exists
if ollama list | grep -q "qwen3-coder:480b-cloud"; then
    echo "✅ Model qwen3-coder:480b-cloud already exists"
else
    echo "📥 Downloading Qwen3-Coder-480B-Cloud model (this may take 5-10 minutes)..."
    ollama pull qwen3-coder:480b-cloud
    echo "✅ Model downloaded successfully"
fi

echo "🎉 Ollama initialization complete"
