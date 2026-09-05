#!/bin/bash
set -e

echo "=== Phase 2C Startup Sequence ==="

# 1. Wait for Ollama to be ready
echo "[1/3] Waiting for Ollama to be ready..."
for i in {1..30}; do
  if curl -s http://ollama:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is ready"
    break
  fi
  echo "  Attempt $i/30..."
  sleep 1
done

# 2. Pull model if needed
echo "[2/3] Ensuring model is available..."
MODELS=$(curl -s http://ollama:11434/api/tags 2>/dev/null | grep -o "qwen2.5-coder" || true)
if [ -z "$MODELS" ]; then
  echo "  Pulling qwen2.5-coder:14b (this may take a few minutes)..."
  curl -s -X POST http://ollama:11434/api/pull \
    -d '{"name":"qwen2.5-coder:14b"}' \
    2>/dev/null | tail -1
  echo "✓ Model ready"
else
  echo "✓ Model already available"
fi

# 3. Start app
echo "[3/3] Starting application..."
exec "$@"
