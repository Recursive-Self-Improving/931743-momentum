#!/usr/bin/env bash
set -euo pipefail

# 使用 Hermes venv 里的 Python3，确保 akshare 等依赖可用
PYTHON3="/root/.hermes/hermes-agent/venv/bin/python3"

# 进入项目目录
cd "$(dirname "$0")"

# 检查依赖
if ! $PYTHON3 -c "import akshare" 2>/dev/null; then
    echo "⚠️ akshare 未安装，正在安装..."
    $PYTHON3 -m pip install -r requirements.txt
fi

# 执行命令
exec $PYTHON3 main.py "$@"
