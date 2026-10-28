#!/bin/bash
# Jot-Local 一键启动脚本
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=================================================="
echo "🚀 启动 Jot-Local 纯本地离线服务"
echo "=================================================="

# 检查 Ollama 是否运行
if curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "✅ 检测到本地 Ollama 服务正常运行"
else
    echo "⚠️ 未检测到本地 Ollama 服务 (http://127.0.0.1:11434)"
    echo "   建议在后台运行: ollama run qwen2.5:1.5b"
fi

python3 "$DIR/server.py"
