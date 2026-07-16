"""
解析器基类
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MediaType(str, Enum):
    AUDIO = "audio"
    VIDEO = "video"


class MediaFormat(str, Enum):
    # 音频格式
    MP3_128 = "mp3_128"
    MP3_320 = "mp3_320"
    FLAC = "flac"
    # 视频格式
    VIDEO_360P = "360p"
    VIDEO_480P = "480p"
    VIDEO_720P = "720p"
    VIDEO_1080P = "1080p"
    VIDEO_4K = "4k"
    # 仅音频（从视频提取）
    VIDEO_AUDIO = "video_audio"


@dataclass
class ParseResult:
    """解析结果"""
    success: bool
    platform: str
    media_type: MediaType
    title: str = ""
    artist: str = ""          # 音乐：歌手
    uploader: str = ""         # 视频：UP主
    cover_url: str = ""
    duration: int = 0          # 秒
    size_mb: float = 0
    available_formats: list[dict] = field(default_factory=list)
    error: str = ""
    raw_url: str = ""

    @property
    def info_line(self) -> str:
        if self.media_type == MediaType.AUDIO:
            return f"{self.title} - {self.artist}"
        return f"{self.title}"


class BaseParser:
    """解析器基类"""

    platform: str = "unknown"

    async def parse(self, url: str) -> ParseResult:
        raise NotImplementedError

    async def get_download_url(self, url: str, fmt: str) -> tuple[str, str]:
        """返回 (下载直链, 文件扩展名)"""
        raise NotImplementedError
