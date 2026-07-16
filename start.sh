#!/bin/sh
set -e

echo "=== Music Downloader Starting ==="
echo "PORT: ${PORT:-10000}"
echo "RENDER: ${RENDER:-not set}"

# 诊断信息：失败不阻断启动
python -c "from src.config import IS_CLOUD; print('IS_CLOUD:', IS_CLOUD)" 2>/dev/null || true
python -c "from src.config import DOWNLOAD_DIR; print('Download dir:', DOWNLOAD_DIR)" 2>/dev/null || true
python -c "from src.config import TEMPLATES_DIR; print('Templates dir:', TEMPLATES_DIR)" 2>/dev/null || true
echo "================================="

exec python -m uvicorn src.server:app \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips '*'
