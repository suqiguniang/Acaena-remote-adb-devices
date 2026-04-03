# 基础镜像
FROM python:3.11-slim

# 工作目录
WORKDIR /app

# 系统依赖：安装 adb 工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    adb \
    && rm -rf /var/lib/apt/lists/*

# 复制项目依赖文件
COPY pyproject.toml ./

# 安装 Python 依赖（兼容无 uv.lock 场景）
RUN pip install --no-cache-dir -e .

# 复制全部项目代码
COPY . .

# 暴露端口（根据项目默认端口）
EXPOSE 5810 8000

# 启动命令
CMD ["python", "app.py"]
