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

# 入口脚本可执行
RUN chmod +x start.sh

# 环境变量
ENV RENDER=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Render 通过 PORT 环境变量指定端口
EXPOSE 10000

# 使用启动脚本（错误更可见）
CMD ["./start.sh"]
