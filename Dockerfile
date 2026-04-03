FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖（ADB 和 curl）
RUN apt-get update && apt-get install -y \
    android-tools-adb \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 下载 scrcpy-server（版本需与 .env 中的 SCRCPY_VERSION 一致）
ARG SCRCPY_VERSION=2.3.1
RUN curl -L -o /app/scrcpy-server \
    https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/scrcpy-server-v${SCRCPY_VERSION}

# 安装 uv
RUN pip install --no-cache-dir uv

# 先只复制 pyproject.toml（利用 Docker 层缓存）
COPY pyproject.toml ./

# 创建虚拟环境并安装依赖（uv 会自动生成 uv.lock）
RUN uv venv && uv sync --no-dev

# 复制项目其余代码
COPY . .

# 暴露 WebSocket 和 Web 端口（根据项目实际端口调整，默认 8000）
EXPOSE 8000

# 启动命令（使用 uv 运行）
CMD ["uv", "run", "main.py"]
