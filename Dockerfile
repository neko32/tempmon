FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for opencv
# opencv-python-headless often requires these shared libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the scanner directory
COPY scanner/ scanner/

# Create a directory for scanned images
RUN mkdir -p /app/scans

# Default entrypoint
CMD ["python", "scanner/main.py"]
