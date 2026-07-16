#!/bin/sh
set -e

echo "=== Music Downloader Starting ==="
echo "PORT: ${PORT:-10000}"
echo "================================="

# 使用 python3 兼容 slim 镜像
exec python3 -m uvicorn src.server:app \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips '*'
