# 🎬 Cineplete — Audit Plex & Jellyfin

[![Build & Publish Docker](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml/badge.svg)](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/sdblepas/cineplete)](https://hub.docker.com/r/sdblepas/cineplete)
[![Docker Image Version](https://img.shields.io/docker/v/sdblepas/cineplete/latest)](https://hub.docker.com/r/sdblepas/cineplete)
![License](https://img.shields.io/github/license/sdblepas/CinePlete)

> 🇬🇧 [English version](README.md)

---

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

**Ignore par film** — chaque carte film dispose d'un bouton 🚫. Les films ignorés apparaissent dans un onglet **Ignored** dédié avec possibilité de restauration en un clic.

---

### Onglet Letterboxd

Importez et parcourez les films depuis n'importe quelle URL Letterboxd publique — watchlists, listes nommées, journaux ou flux RSS de profil curateur.

- Ajoutez plusieurs URLs — elles sont fusionnées en une grille scorée
- Les films présents dans plusieurs listes affichent un badge **×N** et remontent en tête
- Les films déjà dans votre bibliothèque sont automatiquement filtrés
- Bouton ↻ pour rafraîchir toutes les listes
- Les URLs sont sauvegardées dans `overrides.json`

---

### Intégration FlareSolverr

Certains flux RSS Letterboxd sont protégés par Cloudflare. Si vous utilisez [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr), configurez l'URL dans **Config → FlareSolverr** (ex. `http://flaresolverr:8191`). Les requêtes bloquées (403) sont automatiquement reroutées.

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

### Notifications de version

CinePlete vérifie l'[API GitHub Releases](https://github.com/sdblepas/CinePlete/releases) toutes les heures. Lorsqu'une nouvelle version est disponible, une bannière apparaît dans la barre latérale avec un lien vers les notes de version.

---

### Authentification intelligente

CinePlete propose une authentification de type Radarr, configurable depuis **Config → Authentication**.

| Mode | Comportement |
|------|-------------|
| **None** | Accès libre — aucun login requis (défaut) |
| **Forms** | Identifiant + mot de passe requis pour tous |
| **Local network free** | Pas d'auth sur les IPs locales (`10.x`, `192.168.x`, `127.x`), login requis depuis internet |

- Mots de passe hashés avec **PBKDF2-SHA256**
- **Cookie glissant 7 jours** — session persistante entre les navigations
- Toggle **"Faire confiance à ce navigateur"** — cookie persistant ou de session
- Auth par clé API via header `X-Api-Key` ou `?access_token=`
- Bouton de déconnexion dans le pied de la barre latérale

---

### Mise à jour automatique via Watchtower

CinePlete peut se mettre à jour automatiquement via [Watchtower](https://containrrr.dev/watchtower/).

Configurez-le depuis **Config → Watchtower** :
- Activez **Auto-update enabled**
- Renseignez l'**URL Watchtower** (ex. `http://10.0.0.1:8081`)
- Renseignez le **token API** (correspond à `WATCHTOWER_HTTP_API_TOKEN` sur Watchtower)
- Cliquez **Update Now** pour déclencher un pull & redémarrage immédiat

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

MIT
