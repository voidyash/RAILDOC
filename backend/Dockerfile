FROM python:3.11-slim

WORKDIR /app

# System deps: libgl/libglib are required by opencv-python
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Trained weights are baked into the image at /models (see docker-compose
# volume or the repo's models/ directory). Override RAILDOC_MODEL_DIR to
# point somewhere else; inference never retraining at startup.
ENV RAILDOC_MODEL_DIR=/models

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
