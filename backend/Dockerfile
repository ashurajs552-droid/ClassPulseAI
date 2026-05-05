FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV, MediaPipe, and other CV libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (cache layer)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ .

# Create required directories
RUN mkdir -p logs models model_cache

EXPOSE 8000

CMD ["python", "main.py"]
