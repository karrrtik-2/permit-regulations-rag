FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SDL_AUDIODRIVER=dummy \
    SDL_VIDEODRIVER=dummy

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    curl \
    ffmpeg \
    libasound2 \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY assistant ./assistant
COPY config ./config
COPY db ./db
COPY pipelines ./pipelines
COPY services ./services
COPY utils ./utils
COPY data ./data

RUN pip install --upgrade pip setuptools wheel && \
    pip install -e .

CMD ["python", "-m", "assistant.voice_app"]
