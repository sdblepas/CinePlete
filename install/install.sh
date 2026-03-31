#!/usr/bin/env bash
# CinePlete — Generic installer for Debian/Ubuntu (LXC, VM, Raspberry Pi)
# Usage: curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | bash
#
# Environment variables (optional):
#   SKIP_SYSTEMD=1   — skip systemd registration (used by CI smoke test)
#   PORT=7474        — override listen port
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[CinePlete]${NC} $*"; }
success() { echo -e "${GREEN}[CinePlete]${NC} $*"; }
warn()    { echo -e "${YELLOW}[CinePlete]${NC} $*"; }
die()     { echo -e "${RED}[CinePlete] ERROR:${NC} $*" >&2; exit 1; }

# ── Config ────────────────────────────────────────────────────────────────────
APP_USER="cineplete"
APP_DIR="/opt/cineplete"
DATA_DIR="/data"
CONFIG_DIR="/config"
PORT="${PORT:-7474}"
SKIP_SYSTEMD="${SKIP_SYSTEMD:-0}"
REPO="https://github.com/sdblepas/CinePlete"
SERVICE_FILE="/etc/systemd/system/cineplete.service"

# ── Checks ────────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "Run as root (or with sudo)"

. /etc/os-release 2>/dev/null || true
if [[ "${ID:-}" != "debian" && "${ID:-}" != "ubuntu" && "${ID_LIKE:-}" != *"debian"* ]]; then
  warn "This script targets Debian/Ubuntu. Proceeding anyway — your mileage may vary."
fi

# ── Dependencies ──────────────────────────────────────────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
  python3 python3-pip python3-venv \
  git curl ca-certificates

# Ensure Python 3.11+
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
  PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  die "Python 3.11+ required (found $PY_VER). On older distros: apt install python3.11"
fi
info "Python $(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')") OK"

# ── User & directories ────────────────────────────────────────────────────────
info "Creating user and directories..."
id "$APP_USER" &>/dev/null || useradd -r -s /bin/false -m "$APP_USER"
mkdir -p "$APP_DIR" "$DATA_DIR" "$CONFIG_DIR"
chown -R "$APP_USER:$APP_USER" "$DATA_DIR" "$CONFIG_DIR"

# ── Fetch latest release ──────────────────────────────────────────────────────
info "Fetching latest release..."
LATEST=$(curl -fsSL "https://api.github.com/repos/sdblepas/CinePlete/releases/latest" \
  2>/dev/null | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/' || true)

if [[ -n "$LATEST" ]]; then
  info "Downloading release $LATEST..."
  curl -fsSL "$REPO/archive/refs/tags/${LATEST}.tar.gz" \
    | tar -xz --strip-components=1 -C "$APP_DIR"
else
  warn "No release found — cloning latest main branch..."
  if [[ -d "$APP_DIR/.git" ]]; then
    git -C "$APP_DIR" pull --quiet
  else
    git clone --depth 1 --quiet "$REPO" "$APP_DIR"
  fi
  LATEST="main"
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ── Python virtualenv + deps ──────────────────────────────────────────────────
info "Installing Python dependencies..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# ── Systemd service ───────────────────────────────────────────────────────────
if [[ "$SKIP_SYSTEMD" == "1" ]]; then
  warn "SKIP_SYSTEMD=1 — skipping systemd registration"
else
  info "Writing systemd service..."
  cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=CinePlete — Movie library gap finder
After=network.target
Wants=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment=DATA_DIR=$DATA_DIR
Environment=CONFIG_DIR=$CONFIG_DIR
Environment=STATIC_DIR=$APP_DIR/static
Environment=APP_VERSION=$LATEST
ExecStart=$APP_DIR/.venv/bin/uvicorn app.web:app --host 0.0.0.0 --port $PORT --workers 1
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now cineplete
fi

IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "YOUR_IP")
echo ""
success "CinePlete $LATEST installed successfully!"
echo -e "  ${CYAN}Web UI:${NC}   http://${IP}:${PORT}"
echo -e "  ${CYAN}Data:${NC}     $DATA_DIR"
echo -e "  ${CYAN}Config:${NC}   $CONFIG_DIR"
echo -e "  ${CYAN}Logs:${NC}     journalctl -u cineplete -f"
echo -e "  ${CYAN}Update:${NC}   curl -fsSL $REPO/raw/main/install/install.sh | bash"
echo ""
