# syntax=docker/dockerfile:1.7

FROM python:3.14.0-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        gcc \
        make \
        pkg-config \
        python3-dev \
        curl \
        unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir=/wheels -r requirements.txt

RUN BITWARDEN_VERSION="2025.11.0" \
    && BITWARDEN_SHA256="943f0107b3a471e7376b08f118e21a59583afeb49e4eb86f378e3b0d7c79c969" \
    && curl -fsSL \
        "https://github.com/bitwarden/clients/releases/download/cli-v${BITWARDEN_VERSION}/bw-linux-${BITWARDEN_VERSION}.zip" \
        -o /tmp/bw.zip \
    && echo "${BITWARDEN_SHA256}  /tmp/bw.zip" | sha256sum -c - \
    && unzip /tmp/bw.zip -d /tmp/bw \
    && install -m 0755 /tmp/bw/bw /usr/local/bin/bw \
    && rm -rf /tmp/bw /tmp/bw.zip


FROM python:3.14.0-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libffi8 \
        libssl3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/bw /usr/local/bin/bw
COPY --from=builder /wheels /wheels

COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

COPY app/ ./app/

RUN useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2).read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
