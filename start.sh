#!/bin/bash
set -e

echo "=== Music Downloader Starting ==="
echo "PORT: ${PORT:-10000}"
echo "RENDER: ${RENDER:-not set}"
echo "IS_CLOUD: $(python -c "from src.config import IS_CLOUD; print(IS_CLOUD)")"
echo "Download dir: $(python -c "from src.config import DOWNLOAD_DIR; print(DOWNLOAD_DIR)")"
echo "Templates dir: $(python -c "from src.config import TEMPLATES_DIR; print(TEMPLATES_DIR)")"
echo "================================="

exec python -m uvicorn src.server:app \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips '*'
