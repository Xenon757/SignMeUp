# SignMeUp: the Flask app with the built React page and every model baked in.

# 1) Build the web page.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) The app.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models/hf \
    STANZA_RESOURCES_DIR=/models/stanza \
    SIGNMEUP_POSE_MODEL=/models/mediapipe/holistic_landmarker.task \
    SIGNMEUP_CACHE_DIR=/data/cache \
    SIGNMEUP_UPLOAD_DIR=/tmp

# OpenCV, which MediaPipe pulls in, needs these system libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
# CPU-only PyTorch (needed by Stanza) is far smaller than the default GPU build.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt

# Download the speech, parsing and pose models now, so the server never waits for them.
COPY asl_util/ asl_util/
COPY scripts/ scripts/
RUN python scripts/download_models.py /models

COPY app.py ./
COPY static/ static/
COPY --from=frontend /frontend/dist frontend/dist

EXPOSE 8080
# One worker process: background jobs are tracked in memory and must be shared. Threads
# serve the page and progress polling while a job runs.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "600", "--bind", "0.0.0.0:8080", "app:create_app()"]
