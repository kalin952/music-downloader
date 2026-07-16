"""
Music Downloader — 桌面启动器

职责：
1. 端口冲突检测（避免重复启动）
2. 启动 FastAPI 服务
3. 自动打开浏览器
4. 可以扩展到系统托盘管理
"""
import os
import sys
import time
import socket
import webbrowser
import subprocess
import threading
import signal
from pathlib import Path

import uvicorn

from .config import PORT, HOST, DOWNLOAD_DIR, TEMP_DIR, VERSION, APP_NAME


def is_port_in_use(port: int) -> bool:
    """检测端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return False
        except OSError:
            return True


def find_existing_instance() -> bool:
    """检测是否已有实例在运行，如果是则打开浏览器指向已有实例"""
    if is_port_in_use(PORT):
        print(f"[{APP_NAME}] 检测到已有实例在运行，正在打开浏览器...")
        webbrowser.open(f"http://{HOST}:{PORT}")
        return True
    return False


def open_browser():
    """延迟打开浏览器，等待服务完全启动"""
    time.sleep(1.5)
    webbrowser.open(f"http://{HOST}:{PORT}")


def ensure_dirs():
    """确保下载目录和临时目录存在"""
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)


def run_server():
    """启动 FastAPI 服务"""
    print(f"""
╔══════════════════════════════════════════╗
║        🎵 {APP_NAME}  v{VERSION}            ║
║                                          ║
║  服务地址: http://{HOST}:{PORT}              ║
║  下载目录: {DOWNLOAD_DIR}
║                                          ║
║  浏览器将自动打开，如果没有请在浏览器输入  ║
║  上方地址。                               ║
║                                          ║
║  按 Ctrl+C 退出                          ║
╚══════════════════════════════════════════╝
""")

    # 服务启动后打开浏览器
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动 uvicorn
    uvicorn.run(
        "src.server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False,  # 打包后不用热重载
    )


def main():
    """主入口"""
    # 确保目录存在
    ensure_dirs()

    # 检测是否已有实例在运行
    if find_existing_instance():
        return

    # 启动服务
    run_server()


if __name__ == "__main__":
    main()
