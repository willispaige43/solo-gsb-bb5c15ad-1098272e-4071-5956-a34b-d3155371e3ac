FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite 数据库文件目录（compose 中挂载为命名卷以持久化）
RUN mkdir -p /data
ENV DB_PATH=/data/phase_allocations.db \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

EXPOSE 8000

# 应用启动时（FastAPI lifespan）自动建表，无需额外初始化命令
CMD ["sh", "-c", "uvicorn app.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT}"]
