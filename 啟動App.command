#!/bin/bash
cd "$(dirname "$0")"
echo "✦ Listen Within 專案管理 App 啟動中..."
pip3 install flask -q 2>/dev/null
python3 server.py
