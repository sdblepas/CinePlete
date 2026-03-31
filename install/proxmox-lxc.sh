#!/usr/bin/env bash
# CinePlete — Proxmox LXC creator
# Run on your Proxmox HOST (not inside a container)
# Usage: bash -c "$(curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/proxmox-lxc.sh)"
#
# Environment variables (optional):
#   CT_ID=200              — LXC container ID (default: next available)
#   CT_IP=192.168.1.50/24 — static IP (default: dhcp)
#   CT_GW=192.168.1.1     — gateway for static IP
#   CT_CORES=2             — CPU cores (default: 2)
#   CT_RAM=512             — RAM in MB (default: 512)
#   CT_DISK=4              — disk in GB (default: 4)
#   CT_BRIDGE=vmbr0        — network bridge (default: vmbr0)
#   PORT=7474              — app port (default: 7474)
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[CinePlete]${NC} $*"; }
success() { echo -e "${GREEN}[CinePlete]${NC} $*"; }
warn()    { echo -e "${YELLOW}[CinePlete]${NC} $*"; }
die()     { echo -e "${RED}[CinePlete] ERROR:${NC} $*" >&2; exit 1; }

# ── Config ────────────────────────────────────────────────────────────────────
CT_ID="${CT_ID:-$(pvesh get /cluster/nextid 2>/dev/null || echo 200)}"
CT_HOSTNAME="cineplete"
CT_CORES="${CT_CORES:-2}"
CT_RAM="${CT_RAM:-512}"
CT_DISK="${CT_DISK:-4}"
CT_BRIDGE="${CT_BRIDGE:-vmbr0}"
CT_IP="${CT_IP:-dhcp}"
CT_GW="${CT_GW:-}"
PORT="${PORT:-7474}"
TEMPLATE="debian-12-standard"

# ── Checks ────────────────────────────────────────────────────────────────────
command -v pct   &>/dev/null || die "pct not found — run this script on your Proxmox host"
command -v pvesh &>/dev/null || die "pvesh not found — run this script on your Proxmox host"
[[ $EUID -ne 0 ]] && die "Run as root on the Proxmox host"

# ── Find template storage ─────────────────────────────────────────────────────
info "Locating template storage..."
STORAGE=$(pvesm status -content vztmpl 2>/dev/null | awk 'NR==2{print $1}')
[[ -z "$STORAGE" ]] && die "No storage with 'vztmpl' content found. Configure one in Proxmox first."

# ── Download template if missing ──────────────────────────────────────────────
TMPL_PATH=$(pveam list "$STORAGE" 2>/dev/null | grep "$TEMPLATE" | tail -1 | awk '{print $1}' || true)
if [[ -z "$TMPL_PATH" ]]; then
  info "Downloading $TEMPLATE template..."
  pveam update
  AVAIL=$(pveam available 2>/dev/null | grep "$TEMPLATE" | tail -1 | awk '{print $1}')
  [[ -z "$AVAIL" ]] && die "Template $TEMPLATE not available. Check: pveam available"
  pveam download "$STORAGE" "$AVAIL"
  TMPL_PATH=$(pveam list "$STORAGE" | grep "$TEMPLATE" | tail -1 | awk '{print $1}')
fi
info "Template: $TMPL_PATH"

# ── Create LXC ────────────────────────────────────────────────────────────────
info "Creating LXC $CT_ID ($CT_HOSTNAME)..."

NET_CFG="name=eth0,bridge=${CT_BRIDGE}"
if [[ "$CT_IP" == "dhcp" ]]; then
  NET_CFG+=",ip=dhcp"
else
  NET_CFG+=",ip=${CT_IP}"
  [[ -n "$CT_GW" ]] && NET_CFG+=",gw=${CT_GW}"
fi

pct create "$CT_ID" "$TMPL_PATH" \
  --hostname    "$CT_HOSTNAME" \
  --cores       "$CT_CORES" \
  --memory      "$CT_RAM" \
  --rootfs      "local-lxc:${CT_DISK}" \
  --net0        "$NET_CFG" \
  --unprivileged 1 \
  --features    nesting=1 \
  --start       1

info "Waiting for LXC to boot..."
sleep 5

# ── Run generic installer inside the LXC ─────────────────────────────────────
info "Running CinePlete installer inside LXC $CT_ID..."
pct exec "$CT_ID" -- bash -c \
  "curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | bash"

# ── Done ──────────────────────────────────────────────────────────────────────
CT_IP_REAL=$(pct exec "$CT_ID" -- hostname -I 2>/dev/null | awk '{print $1}')
echo ""
success "LXC $CT_ID ready!"
echo -e "  ${CYAN}Web UI:${NC}   http://${CT_IP_REAL}:${PORT}"
echo -e "  ${CYAN}Shell:${NC}    pct exec $CT_ID -- bash"
echo -e "  ${CYAN}Logs:${NC}     pct exec $CT_ID -- journalctl -u cineplete -f"
echo -e "  ${CYAN}Update:${NC}   pct exec $CT_ID -- bash -c 'curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | bash'"
echo ""
