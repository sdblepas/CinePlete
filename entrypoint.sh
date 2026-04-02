#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Starting CinePlete with UID=${PUID} GID=${PGID}"

# Remap the cineplete group and user to match the host PGID/PUID
groupmod -o -g "$PGID" cineplete
usermod  -o -u "$PUID" cineplete

# Fix ownership of writable directories
chown -R cineplete:cineplete /data /config

# Drop privileges and start the app
exec gosu cineplete uvicorn app.web:app --host 0.0.0.0 --port 8787
