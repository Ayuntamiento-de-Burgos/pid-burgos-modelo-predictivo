# Módulo Sinergia · Modelo Predictivo (Prophet) — backend (modelo + API).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Madrid \
    PYTHONPATH=/app/src \
    CONFIG_DIR=/config

WORKDIR /app

# Dependencias de compilación para prophet/cmdstan + tzdata
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# prophet 1.1.6 trae su cmdstan bundled; cmdstanpy==1.2.4 lo acepta.
COPY . .
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Por defecto arranca el JOB del modelo. La API se lanza sobrescribiendo el
# command en docker-compose:  uvicorn api:app --host 0.0.0.0 --port 8000
ENTRYPOINT ["/app/entrypoint.sh"]
