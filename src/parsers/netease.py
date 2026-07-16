"""
网易云音乐解析器

策略：
1. 解析分享页 HTML（SSR 渲染），获取歌曲基本信息
2. 调用公开 API 接口获取详细信息
3. 支持标准品质 (128kbps) 默认，高音质需 cookie
"""
import re
import json
import httpx
from .base import BaseParser, ParseResult, MediaType


class NeteaseParser(BaseParser):
    platform = "netease"

    BASE_API = "https://music.163.com/api"

    # 公开 API 端点（无需登录）
    SONG_DETAIL = "https://music.163.com/api/song/detail"
    SONG_URL = "https://music.163.com/song/media/outer/url"

    async def _fetch_json(self, client: httpx.AsyncClient, url: str, params: dict = None) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://music.163.com/",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _extract_song_id(self, url: str) -> str:
        """从各种网易云链接中提取歌曲 ID"""
        # music.163.com/song?id=123456
        m = re.search(r"[?&]id=(\d+)", url)
        if m:
            return m.group(1)
        # music.163.com/song/123456/
        m = re.search(r"/song/(\d+)", url)
        if m:
            return m.group(1)
        return ""

    async def parse(self, url: str) -> ParseResult:
        song_id = self._extract_song_id(url)
        if not song_id:
            return ParseResult(
                success=False,
                platform=self.platform,
                media_type=MediaType.AUDIO,
                error="无法识别网易云音乐链接，请确认链接格式正确",
                raw_url=url,
            )

        try:
            async with httpx.AsyncClient() as client:
                # 获取歌曲详情
                params = {"id": song_id, "ids": f"[{song_id}]"}
                data = await self._fetch_json(client, self.SONG_DETAIL, params)

                songs = data.get("songs", [])
                if not songs:
                    return ParseResult(
                        success=False,
                        platform=self.platform,
                        media_type=MediaType.AUDIO,
                        error="歌曲不存在或已下架",
                        raw_url=url,
                    )
                song_data = songs[0]

                title = song_data.get("name", "")
                artists = [ar.get("name", "") for ar in song_data.get("artists", [])]
                artist = " / ".join(artists)
                album_data = song_data.get("album", {})
                cover = album_data.get("picUrl", "")
                duration = song_data.get("duration", 0) // 1000  # 毫秒转秒

                # 构建可用格式
                formats = [
                    {
                        "id": "standard",
                        "label": "标准品质 (128kbps MP3)",
                        "type": "audio",
                        "ext": "mp3",
                        "note": "无需登录",
                    },
                    {
                        "id": "higher",
                        "label": "较高品质 (192kbps MP3)",
                        "type": "audio",
                        "ext": "mp3",
                        "note": "需要 Cookie 登录",
                    },
                    {
                        "id": "lossless",
                        "label": "无损品质 (FLAC)",
                        "type": "audio",
                        "ext": "flac",
                        "note": "需要 VIP Cookie",
                    },
                ]

                return ParseResult(
                    success=True,
                    platform=self.platform,
                    media_type=MediaType.AUDIO,
                    title=title,
                    artist=artist,
                    cover_url=cover,
                    duration=duration,
                    available_formats=formats,
                    raw_url=url,
                )
        except Exception as e:
            return ParseResult(
                success=False,
                platform=self.platform,
                media_type=MediaType.AUDIO,
                error=f"网易云音乐解析失败: {str(e)}",
                raw_url=url,
            )

    async def get_download_url(self, url: str, fmt: str) -> tuple[str, str]:
        """
        返回 (下载直链, 文件扩展名)
        fmt: standard | higher | lossless
        """
        song_id = self._extract_song_id(url)
        ext = "mp3" if fmt != "lossless" else "flac"

        if fmt == "standard":
            # 标准品质 — 公开外链
            dl_url = f"{self.SONG_URL}?id={song_id}.mp3"
        elif fmt == "higher":
            dl_url = f"{self.SONG_URL}?id={song_id}.mp3&br=192000"
        else:
            dl_url = f"{self.SONG_URL}?id={song_id}.flac&br=999000"

        return dl_url, ext
