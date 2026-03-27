# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CinePlete is a self-hosted Docker tool that scans Plex or Jellyfin movie libraries and identifies missing content:
- Missing movies from franchises (TMDB collections)
- Missing films from directors/actors in your library
- Classic films (TMDB Top Rated)
- Personalized suggestions based on library recommendations
- Metadata diagnostics (missing TMDB GUIDs)
- Radarr integration for adding movies
- Telegram notifications for scan results

## Development Commands

### Running Tests
```bash
# Unit tests (Python)
pytest --tb=short -v

# E2E tests (Playwright) — requires the app to be running on port 8787
cd e2e && npm ci && npx playwright install --with-deps chromium
BASE_URL=http://localhost:8787 npx playwright test
```

Unit tests are in `tests/` and cover:
- `test_config.py` - Config deep-merge and validation
- `test_overrides.py` - Ignore/wishlist persistence
- `test_scoring.py` - Movie scoring algorithms
- `test_scheduler.py` - Library polling logic
- `test_telegram.py` - Notification formatting

E2E tests are in `e2e/tests/` (Playwright + Chromium):
- `smoke.spec.js` - App loads, API endpoints respond (`/api/version`, `/api/scan/status`, `/api/config`)
- `navigation.spec.js` - All sidebar nav buttons present, `.active` class toggles correctly
- `config.spec.js` - Settings form fields, TMDB key masking, config save/reload roundtrip, modal

### Running Locally
```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI server
uvicorn app.web:app --host 0.0.0.0 --port 8787
```

Access UI at `http://localhost:8787`

### Docker
```bash
# Build
docker build -t cineplete .

# Run
docker compose up -d
```

## Architecture

### Core Components

**Backend (FastAPI)**
- `app/web.py` - All API endpoints, lifespan management, scheduler startup
- `app/scanner.py` - 8-step scan engine with background threading and progress state
- `app/config.py` - Config loader/saver with deep-merge pattern (preserves defaults)
- `app/logger.py` - Rotating file logger (2 MB × 3 files)

**Media Server Scanners**
- `app/plex_xml.py` - Fast Plex XML API scanner (~2s for 1000 movies)
- `app/jellyfin_api.py` - Jellyfin API scanner (drop-in replacement for Plex)

Both scanners return identical tuple structure:
```python
(plex_ids, directors, actors, stats, no_tmdb_guid)
```

**TMDB Integration**
- `app/tmdb.py` - TMDB API client with persistent caching in `/data/tmdb_cache.json`

**Automation & Notifications**
- `app/scheduler.py` - APScheduler-based library polling (checks movie count, triggers scan if changed)
- `app/telegram.py` - Telegram notifications with rate limiting

**Data Management**
- `app/overrides.py` - Ignore/wishlist persistence helpers

**Frontend**
- `static/index.html` - Single-page app shell with inline CSS
- `static/app.js` - All UI logic (routing, rendering, API calls, Chart.js integration)

### Data Flow

```
1. Config loaded from /config/config.yml (deep-merged with defaults)
2. Scheduler starts on app boot, polls library every N minutes
3. User triggers scan → scanner.build_async() spawns background thread
4. Scanner runs 8 steps with progress updates:
   - Load config
   - Scan Plex/Jellyfin library (determined by SERVER.MEDIA_SERVER)
   - Validate TMDB metadata
   - Analyze collections (franchises)
   - Analyze directors
   - Analyze actors
   - Build suggestions (TMDB recommendations × library overlap)
   - Build results
5. Results written to /data/results.json
6. Frontend polls /api/scan/status for progress
7. Telegram notification sent if enabled
```

### Configuration System

Config is stored at `/config/config.yml` with a deep-merge pattern:
- `DEFAULT_CONFIG` in `app/config.py` defines all possible keys
- User config is deep-merged over defaults (missing keys auto-filled)
- `save_config()` always writes the full merged result
- `is_configured()` validates based on media server type (Plex vs Jellyfin)

**Media Server Selection**
- `SERVER.MEDIA_SERVER` - `"plex"` or `"jellyfin"`
- Scanner dynamically imports the appropriate module at runtime
- Configuration requirements differ:
  - Plex: PLEX_URL, PLEX_TOKEN, LIBRARY_NAME
  - Jellyfin: JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_LIBRARY_NAME

### Persistent Data (`/data/`)

| File | Purpose |
|------|---------|
| `results.json` | Full scan output (regenerated each scan) |
| `tmdb_cache.json` | TMDB API response cache (permanent) |
| `overrides.json` | Ignored items, wishlist, rec_fetched_ids |
| `cineplete.log` | Rotating log file (2 MB × 3 files) |
| `last_telegram.txt` | Timestamp of last Telegram notification |

### Scan State Management

`scanner.py` uses a shared `scan_state` dict with threading lock:
```python
scan_state = {
    "running": bool,
    "step": str,
    "step_index": int,
    "step_total": 8,
    "detail": str,
    "error": None,
    "last_completed": timestamp,
    "last_duration": seconds,
}
```

Only one scan can run at a time. Concurre
t requests are rejected.

## Key Patterns

### Deep Merge
Config uses a recursive deep-merge to preserve all default keys when user saves partial config. See `_deep_merge()` in `app/config.py`.

### Media Server Abstraction
Both `plex_xml.py` and `jellyfin_api.py` export `scan_movies()` that returns identical tuple structure, allowing scanner.py to work with either server without logic changes.

### TMDB Caching
All TMDB API calls are cached permanently in `tmdb_cache.json`. Only new lookups hit the API. Cache is shared across scans.

### Background Scanning
`build_async()` spawns a thread running `build()`. The main thread never blocks. Progress is exposed via `scan_state` dict.

### Telegram Rate Limiting
Notifications respect `TELEGRAM_MIN_INTERVAL` to avoid spam. Last notification time persisted in `/data/last_telegram.txt`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/version` | App version |
| GET | `/api/config` | Full config |
| POST | `/api/config` | Save config (triggers scheduler restart) |
| GET | `/api/config/status` | `{configured: bool}` |
| GET | `/api/results` | Last scan results (never blocks) |
| POST | `/api/scan` | Start background scan |
| GET | `/api/scan/status` | Live scan progress |
| POST | `/api/ignore` | Ignore movie/franchise/director/actor |
| POST | `/api/unignore` | Remove ignore |
| POST | `/api/wishlist/add` | Add to wishlist |
| POST | `/api/wishlist/remove` | Remove from wishlist |
| POST | `/api/radarr/add` | Add movie to Radarr |
| GET | `/api/logs` | Last N lines of cineplete.log |

## CI/CD

GitHub Actions workflow (`.github/workflows/docker.yml`) runs on **every branch push**:
1. Security scan (Trivy — blocks on CRITICAL/HIGH CVEs)
2. Unit tests (pytest)
3. **E2E tests** (Playwright Chromium — builds image locally, spins up container, runs full suite)
4. Semantic versioning based on commit message (main branch only):
   - `fix:` → patch bump
   - `feat:` → minor bump
   - `feat!:` → major bump
5. Multi-arch Docker build (amd64 + arm64)
6. Push to Docker Hub (`latest` + version tag on main, `STG` + branch-sha on other branches)

**Version tags and DockerHub push only happen after all e2e tests pass.**
**Version tags only created on main branch**. Feature branches get `STG` + branch-sha tags.

## Important Notes

### Commit Message Conventions
Follow conventional commits for automatic versioning:
- `fix: bug description` → patch (v1.2.3 → v1.2.4)
- `feat: new feature` → minor (v1.2.3 → v1.3.0)
- `feat!: breaking change` → major (v1.2.3 → v2.0.0)

### TMDB API Key
Use the **API Key (v3)** from TMDB settings, NOT the Read Access Token (JWT). The API key is a short alphanumeric string, the token is a long JWT starting with `eyJ`.

### Radarr Integration
Movies added to Radarr have `searchForMovie = false` by default (controlled by `RADARR_SEARCH_ON_ADD`). They are added but NOT automatically downloaded.

### Jellyfin Support
Jellyfin support is on the `feature-jellyfin` branch. The scanner uses the exact same return structure as Plex, so no changes to `scanner.py` are needed.

### Docker Volumes
- `/config` - config.yml (editable from UI)
- `/data` - results, cache, logs, overrides (persist across updates)

### Port Configuration
Default port is 8787. Override with `APP_PORT` environment variable or change `SERVER.UI_PORT` in config.

## Security Rules

**All sensitive fields must use `secret` input type (password-masked with show/hide toggle).**

This applies to every field that holds a token, key, password, secret, or bearer credential — without exception:
- API keys (TMDB, Radarr, Overseerr, Jellyseerr, Watchtower, any future integration)
- Bearer tokens
- Webhook secrets
- Passwords
- Any field whose name contains: `key`, `token`, `secret`, `password`, `bearer`, `credential`

Implementation pattern (already used for `cfg_tmdb_key` and `cfg_wh_secret`):
```js
field("cfg_field_name", "Label", value, "secret")
```
The `field()` helper in `config.js` renders a `type="password"` input with a show/hide eye toggle when the 4th argument is `"secret"`. Never render these as `type="text"`.

## Testing Rules

**Every code change must keep the test suite green. Specifically:**

[### When adding a new backend feature or API endpoint
- Add or update unit tests in `tests/` covering the new logic
- Add or update the relevant smoke test in `e2e/tests/smoke.spec.js` if a new API endpoint is introduced (check it returns 200 and the expected shape)

](https://x.com/sdblepas/status/2036704070631674111?s=20)### When changing the UI (new tab, renamed tab, new button, new form field, modal change)
- Update `e2e/tests/navigation.spec.js` if a nav tab is added, removed, or renamed — keep `ALL_TABS`, `TITLE_TABS`, and `DATA_GATED` arrays in sync
- Update `e2e/tests/config.spec.js` if the Settings form changes (new fields, renamed buttons, new sections)
- If a new modal is added, add a DOM-manipulation open/close test (do NOT call API-backed JS functions like `openMovieModal()` in tests — they trigger real external API calls)

### Key facts about the CI test environment
- The app starts with **no scan data** and **no configuration** (empty `/data` and `/config` volumes)
- `!CONFIGURED` → the app forces the config tab for all navigation — only `dashboard` and `config` tabs show their correct `#page-title`
- Data-gated tabs (`notmdb`, `nomatch`, `duplicates`, `franchises`, `directors`, `actors`, `classics`, `suggestions`, `wishlist`) call `renderSkeleton()` when no data exists — `#page-title` stays `"Dashboard"`. Test the `.active` class, not the page title, for these tabs
- `PAGE_TITLES.config = "Configuration"` (not "Settings") — always use the value from `app.js` `PAGE_TITLES` dict as the source of truth for expected titles

## Shipped ✅
- **Radarr 4K instance** — v2.6.0
- **Scheduled auto-scan** (daily / weekly cron) — v2.6.0
- **Quality profile dropdown** — fetch real profile names from Radarr API — v2.6.0
- **Movie posters** — v2.5.x
- **CSV export** — v2.5.x
- **Dashboard charts** (donut + KPI strip) — v2.5.x
- **Smart authentication** — network-aware, local bypass, PBKDF2, sliding cookie — v2.5.x
- **Watchtower on-demand update** — `POST /v1/update?scope=cineplete` — v2.4.x
- **Watchtower UI** — "Update now" button in Settings + auto-update toggle — v2.4.x
- **New release notification** — non-intrusive badge in sidebar footer when newer version on GitHub — v2.5.x
- **Ignore list** — 🚫 button on every movie card, dedicated Ignored tab, reversible, metadata stored — v2.7.0
- **Export button fix** — was hidden on all tabs due to CSS specificity conflict — v2.7.0
- **Letterboxd tab** — persistent URL list, multi-list scoring (×N badge), owned movies filtered, curator RSS auto-expansion, description HTML fallback — v2.7.0
- **FlareSolverr support** — automatic fallback for Cloudflare-blocked Letterboxd list RSS feeds — v2.7.0

## Backlog (next version)

- **Multiple library support** — currently only one Plex/Jellyfin movie library can be scanned at a time. Users with separate libraries (e.g. 4K + 1080p, or Movies + Anime) need to reconfigure to switch. Future work: allow selecting or scanning multiple libraries and merging results.

- ~~**Letterboxd tab: background fetch + caching**~~ ✅ fixed — `data/letterboxd_cache.json`, background thread via `_lb_do_refresh()`, instant GET, auto-refresh on add/remove URL, JS polls every 5s, shows "Updated Xm ago" / "↻ Refreshing…".
