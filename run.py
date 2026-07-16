#!/usr/bin/env python3
"""
Music Downloader — 开发环境运行入口
用法: python run.py
"""
import sys
import os

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.launcher import main

if __name__ == "__main__":
    main()
