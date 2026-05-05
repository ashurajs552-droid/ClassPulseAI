FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y \
    libgl1 libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 ffmpeg curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1
ENV PIP_DEFAULT_TIMEOUT=300
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt .

RUN pip install --upgrade pip

RUN pip install torch==2.2.0+cpu torchvision==0.17.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu \
    --no-cache-dir

RUN pip install tensorflow-cpu==2.15.0 --no-cache-dir

RUN pip install \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    opencv-python-headless==4.9.0.80 \
    mediapipe==0.10.9 \
    ultralytics==8.1.0 \
    supabase==2.3.4 \
    anthropic==0.18.1 \
    redis==5.0.1 \
    numpy==1.26.4 \
    pandas==2.2.0 \
    Pillow==10.2.0 \
    python-dotenv==1.0.1 \
    pydantic==2.6.0 \
    websockets==12.0 \
    tenacity==8.2.3 \
    python-multipart==0.0.9 \
    reportlab==4.1.0 \
    scikit-learn==1.4.0 \
    --no-cache-dir

RUN pip install deepface==0.0.89 \
    deep-sort-realtime==1.3.2 \
    --no-cache-dir

RUN pip uninstall -y \
    nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 \
    nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 \
    nvidia-cudnn-cu12 nvidia-cufft-cu12 \
    nvidia-curand-cu12 nvidia-cusolver-cu12 \
    nvidia-cusparse-cu12 nvidia-nccl-cu12 \
    nvidia-nvtx-cu12 triton \
    2>/dev/null || true

RUN find /usr/local/lib/python3.11 -name "*.pyc" -delete
RUN find /usr/local/lib/python3.11 -name "__pycache__" \
    -type d -exec rm -rf {} + 2>/dev/null || true

COPY backend/ .
RUN mkdir -p /app/models

EXPOSE 8000

ENV PORT=8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
