"""
FastAPI 应用主体
"""
import os
import asyncio
import json
import time
import threading
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import VERSION, APP_NAME, PORT, HOST, STATIC_DIR, TEMPLATES_DIR, DOWNLOAD_DIR, IS_CLOUD
from .parsers import detect_platform, get_parser, ParseResult
from .downloader import manager as download_manager, DownloadTask

app = FastAPI(title=APP_NAME, version=VERSION)

# CORS：允许跨域（前端可能部署在不同域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件 + 模板
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ========================================
# 云端文件清理：定期删除超过 1 小时的下载文件
# ========================================
def _cleanup_old_files():
    """清理超过 1 小时的下载文件"""
    if not os.path.isdir(DOWNLOAD_DIR):
        return
    now = time.time()
    max_age = 3600  # 1 小时
    for filename in os.listdir(DOWNLOAD_DIR):
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        try:
            if os.path.isfile(filepath):
                mtime = os.path.getmtime(filepath)
                if now - mtime > max_age:
                    os.remove(filepath)
        except Exception:
            pass


def _cleanup_loop():
    """后台清理线程"""
    while True:
        try:
            _cleanup_old_files()
        except Exception:
            pass
        time.sleep(300)  # 每 5 分钟清理一次


# 启动清理线程（仅云端）
if IS_CLOUD:
    cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
    cleanup_thread.start()


@app.on_event("startup")
async def startup():
    """确保下载目录存在"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页面"""
    template = templates.get_template("index.html")
    content = template.render(
        request=request,
        version=VERSION,
        app_name=APP_NAME,
        is_cloud=IS_CLOUD,
    )
    return HTMLResponse(content)


@app.get("/api/version")
async def get_version():
    """获取版本信息"""
    return {"version": VERSION, "app_name": APP_NAME, "is_cloud": IS_CLOUD}


@app.post("/api/parse")
async def parse_url(request: Request):
    """解析链接"""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    if not url:
        raise HTTPException(status_code=400, detail="请输入链接")

    platform = detect_platform(url)
    if not platform:
        return JSONResponse({
            "success": False,
            "error": "不支持的链接。目前支持：B站视频、网易云音乐、QQ音乐",
        })

    parser = get_parser(url)
    if not parser:
        return JSONResponse({
            "success": False,
            "error": f"解析器不可用: {platform}",
        })

    result: ParseResult = await parser.parse(url)

    if not result.success:
        return JSONResponse({
            "success": False,
            "error": result.error,
            "platform": platform,
        })

    return JSONResponse({
        "success": True,
        "platform": result.platform,
        "media_type": result.media_type,
        "title": result.title,
        "artist": result.artist,
        "uploader": result.uploader,
        "cover_url": result.cover_url,
        "duration": result.duration,
        "available_formats": result.available_formats,
        "raw_url": result.raw_url,
    })


@app.post("/api/download")
async def start_download(request: Request):
    """开始下载"""
    try:
        body = await request.json()
        url = body.get("url", "").strip()
        fmt_id = body.get("format_id", "")
        title = body.get("title", "unknown")
        platform = body.get("platform", "")
        ext = body.get("ext", "mp3")
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    if not url or not platform:
        raise HTTPException(status_code=400, detail="参数不完整")

    # 创建下载任务
    task = download_manager.create_task(
        url=url,
        title=title,
        platform=platform,
        fmt_id=fmt_id,
        ext=ext,
    )

    # 在后台启动下载
    asyncio.create_task(_run_download(task))

    return JSONResponse({
        "success": True,
        "task_id": task.task_id,
    })


async def _run_download(task: DownloadTask):
    """后台运行下载任务"""
    try:
        await download_manager.download(task)
    except Exception as e:
        task.status = "error"
        task.error = str(e)


@app.get("/api/download/{task_id}/progress")
async def get_progress(task_id: str):
    """SSE 推送下载进度"""
    task = download_manager.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    async def event_generator():
        # 发送事件队列
        queue: asyncio.Queue = asyncio.Queue()

        def on_update(t: DownloadTask):
            try:
                queue.put_nowait(t.to_dict())
            except asyncio.QueueFull:
                pass

        download_manager.on_update(task_id, on_update)

        # 先发送当前状态
        yield f"data: {json.dumps(task.to_dict(), ensure_ascii=False)}\n\n"

        # 持续推送
        try:
            while task.status in ("pending", "downloading", "processing"):
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f"data: {json.dumps(task.to_dict(), ensure_ascii=False)}\n\n"

            # 最终状态
            yield f"data: {json.dumps(task.to_dict(), ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲（SSE 必需）
        },
    )


@app.get("/api/download/{task_id}/status")
async def get_status(task_id: str):
    """轮询获取下载状态"""
    task = download_manager.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JSONResponse(task.to_dict())


@app.get("/api/download/{task_id}/file")
async def download_file(task_id: str):
    """下载完成的文件（浏览器下载）"""
    task = download_manager.tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != "done":
        raise HTTPException(status_code=400, detail="文件尚未下载完成")

    if not os.path.exists(task.output_path):
        raise HTTPException(status_code=404, detail="文件不存在（可能已被清理，请重新下载）")

    filename = os.path.basename(task.output_path)
    return FileResponse(
        task.output_path,
        filename=filename,
        media_type="application/octet-stream",
    )


@app.get("/api/history")
async def get_history():
    """获取下载历史"""
    tasks = [t.to_dict() for t in download_manager.tasks.values()]
    tasks.sort(key=lambda t: t.get("start_time", 0), reverse=True)
    return JSONResponse(tasks)


@app.post("/api/open-folder")
async def open_folder(request: Request):
    """在文件管理器中打开文件所在文件夹（仅桌面版有效）"""
    if IS_CLOUD:
        return JSONResponse({
            "success": False,
            "error": "云端环境不支持打开文件夹，请点击「下载文件」按钮保存到本地",
            "cloud": True,
        })

    try:
        body = await request.json()
        file_path = body.get("path", "")
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    folder = os.path.dirname(file_path)
    import subprocess, platform

    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", folder])
        elif system == "Windows":
            subprocess.Popen(["explorer", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "cloud": IS_CLOUD}
