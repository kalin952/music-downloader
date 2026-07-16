"""
QQ 音乐解析器

策略 (三级降级)：
1. 尝试解析分享页 HTML 中的 SSR 数据获取歌曲信息
2. 调用公开接口获取标准品质下载链接
3. 失败时返回友好提示
"""
import re
import json
import httpx
from .base import BaseParser, ParseResult, MediaType


class QQMusicParser(BaseParser):
    platform = "qqmusic"

    BASE_URL = "https://c.y.qq.com"

    async def _fetch_json(self, client: httpx.AsyncClient, url: str, params: dict = None) -> dict:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://y.qq.com/",
        }
        resp = await client.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _extract_song_mid(self, url: str) -> str:
        """从 QQ 音乐链接中提取 songmid"""
        # y.qq.com/n/ryqq/songDetail/003JUVFu3pLu6e
        m = re.search(r"songDetail/(\w+)", url)
        if m:
            return m.group(1)
        # songmid=xxx
        m = re.search(r"songmid=(\w+)", url)
        if m:
            return m.group(1)
        return ""

    def _parse_ssr_html(self, html: str) -> dict | None:
        """尝试从分享页 HTML 中提取 SSR 数据"""
        # 方式1: <script>window.__INITIAL_DATA__ = {...}</script>
        m = re.search(r"window\.__INITIAL_DATA__\s*=\s*(\{.+?\});", html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 方式2: <script id="ssr-data" type="application/json">...</script>
        m = re.search(r'<script[^>]*id="ssr-data"[^>]*>(.+?)</script>', html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass

        # 方式3: 从 title 标签获取歌名
        m = re.search(r"<title>(.+?)\s*-\s*QQ音乐", html)
        if m:
            return {"title": m.group(1).strip()}

        return None

    async def parse(self, url: str) -> ParseResult:
        song_mid = self._extract_song_mid(url)

        if not song_mid:
            return ParseResult(
                success=False,
                platform=self.platform,
                media_type=MediaType.AUDIO,
                error="无法从链接中提取歌曲 ID，请复制完整分享链接",
                raw_url=url,
            )

        try:
            async with httpx.AsyncClient() as client:
                # 策略1: 调用 get_song_detail API（最可靠）
                title = ""
                artist = ""
                cover = ""
                duration = 0

                try:
                    mobile_headers = {
                        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                        "Referer": "https://y.qq.com/",
                        "Content-Type": "application/json",
                    }
                    payload = {
                        "comm": {"ct": 24, "cv": 0},
                        "detail": {
                            "module": "music.pf_song_detail_svr",
                            "method": "get_song_detail",
                            "param": {"song_mid": song_mid, "song_type": 0},
                        },
                    }
                    resp = await client.post(
                        "https://u.y.qq.com/cgi-bin/musicu.fcg",
                        json=payload,
                        headers=mobile_headers,
                        timeout=15,
                    )
                    api_data = resp.json()
                    detail = api_data.get("detail", {})
                    if detail.get("code") == 0:
                        info = detail.get("data", {}).get("track_info", {})
                        if info and info.get("mid") == song_mid:
                            title = info.get("name") or info.get("title", "")
                            singer_list = info.get("singer", [])
                            artist = " / ".join(s.get("name", "") for s in singer_list)
                            album = info.get("album", {})
                            cover_mid = album.get("pmid") or album.get("mid", "")
                            if cover_mid:
                                cover = f"https://y.qq.com/music/photo_new/T002R300x300M000{cover_mid}.jpg"
                            duration = info.get("interval", 0)
                except Exception:
                    pass

                # 策略2: 降级 — 尝试从分享页标题提取歌名
                if not title:
                    try:
                        resp = await client.get(
                            f"https://y.qq.com/n/ryqq/songDetail/{song_mid}",
                            headers={
                                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                            },
                            follow_redirects=True,
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            ssr_data = self._parse_ssr_html(resp.text)
                            if ssr_data:
                                title = ssr_data.get("title", "")
                    except Exception:
                        pass

                if not title:
                    return ParseResult(
                        success=False,
                        platform=self.platform,
                        media_type=MediaType.AUDIO,
                        error="无法解析 QQ 音乐链接，请确认链接有效或尝试复制完整分享链接",
                        raw_url=url,
                    )

                formats = [
                    {
                        "id": "standard",
                        "label": "标准品质 (128kbps MP3)",
                        "type": "audio",
                        "ext": "mp3",
                        "note": "通过分享页下载，无需登录",
                    },
                    {
                        "id": "hq",
                        "label": "高品质 (320kbps MP3)",
                        "type": "audio",
                        "ext": "mp3",
                        "note": "需要 Cookie 登录（实验性）",
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
                error=f"QQ音乐解析失败: {str(e)}",
                raw_url=url,
            )

    async def get_download_url(self, url: str, fmt: str) -> tuple[str, str]:
        """返回 (下载直链, 文件扩展名)"""
        song_mid = self._extract_song_mid(url)
        ext = "m4a" if fmt == "standard" else "mp3"

        if not song_mid:
            return url, ext

        # 通过 API 获取 vkey 拼接真实下载链接
        try:
            async with httpx.AsyncClient() as client:
                mobile_headers = {
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                    "Referer": "https://y.qq.com/",
                    "Content-Type": "application/json",
                }

                # 获取歌曲的 file 信息和 vkey
                if fmt == "standard":
                    quality = "128mp3"
                else:
                    quality = "320mp3"

                payload = {
                    "req_0": {
                        "module": "music.vkey.GetVkey",
                        "method": "GetUrl",
                        "param": {
                            "guid": "music-downloader",
                            "songmid": [song_mid],
                            "songtype": [0],
                            "uin": "0",
                            "loginflag": 1,
                            "platform": "20",
                        },
                    }
                }
                resp = await client.post(
                    "https://u.y.qq.com/cgi-bin/musicu.fcg",
                    json=payload,
                    headers=mobile_headers,
                    timeout=15,
                )
                data = resp.json()
                req_0 = data.get("req_0", {})
                if req_0.get("code") == 0:
                    midurlinfo = req_0.get("data", {}).get("midurlinfo", [])
                    sip_list = req_0.get("data", {}).get("sip", [])
                    if midurlinfo and sip_list:
                        purl = midurlinfo[0].get("purl", "")
                        if purl:
                            dl_url = f"{sip_list[0]}{purl}"
                            return dl_url, ext

                # 降级: 直接拼 URL（可能无权限但可尝试）
                dl_url = (
                    f"https://dl.stream.qqmusic.qq.com/C400{song_mid}.m4a"
                    f"?guid=music-downloader&vkey=&uin=&fromtag=66"
                )
                return dl_url, ext
        except Exception:
            # 最底层降级
            dl_url = (
                f"https://dl.stream.qqmusic.qq.com/C400{song_mid}.m4a"
                f"?guid=music-downloader&vkey=&uin=&fromtag=66"
            )
            return dl_url, ext
