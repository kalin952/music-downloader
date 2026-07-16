"""
Music Downloader — PyInstaller 桌面版入口
此文件作为 PyInstaller 打包的主入口点
"""
import sys
import os

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.launcher import main

if __name__ == "__main__":
    main()
