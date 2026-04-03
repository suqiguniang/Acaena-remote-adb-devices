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

# 复制 pyproject.toml 和 README.md（hatchling 构建时需要）
COPY pyproject.toml README.md ./
# 如果项目有 LICENSE 文件也复制（可选）
COPY LICENSE* ./

# 创建虚拟环境并安装依赖
RUN uv venv && uv sync --no-dev

# 复制项目其余代码
COPY . .

EXPOSE 8000
CMD ["uv", "run", "main.py"]
