FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Pillow
RUN apt-get update && apt-get install -y \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .

# ✅ KEY FIX: --no-cache-dir prevents pip from storing downloads in RAM/disk cache
# ✅ --default-timeout=100 prevents hanging on slow connections
RUN pip install --no-cache-dir --default-timeout=100 -r requirements-server.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--workers", "1"]