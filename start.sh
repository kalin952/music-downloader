#!/bin/sh

echo "=========================================="
echo "Music Downloader Startup"
echo "=========================================="
echo "Date: $(date)"
echo "Working dir: $(pwd)"
echo "Python3: $(which python3) ($(python3 --version 2>&1))"
echo "FFmpeg: $(which ffmpeg 2>&1)"
echo "PORT env: '${PORT:-not set}'"
echo "RENDER env: '${RENDER:-not set}'"
echo "=========================================="
echo "Files in /app:"
ls -la
echo "=========================================="
echo "Starting uvicorn..."
echo "=========================================="

# Use exec so the shell process is replaced by python (proper signal handling)
exec python3 -m uvicorn src.server:app \
    --host 0.0.0.0 \
    --port ${PORT:-10000} \
    --log-level info \
    --proxy-headers \
    --forwarded-allow-ips '*'
