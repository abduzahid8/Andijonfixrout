FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY client/ ./client/
COPY dashboard/ ./dashboard/
COPY mock_data.json init_db.py run_bot.py ./

RUN mkdir -p /data/uploads

ENV DATABASE_URL=sqlite:////data/roadpulse.db \
    MEDIA_DIR=/data/uploads

VOLUME ["/data"]
EXPOSE 8000

CMD ["sh", "-c", "python init_db.py && uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
