FROM python:3.13-slim

# Install ADB
RUN apt-get update && apt-get install -y --no-install-recommends \
    adb \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (layer cache)
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev

# Copy source
COPY . .

EXPOSE 8000

CMD ["uv", "run", "main.py"]
