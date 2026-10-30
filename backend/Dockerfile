FROM python:3.12-slim
LABEL org.opencontainers.image.source=https://github.com/latebkb/S.A.L.O.P.E

WORKDIR /app

# System deps for psycopg2, Pillow, and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    fonts-dejavu-core \
    tesseract-ocr \
    tesseract-ocr-fra \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
