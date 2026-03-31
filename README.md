# 🎬 Cineplete — Plex & Jellyfin Movie Audit

[![Build & Publish Docker](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml/badge.svg)](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/sdblepas/cineplete)](https://hub.docker.com/r/sdblepas/cineplete)
[![Docker Image Version](https://img.shields.io/docker/v/sdblepas/cineplete/latest)](https://hub.docker.com/r/sdblepas/cineplete)
![License](https://img.shields.io/github/license/sdblepas/CinePlete)

![Python](https://img.shields.io/badge/python-3.11-blue)
![Self Hosted](https://img.shields.io/badge/self--hosted-ready-brightgreen)
![Multi-Arch](https://img.shields.io/badge/docker-multiarch-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-powered-green)
[![Playwright](https://img.shields.io/badge/tested%20with-Playwright-45ba4b?logo=playwright&logoColor=white)](https://playwright.dev)

![Plex](https://img.shields.io/badge/Plex-compatible-orange)
![Jellyfin](https://img.shields.io/badge/Jellyfin-compatible-7B2FBE)
![Radarr](https://img.shields.io/badge/Radarr-integration-purple)
![Overseerr](https://img.shields.io/badge/Overseerr-integration-F59E0B)
![Jellyseerr](https://img.shields.io/badge/Jellyseerr-integration-29B4E8)
![Watchtower](https://img.shields.io/badge/Watchtower-auto--update-2496ED)
![TMDB](https://img.shields.io/badge/TMDB-API-blue)
![Homelab](https://img.shields.io/badge/homelab-friendly-blue)
![Proxmox](https://img.shields.io/badge/Proxmox-LXC--ready-E57000?logo=proxmox&logoColor=white)
![GitHub Stars](https://img.shields.io/github/stars/sdblepas/CinePlete?style=social)

> 🇫🇷 [Version française](README.fr.md)

---

Ever wondered **which movies you're missing** from your favorite franchises, directors, or actors?

**Cineplete scans your Plex or Jellyfin library in seconds and shows exactly what's missing.**

✔ Missing movies from franchises
✔ Missing films from directors you collect
✔ Popular movies from actors already in your library
✔ Classic films missing from your collection
✔ Tailor-made suggestions based on your library

All in a **beautiful dashboard with charts and Radarr integration.**
Supports **both Plex and Jellyfin** — switchable from the Config tab.

![Cineplete Demo](assets/Demo.gif)

## Overview

**Cineplete** is a self-hosted Docker tool that scans your **Plex or Jellyfin** movie library and identifies:

- Missing movies from franchises
- Missing films from directors you already collect
- Popular films from actors already present in your library
- Classic movies missing from your collection
- Personalized suggestions based on what your library recommends
- Metadata issues (missing TMDB GUID or broken matches)
- Wishlist management
- Direct Radarr integration

The tool includes a **web UI dashboard with charts**, a **Logs tab** for diagnostics, and performs **ultra-fast library scans** (~2 seconds for Plex, depends on library size for Jellyfin).

---

## Features

### Media Server Support — Plex & Jellyfin

Cineplete supports two media servers. Switch between them from the **Config tab** — no restart needed.

| | Plex | Jellyfin |
|---|---|---|
| Scanner | Native XML API | Jellyfin HTTP API |
| Speed | ~2s for 1000 movies | Depends on library size |
| Credentials | URL + Token | URL + API Key |
| Library polling | ✔ | ✔ |
| Test Connection | ✔ | ✔ |

**Jellyfin setup:**
1. In Jellyfin, go to **Dashboard → API Keys** and create a new key for Cineplete.
2. In Cineplete Config, set `Media Server` to `Jellyfin`, enter the URL, API key, and library name.
3. Use the **Test Connection** button to verify before saving.

---

### Multiple Libraries Support

**New in v3.0:** Scan multiple libraries simultaneously — mix Plex and Jellyfin, or connect to multiple servers.

**Key features:**
- **Concurrent scanning** — all enabled libraries scanned in parallel using ThreadPoolExecutor
- **Merged results** — duplicates detected automatically across libraries (same TMDB ID)
- **Per-library toggle** — enable/disable individual libraries from the Config tab
- **Unified dashboard** — all charts and tabs show merged data from all active libraries
- **Progressive optimization** — unchanged libraries skip re-analysis (2-3 minutes → 2 seconds)

**Use cases:**
- Scan both Plex (main server) + Jellyfin (4K server)
- Multiple Plex servers (e.g. home + remote)
- Separate libraries (Movies + Anime + Foreign)
- Mix server types in one deployment

**Configuration:**

Libraries are managed from **Config → Libraries**. Each library has:
- **Type** — `plex` or `jellyfin`
- **Enabled** — toggle on/off without deleting credentials
- **Label** — friendly name (shown in scan progress)
- **Connection settings** — URL, token/API key, library name

**Example config.yml:**

```yaml
LIBRARIES:
  - id: "plex-main"
    type: "plex"
    enabled: true
    label: "Plex Main"
    url: "http://192.168.1.10:32400"
    token: "xxxxxxxxxxxx"
    library_name: "Movies"
    page_size: 500
    short_movie_limit: 60

  - id: "jellyfin-4k"
    type: "jellyfin"
    enabled: true
    label: "Jellyfin 4K"
    url: "http://192.168.1.20:8096"
    api_key: "xxxxxxxxxxxx"
    library_name: "Movies 4K"
    page_size: 500
    short_movie_limit: 60
```

**Auto-migration from v2.x:**

Legacy flat config (single `MEDIA_SERVER` setting) automatically migrates to the new `LIBRARIES` list format on first startup. No manual action required — your existing setup continues to work.

**Performance:**

With 2 libraries (1000 movies each):
- Sequential: 4 seconds (Plex) + 6 seconds (Jellyfin) = 10 seconds
- **Concurrent: ~6 seconds** (parallel scan)

---

### Ultra Fast Plex Scanner

The scanner uses the **native Plex XML API** instead of slow metadata requests.

Performance example:

- 1000 movies → ~2 seconds
- 3000 movies → ~4 seconds

---

### Dashboard

The dashboard shows a full visual overview of your library:

**Score cards:**
- Franchise Completion %
- Directors Score %
- Classics Coverage %
- Global Cinema Score %

**Charts (Chart.js):**
- Franchise Status — doughnut: Complete / Missing 1 / Missing 2+
- Classics Coverage — doughnut: In library vs missing
- Metadata Health — doughnut: Valid TMDB / No GUID / No Match
- Top 10 Actors in library — horizontal bar
- Directors by missing films — grouped bar (0 / 1–2 / 3–5 / 6–10 / 10+)
- Library Stats panel

Ignored franchises are excluded from the Franchise Status chart automatically.

---

### Franchises

Detects **TMDB collections (sagas)** and lists missing films.

Example:

```
Alien Collection (6/7)
Missing: Alien Romulus
```

---

### Directors

Detects missing films from directors already in your library.

Example:

```
Christopher Nolan
Missing: Following, Insomnia
```

---

### Actors

Finds **popular films of actors already in your Plex library**.

Filter criteria:

```
vote_count >= 500
```

Sorted by popularity, vote_count, vote_average.

---

### Classics

Detects missing films from **TMDB Top Rated**.

Default criteria:

```
vote_average >= 8.0
vote_count >= 5000
```

---

### Suggestions

Personalized movie recommendations based on **your own library**.

For each film in your Plex library, Cineplete fetches TMDB recommendations and scores each suggested title by how many of your films recommended it. A film recommended by 30 of your movies ranks higher than one recommended by 2.

Each suggestion card shows a **⚡ N matches** badge so you can see at a glance how strongly your library points to it.

API calls are cached permanently — only newly added films incur real HTTP calls on subsequent scans.

---

### Wishlist

Interactive wishlist with UI buttons on every movie card.

Movies can be added from any tab: franchises, directors, actors, classics, suggestions.

Wishlist is stored in:

```
data/overrides.json
```

---

### Metadata Diagnostics

**No TMDB GUID** — Movies without TMDB metadata.  
Fix inside Plex: `Fix Match → TheMovieDB`

**TMDB No Match** — Films with an invalid TMDB ID that returns no data. The Plex title is shown so you can identify the film immediately.  
Fix: Refresh metadata or fix match manually in Plex.

---

### Ignore System

Permanently ignore franchises, directors, actors, or specific movies via UI buttons.
Ignored items are excluded from all lists and charts.

**Movie-level ignore** — every movie card now has a 🚫 button. Ignored movies appear in a dedicated **Ignored** tab where they can be restored with one click. Metadata (title, year, poster) is stored so the Ignored tab displays properly even before a rescan.

Stored in:

```
data/overrides.json
```

---

### Letterboxd Tab

Import and browse movies from any public Letterboxd URL — watchlists, named lists, diary feeds, or curator profile RSS feeds.

**Features:**
- Add multiple URLs — each is fetched and merged into a single scored grid
- Movies appearing in more than one list get a **×N** badge and are sorted to the top
- Movies already in your library are automatically filtered out
- ↻ refresh button to re-fetch all lists on demand
- URLs are persisted in `overrides.json` and survive container restarts

**Supported URL formats:**

| URL | RSS used |
|-----|----------|
| `letterboxd.com/you/watchlist/` | `/watchlist/rss/` |
| `letterboxd.com/you/list/my-list/` | `/list/my-list/rss/` |
| `letterboxd.com/you/rss/` | used as-is (diary) |
| `letterboxd.com/you/films/` | falls back to diary `/rss/` |
| curator profile RSS (e.g. `/mscorsese/rss/`) | auto-expanded — each linked list's RSS is fetched individually |

> All lists must be public. Private Letterboxd accounts or patron-only lists are not accessible.

---

### FlareSolverr Integration

Some Letterboxd list RSS feeds are protected by Cloudflare (403). If you run [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) in your stack, CinePlete will automatically route blocked requests through it.

Configure the URL in **Config → FlareSolverr** (e.g. `http://flaresolverr:8191`). When a direct fetch returns 403, CinePlete retries via FlareSolverr transparently — no changes needed to your Letterboxd URLs.

```yaml
flaresolverr:
  image: ghcr.io/flaresolverr/flaresolverr:latest
  container_name: flaresolverr
  ports:
    - "8191:8191"
  restart: unless-stopped
```

---

### Search, Filter & Sort

All tabs support live filtering:

- **Search** by title or group name (director / actor / franchise)
- **Year filter** — 2020s / 2010s / 2000s / 1990s / Older
- **Sort** — popularity / rating / votes / year / title

---

### Async Scan with Progress

Clicking **Rescan** launches a background scan immediately without blocking the UI.

A live progress card appears showing:

```
Step 3/8 — Analyzing collections
[=====>      ] 43%
```

The progress card disappears automatically when the scan completes.

Only one scan can run at a time. Concurrent scan requests are rejected cleanly.

---

### Logs

A dedicated **Logs tab** shows the last 200 lines of `/data/cineplete.log` with color-coded severity levels (ERROR in red, WARNING in amber). Useful for diagnosing scan issues, TMDB API errors, and Plex connectivity problems.

The log file rotates automatically (2 MB × 3 files) and never fills your disk.

---

### Version Notifications

CinePlete checks the [GitHub Releases](https://github.com/sdblepas/CinePlete/releases) API once per hour. When a new version is available, a banner appears in the sidebar below the current version with a direct link to the release notes.

---

### Smart Authentication

CinePlete supports Radarr-style authentication, configurable from **Config → Authentication**.

| Mode | Behaviour |
|------|-----------|
| **None** | Open access — no login required (default) |
| **Forms** | Username + password required for all access |
| **Local network free** | No auth on local IPs (`10.x`, `192.168.x`, `127.x`), login required from internet |

- Passwords hashed with **PBKDF2-SHA256** — never stored in plain text
- **7-day sliding session cookie** — stay logged in across browser sessions
- **"Trust this browser"** toggle — persistent vs session cookie
- API key auth via `X-Api-Key` header or `?access_token=` query param (for integrations)
- Logout button in the sidebar footer

> Auth defaults to **None** — existing deployments are unaffected until you configure it.

---

### Auto-Update via Watchtower

CinePlete can automatically update itself using [Watchtower](https://containrrr.dev/watchtower/).

Configure it from the **Config → Watchtower** section:
- Toggle **Auto-update enabled**
- Set the **Watchtower URL** (e.g. `http://10.0.0.1:8081`)
- Set the **API Token** (matches `WATCHTOWER_HTTP_API_TOKEN` on your Watchtower container)
- Click **Update Now** to trigger an immediate pull & restart

Watchtower docker-compose example:
```yaml
watchtower:
  image: containrrr/watchtower
  environment:
    - WATCHTOWER_HTTP_API_UPDATE=true
    - WATCHTOWER_HTTP_API_TOKEN=your_token_here
    - WATCHTOWER_HTTP_API_PERIODIC_POLLS=true  # enable scheduled + on-demand
    - WATCHTOWER_POLL_INTERVAL=86400           # 24h auto-check
    - WATCHTOWER_CLEANUP=true
  ports:
    - "8081:8080"
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  restart: unless-stopped
```

> The `?scope=cineplete` parameter ensures only CinePlete is updated. Add `com.centurylinklabs.watchtower.scope=cineplete` to your CinePlete container labels (already included in the docker-compose example above).

---

### Radarr Integration

Movies can be added to Radarr with one click from any movie card.

**Important:** `searchForMovie = false`
- ✔ Movie is added to Radarr
- ✘ Download is NOT started automatically

---

## Configuration

Configuration is stored in `config/config.yml` and editable from the **Config** tab in the UI.

**Basic settings:**

| Key | Description |
|-----|-------------|
| `TMDB_API_KEY` | TMDB classic API Key (v3) — **not** the Read Access Token |

> ⚠️ Use the **API Key** found under TMDB → Settings → API → **API Key** (short alphanumeric string starting with letters/numbers). Do **not** use the Read Access Token (long JWT string starting with `eyJ`).

**Libraries (v3.0+):**

Libraries are configured from **Config → Libraries** in the UI. Each library entry includes:

| Key | Required | Description |
|-----|----------|-------------|
| `id` | Yes | Unique identifier (e.g. `plex-0`, `jellyfin-4k`) |
| `type` | Yes | `plex` or `jellyfin` |
| `enabled` | Yes | `true` to scan, `false` to skip |
| `label` | No | Friendly name shown in scan progress |
| `url` | Yes | Server URL (e.g. `http://192.168.1.10:32400`) |
| `token` | Plex only | Plex authentication token |
| `api_key` | Jellyfin only | Jellyfin API key |
| `library_name` | Yes | Name of the movie library |
| `page_size` | No | API page size (default: 500) |
| `short_movie_limit` | No | Skip films shorter than N minutes (default: 60) |

**Example multi-library config:**

```yaml
LIBRARIES:
  - id: "plex-main"
    type: "plex"
    enabled: true
    label: "Plex Main"
    url: "http://192.168.1.10:32400"
    token: "xxxxxxxxxxxx"
    library_name: "Movies"

  - id: "jellyfin-4k"
    type: "jellyfin"
    enabled: false
    label: "Jellyfin 4K"
    url: "http://192.168.1.20:8096"
    api_key: "xxxxxxxxxxxx"
    library_name: "Movies 4K"
```

> **Legacy config (v2.x):** Flat `PLEX_URL`, `PLEX_TOKEN`, `JELLYFIN_URL` settings still work and auto-migrate to `LIBRARIES` format on first load.

**Advanced settings** (accessible via the UI "Advanced settings" section):

| Key | Default | Description |
|-----|---------|-------------|
| `CLASSICS_PAGES` | 4 | Number of TMDB Top Rated pages to fetch |
| `CLASSICS_MIN_VOTES` | 5000 | Minimum vote count for classics |
| `CLASSICS_MIN_RATING` | 8.0 | Minimum rating for classics |
| `CLASSICS_MAX_RESULTS` | 120 | Maximum classic results to return |
| `ACTOR_MIN_VOTES` | 500 | Minimum votes for an actor's film to appear |
| `ACTOR_MAX_RESULTS_PER_ACTOR` | 10 | Max missing films shown per actor |
| `PLEX_PAGE_SIZE` | 500 | Plex API page size |
| `JELLYFIN_PAGE_SIZE` | 500 | Jellyfin API page size |
| `SHORT_MOVIE_LIMIT` | 60 | Films shorter than this (minutes) are ignored |
| `SUGGESTIONS_MAX_RESULTS` | 100 | Maximum suggestions to return |
| `SUGGESTIONS_MIN_SCORE` | 2 | Minimum number of your films that must recommend a suggestion |

---

## Installation

### Option 1 — Generic LXC / VM / Bare Metal (Debian · Ubuntu · Raspberry Pi)

One-liner — run inside your container or VM:

```bash
curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | sudo bash
```

What it does: installs Python 3.11+, creates a dedicated `cineplete` user, downloads the latest release, sets up a Python virtualenv, and registers a systemd service that starts automatically on boot.

**Re-running the same command acts as an update.**

Post-install management:
```bash
journalctl -u cineplete -f          # live logs
systemctl restart cineplete          # restart
systemctl status cineplete           # status
```

---

### Option 2 — Proxmox LXC (one command on the Proxmox host)

Run this **on your Proxmox host** as root — it creates a fresh unprivileged Debian 12 LXC and installs CinePlete inside it automatically:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/proxmox-lxc.sh)"
```

**With custom options:**
```bash
CT_ID=200 CT_IP=192.168.1.50/24 CT_GW=192.168.1.1 CT_RAM=1024 \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/proxmox-lxc.sh)"
```

| Variable | Default | Description |
|----------|---------|-------------|
| `CT_ID` | next available | LXC container ID |
| `CT_IP` | `dhcp` | Static IP in CIDR notation (e.g. `192.168.1.50/24`) |
| `CT_GW` | _(none)_ | Gateway for static IP |
| `CT_CORES` | `2` | CPU cores |
| `CT_RAM` | `512` | RAM in MB |
| `CT_DISK` | `4` | Disk in GB |
| `CT_BRIDGE` | `vmbr0` | Network bridge |
| `PORT` | `7474` | App listen port |

Post-install management from the Proxmox host:
```bash
pct exec <CT_ID> -- journalctl -u cineplete -f     # live logs
pct exec <CT_ID> -- bash                            # open shell
# Update:
pct exec <CT_ID> -- bash -c "curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | bash"
```

---

### Option 3 — Docker Compose (recommended)

```yaml
version: "3.9"
services:
  cineplete:
    image: sdblepas/cineplete:latest
    container_name: cineplete
    ports:
      - "8787:8787"
    volumes:
      - /path/to/config:/config
      - /path/to/data:/data
    labels:
      net.unraid.docker.webui: "http://[IP]:[PORT:8787]"
      net.unraid.docker.icon: "https://raw.githubusercontent.com/sdblepas/CinePlete/main/assets/icon.png"
      org.opencontainers.image.url: "http://localhost:8787"
      com.centurylinklabs.watchtower.scope: "cineplete"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8787')"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 20s
    restart: unless-stopped
```

**Port conflict?** Add `APP_PORT` to change the internal port:

```yaml
environment:
  - APP_PORT=8788
ports:
  - "8788:8788"
```

Start:

```bash
docker compose up -d
```

Open UI:

```
http://YOUR_NAS_IP:8787
```

---

## Project Structure

```
CinePlete/
├── .github/
│   └── workflows/
│       └── docker.yml        # CI/CD pipeline (scan → test → version → build)
├── app/
│   ├── web.py                # FastAPI backend + all API endpoints
│   ├── scanner.py            # 8-step scan engine (threaded)
│   ├── plex_xml.py           # Plex XML API scanner
│   ├── jellyfin_api.py       # Jellyfin HTTP API scanner
│   ├── scheduler.py          # Library auto-poll scheduler (Plex & Jellyfin)
│   ├── tmdb.py               # TMDB API client (cached, key-safe, error logging)
│   ├── overrides.py          # Ignore/wishlist/rec_fetched_ids helpers
│   ├── config.py             # Config loader/saver with deep-merge
│   └── logger.py             # Shared rotating logger (console + file)
├── static/
│   ├── index.html            # Single-page app shell + all CSS
│   └── app.js                # All UI logic: routing, rendering, API calls
├── assets/
│   └── icon.png              # App icon (used by Unraid WebUI label)
├── config/
│   └── config.yml            # Default config template
├── tests/
│   ├── test_config.py
│   ├── test_jellyfin_api.py  # 16 unit tests for Jellyfin scanner
│   ├── test_overrides.py
│   ├── test_scheduler.py
│   └── test_scoring.py
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## Data Files

All persistent data lives in the mounted `/data` volume and survives container updates:

| File | Description |
|------|-------------|
| `results.json` | Full scan output — regenerated on each scan |
| `tmdb_cache.json` | TMDB API response cache — persists between scans |
| `overrides.json` | Ignored items, wishlist, rec_fetched_ids |
| `cineplete.log` | Rotating log file (2 MB × 3 files) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/version` | Returns current app version |
| GET | `/api/results` | Returns scan results (never blocks) |
| POST | `/api/scan` | Starts a background scan |
| GET | `/api/scan/status` | Returns live scan progress (8 steps) |
| GET | `/api/config` | Returns current config |
| POST | `/api/config` | Saves config |
| GET | `/api/config/status` | Returns `{configured: bool}` |
| POST | `/api/ignore` | Ignores a movie / franchise / director / actor |
| POST | `/api/unignore` | Removes an ignore |
| GET | `/api/ignored` | Returns ignored movies with title/year/poster metadata |
| POST | `/api/wishlist/add` | Adds a movie to wishlist |
| POST | `/api/wishlist/remove` | Removes from wishlist |
| POST | `/api/radarr/add` | Sends a movie to Radarr |
| POST | `/api/jellyfin/test` | Tests Jellyfin connectivity and library access |
| GET | `/api/logs` | Returns last N lines of cineplete.log |
| POST | `/api/watchtower/update` | Triggers Watchtower to pull latest CinePlete image |
| GET | `/api/auth/status` | Returns current auth mode and login state |
| POST | `/api/auth/login` | Authenticates with username + password |
| POST | `/api/auth/logout` | Clears the session cookie |
| GET | `/api/letterboxd/urls` | Returns saved Letterboxd URLs |
| POST | `/api/letterboxd/urls` | Adds a Letterboxd URL |
| POST | `/api/letterboxd/urls/remove` | Removes a Letterboxd URL |
| GET | `/api/letterboxd/movies` | Fetches, merges and scores all saved Letterboxd lists |

---

## Technologies

- Python 3.11
- FastAPI + Uvicorn
- Docker (multi-arch: amd64 + arm64)
- TMDB API v3
- Plex XML API
- Jellyfin HTTP API (Emby-compatible)
- Chart.js
- Tailwind CSS (CDN)

---

## Architecture

```
Plex Server                        Jellyfin Server
     │                                    │
     │ XML API (~2s/1000 movies)          │ HTTP REST API (paginated)
     ▼                                    ▼
 plex_xml.py                      jellyfin_api.py
  (TMDB IDs, directors,           (TMDB IDs, directors,
   actors, duplicates)             actors, top 5/film)
          \                              /
           └──────── scan_movies() ─────┘
                           │
                           ▼
            8-Step Scan Engine — scanner.py (background thread)
                           │
     ┌─────────────────────┼──────────────────────┐
     ▼                     ▼                       ▼
 Franchises            Directors               Actors
 (TMDB collections)    (person_credits)        (vote_count ≥ 500)
     │                     │                       │
     └─────────── TMDB API client — tmdb.py ───────┘
                  (thread-safe, disk-cached,
                   key-normalized, flush/50 calls)
                           │
     ┌─────────────────────┼──────────────────────┐
     ▼                     ▼                       ▼
  Classics             Suggestions             Scores
 (Top Rated TMDB)    (recommendations        (franchise / directors /
                      scored by library       classics / global)
                      match count)
                           │
                           ▼
                     results.json ◄──── overrides.json
                     (/data volume)     (wishlist, ignores,
                           │            letterboxd_urls,
                           ▼            rec_fetched_ids)
                   FastAPI — web.py
                   (42 API endpoints)
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
    Radarr / 4K      Overseerr /         Letterboxd
    (add, status,    Jellyseerr          (RSS → TMDB,
     grab poller)    (request)           multi-URL merge,
         │                               FlareSolverr)
         ▼
    Telegram
    (scan summary +
     grab notifications)
                           │
                           ▼
         Single-page app — static/js/
    ┌────────┬────────┬────────┬─────────┬─────────┬────────┬────────┐
    │ app.js │scan.js │ api.js │render.js│config.js│filters │modal.js│
    │routing │polling │ fetch  │tabs /   │config   │search/ │detail  │
    │state   │progress│toast   │cards /  │form /   │filter/ │modal / │
    │nav     │badges  │utils   │charts   │cache    │sort    │trailer │
    └────────┴────────┴────────┴─────────┴─────────┴────────┴────────┘
```

---
