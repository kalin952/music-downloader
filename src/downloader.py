"""
统一下载管理模块

职责：
1. 管理下载任务队列
2. 流式下载 + 实时进度上报
3. B站特殊处理（yt-dlp 下载 + ffmpeg 合并）
"""
import os
import re
import time
import asyncio
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable

import httpx
import yt_dlp

from .config import DOWNLOAD_DIR, TEMP_DIR


@dataclass
class DownloadTask:
    """单个下载任务"""
    task_id: str
    url: str
    title: str
    platform: str
    format_id: str
    ext: str
    status: str = "pending"  # pending | downloading | processing | done | error
    progress: float = 0.0
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed: str = ""
    eta: str = ""
    output_path: str = ""
    error: str = ""
    start_time: float = 0.0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "url": self.url,
            "title": self.title,
            "platform": self.platform,
            "format_id": self.format_id,
            "ext": self.ext,
            "status": self.status,
            "progress": self.progress,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "speed": self.speed,
            "eta": self.eta,
            "output_path": self.output_path,
            "error": self.error,
        }


class DownloadProgressHook:
    """yt-dlp 下载进度回调"""

    def __init__(self, task: DownloadTask, on_update: Callable):
        self.task = task
        self.on_update = on_update

    def __call__(self, d: dict):
        status = d.get("status", "")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            eta = d.get("eta") or 0

            self.task.status = "downloading"
            self.task.total_bytes = total
            self.task.downloaded_bytes = downloaded
            self.task.speed = self._format_speed(speed)
            self.task.eta = self._format_eta(eta)

            if total > 0:
                self.task.progress = round(downloaded / total * 100, 1)
            else:
                size_str = d.get("_percent_str", "0%")
                try:
                    self.task.progress = float(size_str.replace("%", "").strip())
                except ValueError:
                    self.task.progress = 0

            self.on_update()

        elif status == "finished":
            self.task.status = "processing"
            self.task.progress = 100.0
            self.on_update()

    @staticmethod
    def _format_speed(speed: float) -> str:
        if speed == 0:
            return ""
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        else:
            return f"{speed / (1024 * 1024):.1f} MB/s"

    @staticmethod
    def _format_eta(eta: int) -> str:
        if eta <= 0:
            return ""
        if eta < 60:
            return f"{eta}秒"
        elif eta < 3600:
            return f"{eta // 60}分{eta % 60}秒"
        else:
            hours = eta // 3600
            mins = (eta % 3600) // 60
            return f"{hours}小时{mins}分"


class DownloadManager:
    """下载管理器"""

    def __init__(self):
        self.tasks: dict[str, DownloadTask] = {}
        self._callbacks: dict[str, list[Callable]] = {}
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)

    def sanitize_filename(self, name: str) -> str:
        """清理文件名中的非法字符"""
        name = re.sub(r'[\\/:*?"<>|]', "_", name)
        return name.strip().rstrip(".")

    def create_task(self, url: str, title: str, platform: str, fmt_id: str, ext: str) -> DownloadTask:
        """创建下载任务"""
        task_id = hashlib.md5(f"{url}-{fmt_id}-{time.time()}".encode()).hexdigest()[:12]
        task = DownloadTask(
            task_id=task_id,
            url=url,
            title=title,
            platform=platform,
            format_id=fmt_id,
            ext=ext,
        )
        self.tasks[task_id] = task
        return task

    def on_update(self, task_id: str, callback: Callable):
        """注册进度回调（用于 SSE 推送）"""
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)

    def _notify(self, task: DownloadTask):
        callbacks = self._callbacks.get(task.task_id, [])
        for cb in callbacks:
            try:
                cb(task)
            except Exception:
                pass

    async def download_bilibili(self, task: DownloadTask) -> str:
        """B站下载：使用 yt-dlp"""
        # 清理历史进度回调
        progress_items = []

        def _on_progress():
            progress_items.append(task.to_dict())

        hook = DownloadProgressHook(task, _on_progress)
        task.start_time = time.time()

        # 输出文件名模板
        safe_title = self.sanitize_filename(task.title)
        if task.format_id == "bestaudio":
            out_tmpl = os.path.join(DOWNLOAD_DIR, f"{safe_title}.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": out_tmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "progress_hooks": [hook],
                "quiet": True,
                "no_warnings": True,
            }
        else:
            out_tmpl = os.path.join(DOWNLOAD_DIR, f"{safe_title}.%(ext)s")
            ydl_opts = {
                "format": task.format_id,
                "outtmpl": out_tmpl,
                "merge_output_format": "mp4",
                "progress_hooks": [hook],
                "quiet": True,
                "no_warnings": True,
            }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(task.url, download=True)
                return ydl.prepare_filename(info)

        loop = asyncio.get_event_loop()
        filename = await loop.run_in_executor(None, _download)

        # 如果是 mp3 提取，文件名后缀变了
        if task.format_id == "bestaudio":
            final_path = filename.rsplit(".", 1)[0] + ".mp3"
        else:
            final_path = filename

        # 确保文件存在
        if not os.path.exists(final_path):
            # 尝试找合并后的文件
            base = os.path.splitext(filename)[0]
            for ext in [".mp4", ".mkv", ".webm", ".mp3"]:
                candidate = base + ext
                if os.path.exists(candidate):
                    final_path = candidate
                    break

        task.status = "done"
        task.progress = 100.0
        task.output_path = final_path
        self._notify(task)
        return final_path

    async def download_netease(self, task: DownloadTask) -> str:
        """网易云下载：HTTP 流式下载"""
        safe_title = self.sanitize_filename(task.title)
        output_path = os.path.join(DOWNLOAD_DIR, f"{safe_title}.{task.ext}")

        task.start_time = time.time()
        task.status = "downloading"
        self._notify(task)

        song_id = ""
        import re
        m = re.search(r"[?&]id=(\d+)", task.url)
        if m:
            song_id = m.group(1)
        m = re.search(r"/song/(\d+)", task.url)
        if m:
            song_id = m.group(1)

        if task.format_id == "standard":
            dl_url = f"https://music.163.com/song/media/outer/url?id={song_id}"
        elif task.format_id == "higher":
            dl_url = f"https://music.163.com/song/media/outer/url?id={song_id}&br=192000"
        else:
            dl_url = f"https://music.163.com/song/media/outer/url?id={song_id}&br=999000"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://music.163.com/",
            "Accept": "audio/*, application/octet-stream",
        }

        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            async with client.stream("GET", dl_url, headers=headers) as resp:
                if resp.status_code != 200:
                    task.status = "error"
                    task.error = f"下载失败，HTTP {resp.status_code}"
                    self._notify(task)
                    return ""

                # 检查响应是否真的是音频（网易云有时返回 HTML 错误页）
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type:
                    task.status = "error"
                    task.error = "网易云返回了网页而非音频文件。可能的解决方案：1) 该歌曲可能需要登录 2) 尝试其他品质 3) 稍后重试"
                    self._notify(task)
                    return ""

                task.total_bytes = int(resp.headers.get("content-length", 0))
                task.downloaded_bytes = 0

                with open(output_path, "wb") as f:
                    last_time = time.time()
                    last_bytes = 0
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        task.downloaded_bytes += len(chunk)

                        now = time.time()
                        if now - last_time >= 0.5:  # 每 0.5 秒更新一次进度
                            elapsed = now - last_time
                            speed = (task.downloaded_bytes - last_bytes) / elapsed
                            task.speed = DownloadProgressHook._format_speed(speed)

                            if task.total_bytes > 0:
                                task.progress = round(task.downloaded_bytes / task.total_bytes * 100, 1)
                                remaining = task.total_bytes - task.downloaded_bytes
                                if speed > 0:
                                    eta = remaining / speed
                                    task.eta = DownloadProgressHook._format_eta(int(eta))

                            self._notify(task)
                            last_time = now
                            last_bytes = task.downloaded_bytes

        task.status = "done"
        task.progress = 100.0
        task.output_path = output_path
        self._notify(task)
        return output_path

    async def download_qqmusic(self, task: DownloadTask) -> str:
        """QQ 音乐下载：通过解析器获取真实下载链接后流式下载"""
        safe_title = self.sanitize_filename(task.title)
        output_path = os.path.join(DOWNLOAD_DIR, f"{safe_title}.{task.ext}")

        task.start_time = time.time()
        task.status = "downloading"
        self._notify(task)

        # 使用解析器获取真实下载链接
        from .parsers.qqmusic import QQMusicParser
        parser = QQMusicParser()
        dl_url, _ = await parser.get_download_url(task.url, task.format_id)

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://y.qq.com/",
        }

        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            async with client.stream("GET", dl_url, headers=headers) as resp:
                if resp.status_code != 200:
                    task.status = "error"
                    task.error = f"下载失败，HTTP {resp.status_code}。QQ音乐可能需要登录。"
                    self._notify(task)
                    return ""

                task.total_bytes = int(resp.headers.get("content-length", 0))
                task.downloaded_bytes = 0

                with open(output_path, "wb") as f:
                    last_time = time.time()
                    last_bytes = 0
                    async for chunk in resp.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        task.downloaded_bytes += len(chunk)

                        now = time.time()
                        if now - last_time >= 0.5:
                            elapsed = now - last_time
                            speed = (task.downloaded_bytes - last_bytes) / elapsed
                            task.speed = DownloadProgressHook._format_speed(speed)

                            if task.total_bytes > 0:
                                task.progress = round(task.downloaded_bytes / task.total_bytes * 100, 1)
                                remaining = task.total_bytes - task.downloaded_bytes
                                if speed > 0:
                                    eta = remaining / speed
                                    task.eta = DownloadProgressHook._format_eta(int(eta))

                            self._notify(task)
                            last_time = now
                            last_bytes = task.downloaded_bytes

        task.status = "done"
        task.progress = 100.0
        task.output_path = output_path
        self._notify(task)
        return output_path

    async def download(self, task: DownloadTask) -> str:
        """统一入口：根据平台分发下载"""
        if task.platform == "bilibili":
            return await self.download_bilibili(task)
        elif task.platform == "netease":
            return await self.download_netease(task)
        elif task.platform == "qqmusic":
            return await self.download_qqmusic(task)
        else:
            task.status = "error"
            task.error = f"不支持的平台: {task.platform}"
            self._notify(task)
            return ""


# 全局单例
manager = DownloadManager()
