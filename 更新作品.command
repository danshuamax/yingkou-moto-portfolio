#!/bin/bash
# 双击即可同步作品（macOS）
cd "$(dirname "$0")"
echo "正在同步作品…"
python3 sync-works.py
echo ""
echo "按回车键关闭窗口"
read -r _
