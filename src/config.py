"""
应用配置
"""
import os
import sys
import platform

VERSION = "1.0.0"
APP_NAME = "Music Downloader"
PORT = 19527
HOST = "127.0.0.1"

# 下载目录：优先用用户配置，否则用系统默认下载目录
def _get_default_download_dir() -> str:
    system = platform.system()
    if system == "Darwin":
        return os.path.expanduser("~/Downloads/MusicDownloader")
    elif system == "Windows":
        return os.path.join(os.environ.get("USERPROFILE", ""), "Downloads", "MusicDownloader")
    else:
        return os.path.expanduser("~/Downloads/MusicDownloader")


DOWNLOAD_DIR = os.environ.get("MD_DOWNLOAD_DIR", _get_default_download_dir())

# GitHub 仓库信息（用于更新检查）
GITHUB_REPO = os.environ.get("MD_GITHUB_REPO", "kalin952/music-downloader")

# 是否为打包后的环境
IS_FROZEN = getattr(sys, "frozen", False)

# 资源路径（打包后 vs 开发环境）
if IS_FROZEN:
    BASE_DIR = sys._MEIPASS  # type: ignore
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
STATIC_DIR = os.path.join(FRONTEND_DIR, "static")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")

# ffmpeg 路径
def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径"""
    if IS_FROZEN:
        system = platform.system()
        if system == "Windows":
            return os.path.join(BASE_DIR, "bin", "ffmpeg.exe")
        else:
            return os.path.join(BASE_DIR, "bin", "ffmpeg")
    else:
        # 开发环境：用系统安装的 ffmpeg
        return "ffmpeg"


# 临时下载缓存目录
TEMP_DIR = os.path.join(os.path.expanduser("~"), ".music_downloader", "temp")
