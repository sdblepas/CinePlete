
# 🎬 Plex Movie Audit

![Docker](https://img.shields.io/badge/docker-ready-blue)
![Python](https://img.shields.io/badge/python-3.11-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)
![Plex](https://img.shields.io/badge/Plex-compatible-orange)
![TMDB](https://img.shields.io/badge/TMDB-API-blue)

---

# 🇬🇧 English

## Overview

**Plex Movie Audit** is a local analysis tool that scans your Plex movie library and identifies:

• Missing movies from franchises  
• Missing films from directors you already collect  
• Popular films from actors already present in your library  
• Classic movies missing from your collection  
• Metadata issues in Plex (missing TMDB GUID or broken matches)  
• Wishlist management  
• Direct Radarr integration  

The tool includes a **fast web UI dashboard** and performs **ultra‑fast Plex scans (~2 seconds)**.

---

# Features

## Ultra Fast Plex Scanner

The scanner uses the **native Plex XML API** instead of slow metadata requests.

Performance example:

1000 movies → ~2 seconds  
3000 movies → ~4 seconds

---

## Dashboard

The dashboard shows statistics about your Plex library:

• Movies indexed  
• Directors tracked  
• Actors tracked  
• Short movies ignored  
• Missing TMDB metadata  

It also includes:

• Saga completion graph  
• Actor heatmap  
• Cinema score  

---

## Franchises

Detects **TMDB collections (sagas)** and lists missing films.

Example:

Alien Collection (6/7)

Missing:
- Alien Romulus

---

## Directors

Detects missing films from directors already in your library.

Example:

Christopher Nolan

Missing:
- Following
- Insomnia

---

## Actors

Finds **popular films of actors already in your Plex library**.

Filtering criteria:

vote_count >= 500

Sorted by:

• popularity  
• vote_count  
• vote_average  

---

## Classics

Detects missing films from **TMDB Top Rated**.

Criteria:

vote_average >= 8  
vote_count >= 5000  

---

## Wishlist

Interactive wishlist with UI buttons.

Movies can be added from:

• franchises  
• directors  
• actor suggestions  
• TMDB suggestions  

Wishlist is stored in:

data/overrides.json

---

## Metadata Diagnostics

### No TMDB GUID

Movies without TMDB metadata.

Fix inside Plex:

Fix Match → TheMovieDB

---

### No Match Found

Films with invalid TMDB metadata.

Solution:

Refresh metadata or fix match.

---

## Ignore System

You can permanently ignore:

• franchises  
• directors  
• actors  
• specific movies  

Stored in:

data/overrides.json

---

## Radarr Integration

Movies can be added to Radarr with one click.

Important:

searchForMovie = false

Meaning:

✔ movie is added to Radarr  
❌ download is NOT started automatically  

---

# Configuration

Configuration is stored in `.env`.

Example:

PLEX_URL=http://192.168.1.20:32400  
PLEX_TOKEN=XXXXXXXX  

LIBRARY_NAME=Movies  

TMDB_API_KEY=XXXXXXXX  

UI_PORT=8787  

---

# Installation

Create folder:

/volume1/Docker/plex-audit

Copy project files and start:

docker compose up -d

Open UI:

http://NAS:8787

---

# Project Structure

plex-audit

docker-compose.yml  
.env  

app/
- web.py
- scanner.py
- plex_xml.py
- tmdb.py
- overrides.py

static/
- index.html
- app.js

data/
- overrides.json
- results.json
- tmdb_cache.json

---

# Example results.json

{
  "stats": {
    "movies_indexed": 1025,
    "directors_tracked": 217,
    "actors_tracked": 546
  },
  "franchises": [
    {
      "name": "Alien Collection",
      "have": 6,
      "total": 7,
      "missing": ["Alien Romulus"]
    }
  ]
}

---

# Example overrides.json

{
  "ignore_movies": [12345],
  "ignore_franchises": ["Goofy Movie Collection"],
  "ignore_directors": ["Uwe Boll"],
  "ignore_actors": ["Some Actor"],
  "wishlist_movies": [945961]
}

---

# Architecture

Plex Server
     │
     │ XML API
     ▼
Plex XML Scanner
     │
     │ TMDB API
     ▼
Analysis Engine
     │
     ▼
FastAPI Backend
     │
     ▼
Web UI Dashboard

---

# Technologies

Python  
FastAPI  
Docker  
TMDB API  
Plex XML API  
Chart.js  

---

# 🇫🇷 Français

## Présentation

**Plex Movie Audit** est un outil local permettant d'analyser une bibliothèque Plex et de détecter :

• les films manquants dans les sagas  
• les films manquants de réalisateurs déjà présents  
• les films populaires d’acteurs présents  
• les classiques absents  
• les problèmes de métadonnées Plex  
• la gestion d'une wishlist  
• l'intégration Radarr  

L'outil propose une **interface web rapide** et un **scan Plex ultra rapide (~2 secondes)**.

---

## Fonctionnalités

### Scanner Plex ultra rapide

Le scanner utilise l’API XML native Plex.

Exemple de performance:

1000 films → ~2 secondes  
3000 films → ~4 secondes  

---

### Dashboard

Statistiques Plex :

• films indexés  
• réalisateurs suivis  
• acteurs suivis  
• films courts ignorés  
• films sans metadata TMDB  

Graphiques :

• complétion des sagas  
• heatmap des acteurs  
• score cinéma  

---

### Sagas

Détection automatique des collections TMDB.

Exemple :

Alien Collection (6/7)

Manquant :
- Alien Romulus

---

### Réalisateurs

Films manquants de réalisateurs présents dans la bibliothèque.

---

### Acteurs

Films populaires manquants d’acteurs présents.

Critère :

vote_count >= 500

---

### Classiques

Films manquants issus du **Top Rated TMDB**.

Critères :

note ≥ 8  
vote_count ≥ 5000  

---

### Wishlist

Liste de films à ajouter.

Stockée dans :

data/overrides.json

---

### Diagnostic métadonnées

No TMDB GUID  
No Match Found  

Permet de corriger facilement Plex.

---

### Système Ignore

Possibilité d’ignorer :

• sagas  
• réalisateurs  
• acteurs  
• films  

---

### Intégration Radarr

Ajout en un clic dans Radarr.

Téléchargement automatique **désactivé**.

---

# Licence

MIT License
