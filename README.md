# 🎬 Cineplete — Plex & Jellyfin Movie Audit

[![Build & Publish Docker](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml/badge.svg)](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/sdblepas/cineplete)](https://hub.docker.com/r/sdblepas/cineplete)
[![Docker Image Version](https://img.shields.io/docker/v/sdblepas/cineplete/latest)](https://hub.docker.com/r/sdblepas/cineplete)
![License](https://img.shields.io/github/license/sdblepas/CinePlete)

![Python](https://img.shields.io/badge/python-3.11-blue)
![Self Hosted](https://img.shields.io/badge/self--hosted-ready-brightgreen)
![Multi-Arch](https://img.shields.io/badge/docker-multiarch-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-powered-green)

![Plex](https://img.shields.io/badge/Plex-compatible-orange)
![Jellyfin](https://img.shields.io/badge/Jellyfin-compatible-7B2FBE)
![Radarr](https://img.shields.io/badge/Radarr-integration-purple)
![TMDB](https://img.shields.io/badge/TMDB-API-blue)
![Homelab](https://img.shields.io/badge/homelab-friendly-blue)
![GitHub Stars](https://img.shields.io/github/stars/sdblepas/CinePlete?style=social)

---

# 🇬🇧 English

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

Stored in:

```
data/overrides.json
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
| `MEDIA_SERVER` | `plex` or `jellyfin` (default: `plex`) |
| `TMDB_API_KEY` | TMDB classic API Key (v3) — **not** the Read Access Token |

> ⚠️ Use the **API Key** found under TMDB → Settings → API → **API Key** (short alphanumeric string starting with letters/numbers). Do **not** use the Read Access Token (long JWT string starting with `eyJ`).

**Plex settings:**

| Key | Description |
|-----|-------------|
| `PLEX_URL` | URL of your Plex server |
| `PLEX_TOKEN` | Plex authentication token |
| `LIBRARY_NAME` | Name of the movie library in Plex |

**Jellyfin settings:**

| Key | Description |
|-----|-------------|
| `JELLYFIN_URL` | URL of your Jellyfin server (e.g. `http://192.168.1.10:8096`) |
| `JELLYFIN_API_KEY` | API key from Jellyfin Dashboard → API Keys |
| `JELLYFIN_LIBRARY_NAME` | Name of the movie library in Jellyfin (default: `Movies`) |

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

### Docker Compose (recommended)

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
| POST | `/api/wishlist/add` | Adds a movie to wishlist |
| POST | `/api/wishlist/remove` | Removes from wishlist |
| POST | `/api/radarr/add` | Sends a movie to Radarr |
| POST | `/api/jellyfin/test` | Tests Jellyfin connectivity and library access |
| GET | `/api/logs` | Returns last N lines of cineplete.log |

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
Plex Server                  Jellyfin Server
     │                              │
     │ XML API (~2s/1000 movies)    │ HTTP API
     ▼                              ▼
Plex XML Scanner          Jellyfin API Scanner
          \                    /
           └──── scan_movies() ────┘
                      │
                      │ {tmdb_id: title}
                      ▼
     8-Step Scan Engine (background thread + progress state)
                      │
          ┌───────────┼───────────────┐
          ▼           ▼               ▼
     Franchises   Directors   Actors / Classics / Suggestions
          │           │               │
          └───────────┴───────────────┘
                      │ TMDB API (cached)
                      ▼
              FastAPI Backend  ──→  results.json
                      │
                      ▼
        Web UI Dashboard (charts, filters, wishlist, Radarr, logs)
```

---

# 🇫🇷 Français

## Présentation

**Cineplete** est un outil Docker auto-hébergé permettant d'analyser une bibliothèque **Plex ou Jellyfin** et de détecter :

- Les films manquants dans les sagas
- Les films manquants de réalisateurs déjà présents
- Les films populaires d'acteurs présents
- Les classiques absents
- Les suggestions personnalisées basées sur votre bibliothèque
- Les problèmes de métadonnées
- La gestion d'une wishlist
- L'intégration Radarr

L'outil propose une **interface web avec graphiques**, un **onglet Logs** pour le diagnostic, et un **scan ultra rapide** (~2 secondes avec Plex). Les deux serveurs multimédia sont sélectionnables depuis l'onglet Config, sans redémarrage.

---

## Fonctionnalités

### Support Plex & Jellyfin

Cineplete prend en charge deux serveurs multimédia, sélectionnables depuis l'onglet Config :

- **Plex** — utilise l'API XML native (~2s pour 1000 films)
- **Jellyfin** — utilise l'API HTTP Jellyfin, avec bouton **Test de connexion** intégré

### Scanner Plex ultra rapide

Utilise l'API XML native de Plex.

- 1000 films → ~2 secondes
- 3000 films → ~4 secondes

---

### Dashboard

Vue d'ensemble visuelle complète de la bibliothèque.

**Scores :**
- Complétion des sagas
- Score réalisateurs
- Couverture classiques
- Score cinéma global

**Graphiques (Chart.js) :**
- Statut des sagas — donut : Complet / Manque 1 / Manque 2+
- Couverture classiques — donut : En bibliothèque vs manquants
- Santé des métadonnées — donut : TMDB valide / Sans GUID / Sans correspondance
- Top 10 acteurs — barre horizontale
- Réalisateurs par films manquants — barre groupée
- Panel statistiques bibliothèque

Les sagas ignorées sont automatiquement exclues du graphique.

---

### Sagas

Détection automatique des collections TMDB.

Exemple :
```
Alien Collection (6/7)
Manquant : Alien Romulus
```

---

### Réalisateurs

Films manquants de réalisateurs présents dans la bibliothèque.

---

### Acteurs

Films populaires manquants d'acteurs présents.

Critère :
```
vote_count >= 500
```

---

### Classiques

Films manquants issus du **Top Rated TMDB**.

Critères par défaut :
```
note >= 8.0
vote_count >= 5000
```

---

### Suggestions

Recommandations personnalisées basées sur **votre propre bibliothèque**.

Pour chaque film de votre bibliothèque Plex, Cineplete récupère les recommandations TMDB et attribue un score à chaque suggestion selon combien de vos films la recommandent. Un badge **⚡ N correspondances** est affiché sur chaque carte.

Les appels API sont mis en cache — seuls les nouveaux films ajoutés génèrent de vraies requêtes HTTP lors des scans suivants.

---

### Wishlist

Boutons d'ajout sur chaque carte film, depuis tous les onglets.
Stockée dans `data/overrides.json`.

---

### Diagnostic métadonnées

**No TMDB GUID** — Films sans métadonnées TMDB.  
Correction dans Plex : `Corriger la correspondance → TheMovieDB`

**TMDB No Match** — Films avec un ID TMDB invalide. Le titre Plex est affiché pour identifier le film immédiatement.  
Correction : Actualiser les métadonnées ou corriger manuellement.

---

### Système Ignore

Ignorer définitivement des sagas, réalisateurs, acteurs ou films via les boutons de l'interface.
Les éléments ignorés sont exclus des listes et des graphiques.

---

### Recherche, Filtres & Tri

Disponibles sur tous les onglets :

- **Recherche** par titre ou nom de groupe
- **Filtre par décennie** — 2020s / 2010s / 2000s / 1990s / Older
- **Tri** — popularité / note / votes / année / titre

---

### Scan asynchrone avec progression

Le bouton **Rescan** lance un scan en arrière-plan sans bloquer l'interface.

Une carte de progression apparaît :
```
Étape 3/8 — Analyzing collections
[=====>      ] 43%
```

Elle disparaît automatiquement à la fin du scan.
Un seul scan peut tourner à la fois.

---

### Logs

Un onglet **Logs** dédié affiche les 200 dernières lignes de `/data/cineplete.log` avec niveaux de sévérité colorés. Utile pour diagnostiquer les erreurs de scan, d'API TMDB ou de connectivité Plex.

---

### Intégration Radarr

Ajout en un clic depuis n'importe quelle carte film.

`searchForMovie = false` — le film est ajouté à Radarr mais le téléchargement n'est **pas** déclenché automatiquement.

---

## Configuration

Fichier : `config/config.yml` — éditable depuis l'onglet **Config** de l'interface.

**Paramètres de base :**

| Clé | Description |
|-----|-------------|
| `MEDIA_SERVER` | `plex` ou `jellyfin` (défaut : `plex`) |
| `TMDB_API_KEY` | Clé API TMDB classique (v3) — **pas** le Read Access Token |

> ⚠️ Utiliser la **clé API** disponible sous TMDB → Paramètres → API → **Clé API** (chaîne alphanumérique courte). Ne **pas** utiliser le Read Access Token (longue chaîne JWT commençant par `eyJ`).

**Paramètres Plex :**

| Clé | Description |
|-----|-------------|
| `PLEX_URL` | URL du serveur Plex |
| `PLEX_TOKEN` | Token d'authentification Plex |
| `LIBRARY_NAME` | Nom de la bibliothèque films dans Plex |

**Paramètres Jellyfin :**

| Clé | Description |
|-----|-------------|
| `JELLYFIN_URL` | URL du serveur Jellyfin (ex. `http://192.168.1.10:8096`) |
| `JELLYFIN_API_KEY` | Clé API depuis Jellyfin → Tableau de bord → Clés API |
| `JELLYFIN_LIBRARY_NAME` | Nom de la bibliothèque films dans Jellyfin (défaut : `Movies`) |

**Paramètres avancés :**

| Clé | Défaut | Description |
|-----|--------|-------------|
| `CLASSICS_PAGES` | 4 | Pages TMDB Top Rated à récupérer |
| `CLASSICS_MIN_VOTES` | 5000 | Votes minimum pour les classiques |
| `CLASSICS_MIN_RATING` | 8.0 | Note minimum pour les classiques |
| `CLASSICS_MAX_RESULTS` | 120 | Nombre maximum de classiques |
| `ACTOR_MIN_VOTES` | 500 | Votes minimum pour les films d'acteurs |
| `ACTOR_MAX_RESULTS_PER_ACTOR` | 10 | Nombre max de films par acteur |
| `PLEX_PAGE_SIZE` | 500 | Taille de page API Plex |
| `JELLYFIN_PAGE_SIZE` | 500 | Taille de page API Jellyfin |
| `SHORT_MOVIE_LIMIT` | 60 | Films plus courts que cette durée (minutes) ignorés |
| `SUGGESTIONS_MAX_RESULTS` | 100 | Nombre maximum de suggestions |
| `SUGGESTIONS_MIN_SCORE` | 2 | Nombre minimum de vos films devant recommander une suggestion |

---

## Installation

```bash
docker compose up -d
```

Ouvrir l'interface :

```
http://IP_DU_NAS:8787
```

---

## Licence

MIT License