# 🎬 Cineplete — Plex Movie Audit

[![Build & Publish Docker](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml/badge.svg)](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/sdblepas/cineplete)](https://hub.docker.com/r/sdblepas/cineplete)
[![Docker Image Version](https://img.shields.io/docker/v/sdblepas/cineplete/latest)](https://hub.docker.com/r/sdblepas/cineplete)
![License](https://img.shields.io/github/license/sdblepas/CinePlete)

![Python](https://img.shields.io/badge/python-3.11-blue)
![Self Hosted](https://img.shields.io/badge/self--hosted-ready-brightgreen)
![Multi-Arch](https://img.shields.io/badge/docker-multiarch-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-powered-green)

![Plex](https://img.shields.io/badge/Plex-compatible-orange)
![Radarr](https://img.shields.io/badge/Radarr-integration-purple)
![TMDB](https://img.shields.io/badge/TMDB-API-blue)
![Homelab](https://img.shields.io/badge/homelab-friendly-blue)
![GitHub Stars](https://img.shields.io/github/stars/sdblepas/CinePlete?style=social)
---

# 🇬🇧 English

Ever wondered **which movies you're missing** from your favorite franchises, directors, or actors?

**Cineplete scans your Plex library in seconds and shows exactly what's missing.**

✔ Missing movies from franchises  
✔ Missing films from directors you collect  
✔ Popular movies from actors already in your library  
✔ Classic films missing from your collection  
✔ Tailor-made suggestions based on your library  

All in a **beautiful dashboard with charts and Radarr integration.**

![Cineplete Demo](assets/Demo.gif)
## Overview

**Plex Movie Audit** is a local analysis tool that scans your Plex movie library and identifies:

- Missing movies from franchises
- Missing films from directors you already collect
- Popular films from actors already present in your library
- Classic movies missing from your collection
- Metadata issues in Plex (missing TMDB GUID or broken matches)
- Wishlist management
- Direct Radarr integration

The tool includes a **web UI dashboard with charts** and performs **ultra-fast Plex scans (~2 seconds)**.

---

## Features

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

### Suggestions TMDB

Full list of TMDB Top Rated films not yet in your library, sorted by rating.

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

**TMDB No Match** — Films with an invalid TMDB ID that returns no data.
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

A live progress card appears (bottom-right) showing:

```
Step 3/7 — Analyzing collections
[=====>      ] 43%
```

The progress card disappears automatically when the scan completes.

Only one scan can run at a time. Concurrent scan requests are rejected cleanly.

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
| `PLEX_URL` | URL of your Plex server |
| `PLEX_TOKEN` | Plex authentication token |
| `LIBRARY_NAME` | Name of the movie library |
| `TMDB_API_KEY` | TMDB v3 API key |

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
| `SHORT_MOVIE_LIMIT` | 60 | Films shorter than this (minutes) are ignored |

---

## Installation

Create folder:

```
/volume1/Docker/plex-audit
```

Copy project files and start:

```bash
docker compose up -d
```

Open UI:

```
http://NAS:8787
```

---

## Project Structure

```
plex-audit/
├── docker-compose.yml
├── app/
│   ├── web.py         # FastAPI backend
│   ├── scanner.py     # Main scan engine (async, threaded)
│   ├── plex_xml.py    # Plex XML API scanner
│   ├── tmdb.py        # TMDB API client (cached, key-safe)
│   ├── overrides.py   # Ignore/wishlist helpers
│   └── config.py      # Config loader/saver
├── static/
│   ├── index.html
│   └── app.js
├── config/
│   └── config.yml
└── data/
    ├── overrides.json
    ├── results.json
    └── tmdb_cache.json
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/results` | Returns scan results (never blocks) |
| POST | `/api/scan` | Starts a background scan |
| GET | `/api/scan/status` | Returns live scan progress |
| GET | `/api/config` | Returns current config |
| POST | `/api/config` | Saves config |
| POST | `/api/ignore` | Ignores a movie / franchise / director / actor |
| POST | `/api/unignore` | Removes an ignore |
| POST | `/api/wishlist/add` | Adds a movie to wishlist |
| POST | `/api/wishlist/remove` | Removes from wishlist |
| POST | `/api/radarr/add` | Sends a movie to Radarr |

---

## Technologies

- Python 3.11
- FastAPI + Uvicorn
- Docker
- TMDB API v3
- Plex XML API
- Chart.js
- Tailwind CSS (CDN)

---

## Architecture

```
Plex Server
     │
     │ XML API (~2s for 1000 movies)
     ▼
Plex XML Scanner
     │
     │ TMDB API (cached, key-stripped, periodic flush)
     ▼
Async Scan Engine (background thread + progress state)
     │
     ▼
FastAPI Backend
     │
     ▼
Web UI Dashboard (charts, filters, wishlist, Radarr)
```

---

# 🇫🇷 Français

## Présentation

**Plex Movie Audit** est un outil local permettant d'analyser une bibliothèque Plex et de détecter :

- Les films manquants dans les sagas
- Les films manquants de réalisateurs déjà présents
- Les films populaires d'acteurs présents
- Les classiques absents
- Les problèmes de métadonnées Plex
- La gestion d'une wishlist
- L'intégration Radarr

L'outil propose une **interface web avec graphiques** et un **scan Plex ultra rapide (~2 secondes)**.

---

## Fonctionnalités

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

### Suggestions TMDB

Liste complète des films Top Rated TMDB absents de la bibliothèque.

---

### Wishlist

Boutons d'ajout sur chaque carte film, depuis tous les onglets.
Stockée dans `data/overrides.json`.

---

### Diagnostic métadonnées

**No TMDB GUID** — Films sans métadonnées TMDB.
Correction dans Plex : `Corriger la correspondance → TheMovieDB`

**TMDB No Match** — Films avec un ID TMDB invalide.
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

Une carte de progression apparaît en bas à droite :
```
Étape 3/7 — Analyzing collections
[=====>      ] 43%
```

Elle disparaît automatiquement à la fin du scan.
Un seul scan peut tourner à la fois.

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
| `PLEX_URL` | URL du serveur Plex |
| `PLEX_TOKEN` | Token d'authentification Plex |
| `LIBRARY_NAME` | Nom de la bibliothèque films |
| `TMDB_API_KEY` | Clé API TMDB v3 |

**Paramètres avancés** (section "Advanced settings" dans l'interface) :

| Clé | Défaut | Description |
|-----|--------|-------------|
| `CLASSICS_PAGES` | 4 | Pages TMDB Top Rated à récupérer |
| `CLASSICS_MIN_VOTES` | 5000 | Votes minimum pour les classiques |
| `CLASSICS_MIN_RATING` | 8.0 | Note minimum pour les classiques |
| `CLASSICS_MAX_RESULTS` | 120 | Nombre maximum de classiques |
| `ACTOR_MIN_VOTES` | 500 | Votes minimum pour les films d'acteurs |
| `ACTOR_MAX_RESULTS_PER_ACTOR` | 10 | Nombre max de films par acteur |
| `PLEX_PAGE_SIZE` | 500 | Taille de page API Plex |
| `SHORT_MOVIE_LIMIT` | 60 | Films plus courts que cette durée (minutes) ignorés |

---

## Installation

Créer le dossier :

```
/volume1/Docker/plex-audit
```

Copier les fichiers et démarrer :

```bash
docker compose up -d
```

Ouvrir l'interface :

```
http://NAS:8787
```

---

## Structure du projet

```
plex-audit/
├── docker-compose.yml
├── app/
│   ├── web.py         # Backend FastAPI
│   ├── scanner.py     # Moteur de scan (async, threadé)
│   ├── plex_xml.py    # Scanner API XML Plex
│   ├── tmdb.py        # Client API TMDB (cache, clé sécurisée)
│   ├── overrides.py   # Helpers ignore/wishlist
│   └── config.py      # Chargement/sauvegarde config
├── static/
│   ├── index.html
│   └── app.js
├── config/
│   └── config.yml
└── data/
    ├── overrides.json
    ├── results.json
    └── tmdb_cache.json
```

---

## Endpoints API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/results` | Résultats du scan (non bloquant) |
| POST | `/api/scan` | Lance un scan en arrière-plan |
| GET | `/api/scan/status` | Progression du scan en direct |
| GET | `/api/config` | Config actuelle |
| POST | `/api/config` | Sauvegarde la config |
| POST | `/api/ignore` | Ignore un film / saga / réalisateur / acteur |
| POST | `/api/unignore` | Retire un ignore |
| POST | `/api/wishlist/add` | Ajoute à la wishlist |
| POST | `/api/wishlist/remove` | Retire de la wishlist |
| POST | `/api/radarr/add` | Envoie un film à Radarr |

---

## Technologies

- Python 3.11
- FastAPI + Uvicorn
- Docker
- API TMDB v3
- API XML Plex
- Chart.js
- Tailwind CSS (CDN)

---

## Licence

MIT License