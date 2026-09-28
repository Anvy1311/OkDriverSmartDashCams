FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/okdriver.db

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY static ./static
COPY docs ./docs
COPY sql ./sql
COPY data ./data

RUN useradd --create-home --uid 10001 appuser && mkdir -p /data && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
