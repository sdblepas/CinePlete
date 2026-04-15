FROM python:3.11-slim

ARG VERSION=dev
ENV APP_VERSION=$VERSION

WORKDIR /app

# Install system deps and Python packages first — these layers are cached
# independently of app code, so they won't re-run on every code change.
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gosu && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app code last — changes here won't bust the pip/apt cache layers above.
COPY app /app/app
COPY static /app/static
COPY config /app/config
COPY entrypoint.sh /entrypoint.sh

RUN useradd -m -u 1000 cineplete && \
    mkdir -p /data /config && \
    chown -R cineplete:cineplete /app /data /config && \
    chmod +x /entrypoint.sh

EXPOSE 8787

# NOTE: We intentionally do not set USER here. The entrypoint uses gosu to
# drop from root to the cineplete user (UID/GID remapped to match host PUID/PGID).
# Setting USER would prevent the groupmod/usermod/chown calls the entrypoint needs.
# The app itself always runs as non-root — see entrypoint.sh.
ENTRYPOINT ["/entrypoint.sh"]
