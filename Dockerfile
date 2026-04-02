FROM python:3.11-slim

ARG VERSION=dev
ENV APP_VERSION=$VERSION

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY app /app/app
COPY static /app/static
COPY config /app/config

COPY entrypoint.sh /entrypoint.sh

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /app/requirements.txt

RUN useradd -m -u 1000 cineplete && \
    mkdir -p /data /config && \
    chown -R cineplete:cineplete /app /data /config && \
    chmod +x /entrypoint.sh

EXPOSE 8787

ENTRYPOINT ["/entrypoint.sh"]