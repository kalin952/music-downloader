#!/bin/bash
# Music Downloader — macOS 打包脚本
# 使用 PyInstaller 生成 .app 捆绑包

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_DIR="$PROJECT_DIR/build/macos"
DIST_DIR="$PROJECT_DIR/build/macos/dist"
VENV_DIR="$PROJECT_DIR/.venv"

APP_NAME="MusicDownloader"
VERSION=$(grep 'VERSION = ' "$PROJECT_DIR/src/config.py" | head -1 | cut -d'"' -f2)

echo "=== 构建 $APP_NAME v$VERSION ==="

# 确保虚拟环境和依赖
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
fi

echo "安装依赖..."
"$VENV_DIR/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt" pyinstaller

# 查找 ffmpeg 路径
FFMPEG_PATH=$(which ffmpeg || echo "")
if [ -z "$FFMPEG_PATH" ]; then
    echo "警告: 未找到 ffmpeg，B站视频处理功能可能不可用"
fi

mkdir -p "$BUILD_DIR"

echo "开始 PyInstaller 打包..."
cd "$PROJECT_DIR"

"$VENV_DIR/bin/pyinstaller" \
    --name="$APP_NAME" \
    --onefile \
    --windowed \
    --icon=none \
    --add-data "frontend:frontend" \
    --add-data "src:src" \
    --hidden-import=yt_dlp \
    --hidden-import=httpx \
    --hidden-import=aiofiles \
    --hidden-import=jinja2 \
    --hidden-import=uvicorn.loops.auto \
    --hidden-import=uvicorn.protocols.http.auto \
    --hidden-import=fastapi \
    --hidden-import=starlette \
    --collect-all yt_dlp \
    --collect-all httpx \
    --workpath "$BUILD_DIR/pyinstaller-work" \
    --distpath "$DIST_DIR" \
    --specpath "$BUILD_DIR" \
    run_desktop.py

# 清理工作目录
rm -rf "$BUILD_DIR/pyinstaller-work"

# 创建 .app 捆绑包结构
APP_DIR="$DIST_DIR/$APP_NAME.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# 移动可执行文件
mv "$DIST_DIR/$APP_NAME" "$APP_DIR/Contents/MacOS/$APP_NAME"

# 创建 Info.plist
cat > "$APP_DIR/Contents/Info.plist" << INFOEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>Music Downloader</string>
    <key>CFBundleIdentifier</key>
    <string>com.musicdownloader.app</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleExecutable</key>
    <string>$APP_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
INFOEOF

# 复制 ffmpeg 到资源目录（如果存在）
if [ -n "$FFMPEG_PATH" ]; then
    cp "$FFMPEG_PATH" "$APP_DIR/Contents/Resources/ffmpeg"
    chmod +x "$APP_DIR/Contents/Resources/ffmpeg"
fi

chmod +x "$APP_DIR/Contents/MacOS/$APP_NAME"

# 创建 DMG
echo "创建 DMG 安装包..."
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$APP_DIR" \
    -ov \
    -format UDZO \
    "$DIST_DIR/$APP_NAME-$VERSION.dmg" 2>/dev/null || true

echo ""
echo "=== 构建完成 ==="
echo "App:  $APP_DIR"
echo "DMG:  $DIST_DIR/$APP_NAME-$VERSION.dmg"
echo "Size (DMG): $(du -sh "$DIST_DIR/$APP_NAME-$VERSION.dmg" 2>/dev/null | cut -f1 || echo 'N/A')"
