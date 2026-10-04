FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ghostscript \
    qpdf \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD gunicorn app:app --timeout 300 --workers 1 --bind 0.0.0.0:$PORT