FROM python:3.11-slim

# Instala Chromium (compatível com ARM e x86)
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY coletor_blaze.py .

ENV PYTHONUNBUFFERED=1
ENV CHROMIUM_FLAGS="--no-sandbox --disable-dev-shm-usage"

CMD ["python3", "coletor_blaze.py"]