"""
B站视频解析器
基于 yt-dlp Python API
"""
import re
import yt_dlp
from .base import BaseParser, ParseResult, MediaType


class BilibiliParser(BaseParser):
    platform = "bilibili"

    def _extract_id(self, url: str) -> str:
        """从 B站链接中提取 BV 号或 AV 号"""
        # BV号
        m = re.search(r"BV[a-zA-Z0-9]{10}", url)
        if m:
            return m.group(0)
        # AV号
        m = re.search(r"av(\d+)", url, re.IGNORECASE)
        if m:
            return f"av{m.group(1)}"
        # b23.tv 短链
        return url

    def _build_formats(self, info: dict) -> list[dict]:
        """从 yt-dlp 信息中构建可用格式列表"""
        formats = []

        # 视频格式
        format_list = info.get("formats", [])
        seen_heights = set()
        for f in format_list:
            height = f.get("height")
            if height and height not in seen_heights and height >= 360:
                seen_heights.add(height)
                label = f"{height}p"
                if height >= 2160:
                    label = "4K"
                elif height >= 1080:
                    label = "1080p"
                elif height >= 720:
                    label = "720p"
                elif height >= 480:
                    label = "480p"
                else:
                    label = "360p"

                # 估算大小
                filesize = f.get("filesize") or f.get("filesize_approx", 0)
                size_mb = round(filesize / 1024 / 1024, 1) if filesize else 0

                formats.append({
                    "id": f"bestvideo[height<={height}]+bestaudio",
                    "label": label,
                    "type": "video",
                    "size_mb": size_mb if size_mb > 0 else None,
                    "note": "视频 + 音频" if height >= 480 else "标清",
                })

        # 仅音频
        formats.append({
            "id": "bestaudio",
            "label": "MP3 音频",
            "type": "audio",
            "size_mb": None,
            "note": "从视频提取音频",
        })

        # 弹幕（可选）
        formats.append({
            "id": "danmaku",
            "label": "弹幕文件 (XML)",
            "type": "subtitle",
            "size_mb": None,
            "note": "附带弹幕",
        })

        return formats

    async def parse(self, url: str) -> ParseResult:
        try:
            video_id = self._extract_id(url)

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
            }

            def _extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(url, download=False)

            info = _extract()

            title = info.get("title", "")
            uploader = info.get("uploader", "")
            duration = info.get("duration", 0) or 0
            thumbnail = info.get("thumbnail", "")

            return ParseResult(
                success=True,
                platform=self.platform,
                media_type=MediaType.VIDEO,
                title=title,
                uploader=uploader,
                cover_url=thumbnail,
                duration=duration,
                available_formats=self._build_formats(info),
                raw_url=url,
            )
        except Exception as e:
            return ParseResult(
                success=False,
                platform=self.platform,
                media_type=MediaType.VIDEO,
                error=f"B站解析失败: {str(e)}",
                raw_url=url,
            )

    async def get_download_url(self, url: str, fmt: str) -> tuple[dict, str]:
        """
        返回 (yt_dlp_options, extension)
        fmt 可以是格式 id 字符串
        """
        # 构建 yt-dlp 下载选项
        if fmt == "bestaudio":
            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "no_warnings": True,
            }
            ext = "mp3"
        elif fmt == "danmaku":
            ydl_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["danmaku"],
                "subtitlesformat": "xml",
                "quiet": True,
            }
            ext = "xml"
        else:
            # 视频格式
            ydl_opts = {
                "format": fmt,
                "merge_output_format": "mp4",
                "quiet": True,
                "no_warnings": True,
            }
            ext = "mp4"

        return ydl_opts, ext
