FROM python:3.13-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    android-tools-adb \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 下载 scrcpy-server
ARG SCRCPY_VERSION=2.3.1
RUN curl -L -o /app/scrcpy-server \
    https://github.com/Genymobile/scrcpy/releases/download/v${SCRCPY_VERSION}/scrcpy-server-v${SCRCPY_VERSION}

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制整个项目（包括 pyproject.toml, README.md, 源代码目录）
COPY . .

# 创建虚拟环境并安装依赖（现在能找到源代码了）
RUN uv venv && uv sync --no-dev

EXPOSE 8000
CMD ["uv", "run", "main.py"]
