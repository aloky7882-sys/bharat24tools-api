FROM python:3.11-slim

# Install system dependencies (Ghostscript, qpdf, poppler)
RUN apt-get update && apt-get install -y \
    ghostscript \
    qpdf \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Render uses $PORT)
EXPOSE 10000

# Run with gunicorn
CMD gunicorn app:app --timeout 180 --workers 1 --bind 0.0.0.0:$PORT