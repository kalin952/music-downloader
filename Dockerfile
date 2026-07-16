FROM python:3.11-slim

# 安装 ffmpeg（B站下载必需）
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建下载目录
RUN mkdir -p /tmp/md_downloads /tmp/md_temp

# 环境变量
ENV RENDER=1
ENV PYTHONUNBUFFERED=1

# Render 通过 PORT 环境变量指定端口
EXPOSE 10000

# 使用 uvicorn 直接启动（SSE 需要单 worker）
CMD uvicorn src.server:app --host 0.0.0.0 --port ${PORT:-10000} --timeout-keep-alive 300
