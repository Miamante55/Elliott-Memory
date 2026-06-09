# ============================================================
# Ombre Brain Docker Build
# Docker 构建文件
#
# Build: docker build -t ombre-brain .
# Run:   docker run -e OMBRE_API_KEY=your-key -p 8000:8000 ombre-brain
# ============================================================

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (leverage Docker cache)
# 先装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files / 复制项目文件
COPY *.py .
COPY scripts ./scripts
COPY dashboard.html .
COPY config.example.yaml ./config.yaml
COPY render-nginx.conf /etc/nginx/nginx.conf
COPY start-render.sh /app/start-render.sh
RUN chmod +x scripts/*.sh /app/start-render.sh

# Persistent mount point: bucket data
# 持久化挂载点：记忆数据
VOLUME ["/var/data"]

# Default to streamable-http for container (remote access)
# 容器场景默认用 streamable-http
ENV OMBRE_TRANSPORT=streamable-http
ENV OMBRE_BUCKETS_DIR=/var/data/buckets
ENV OMBRE_STATE_DIR=/var/data/state
ENV OMBRE_GATEWAY_HOST=127.0.0.1
ENV OMBRE_GATEWAY_PORT=8010
ENV OMBRE_GATEWAY_ADMIN_URL=http://127.0.0.1:8010/api/config

EXPOSE 10000

CMD ["/app/start-render.sh"]
