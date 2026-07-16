from .base import ParseResult, MediaFormat, MediaType
from .bilibili import BilibiliParser
from .netease import NeteaseParser
from .qqmusic import QQMusicParser

# 平台识别 -> 解析器映射
PARSERS = {
    "bilibili": BilibiliParser(),
    "netease": NeteaseParser(),
    "qqmusic": QQMusicParser(),
}


def detect_platform(url: str) -> str | None:
    """根据链接识别平台"""
    patterns = {
        "bilibili": [
            "bilibili.com/video/",
            "b23.tv",
            "bilibili.com/bangumi/",
        ],
        "netease": [
            "music.163.com/song",
            "music.163.com/album",
            "music.163.com/playlist",
            "163cn.tv",
        ],
        "qqmusic": [
            "y.qq.com/n/ryqq/songDetail",
            "y.qq.com/n/ryqq/albumDetail",
            "y.qq.com/n/ryqq/playlist",
            "i.y.qq.com",
            "c.y.qq.com",
        ],
    }

    for platform, pats in patterns.items():
        for pat in pats:
            if pat in url:
                return platform
    return None


def get_parser(url: str):
    """根据 URL 获取对应的解析器"""
    platform = detect_platform(url)
    if platform is None:
        return None
    return PARSERS.get(platform)
