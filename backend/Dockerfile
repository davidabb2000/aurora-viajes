FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY modelos ./modelos

ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV ENTORNO=produccion
ENV DEPURACION=false
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\", \"8000\")}/api/health')"
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"
