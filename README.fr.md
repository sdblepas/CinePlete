# 🎬 Cineplete — Audit Plex, Jellyfin & Emby

[![Build & Publish Docker](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml/badge.svg)](https://github.com/sdblepas/CinePlete/actions/workflows/docker.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/sdblepas/cineplete)](https://hub.docker.com/r/sdblepas/cineplete)
[![Docker Image Version](https://img.shields.io/docker/v/sdblepas/cineplete/latest)](https://hub.docker.com/r/sdblepas/cineplete)
![License](https://img.shields.io/github/license/sdblepas/CinePlete)

![Plex](https://img.shields.io/badge/Plex-compatible-orange)
![Jellyfin](https://img.shields.io/badge/Jellyfin-compatible-7B2FBE)
![Emby](https://img.shields.io/badge/Emby-compatible-00A4DC)
![Trakt](https://img.shields.io/badge/Trakt-integration-ED2224)
![Proxmox](https://img.shields.io/badge/Proxmox-LXC--ready-E57000?logo=proxmox&logoColor=white)

> 🇬🇧 [English version](README.md)

---

## Présentation

**Cineplete** est un outil Docker auto-hébergé permettant d'analyser une bibliothèque **Plex, Jellyfin ou Emby** et de détecter :

- Les films manquants dans les sagas
- Les films manquants de réalisateurs déjà présents
- Les films populaires d'acteurs présents
- Les classiques absents
- Les suggestions personnalisées basées sur votre bibliothèque
- Les problèmes de métadonnées
- La gestion d'une wishlist
- L'intégration Radarr

L'outil propose une **interface web avec graphiques**, un **onglet Logs** pour le diagnostic, et un **scan ultra rapide** (~2 secondes avec Plex). Les trois serveurs multimédia sont sélectionnables depuis l'onglet Config, sans redémarrage.

---

## Fonctionnalités

### Support Plex, Jellyfin & Emby

Cineplete prend en charge trois serveurs multimédia, sélectionnables depuis l'onglet Config :

- **Plex** — utilise l'API XML native (~2s pour 1000 films)
- **Jellyfin** — utilise l'API HTTP Jellyfin, avec bouton **Test de connexion** intégré
- **Emby** — utilise l'API HTTP Emby (préfixe `/emby/`), identifiants : URL + clé API

---

### Support multi-bibliothèques

**Nouveau en v3.0 :** Scannez plusieurs bibliothèques simultanément — combinez Plex et Jellyfin, ou connectez plusieurs serveurs.

**Fonctionnalités clés :**
- **Scan concurrent** — toutes les bibliothèques actives scannées en parallèle avec ThreadPoolExecutor
- **Résultats fusionnés** — les doublons détectés automatiquement entre bibliothèques (même ID TMDB)
- **Activation par bibliothèque** — activez/désactivez individuellement depuis l'onglet Config
- **Tableau de bord unifié** — tous les graphiques et onglets affichent les données fusionnées
- **Optimisation progressive** — les bibliothèques inchangées ignorent la ré-analyse (2-3 minutes → 2 secondes)

**Cas d'usage :**
- Scanner à la fois Plex (serveur principal) + Jellyfin (serveur 4K)
- Plusieurs serveurs Plex (ex. local + distant)
- Bibliothèques séparées (Films + Animés + Films étrangers)
- Mélanger types de serveurs dans un seul déploiement

**Configuration :**

Les bibliothèques sont gérées depuis **Config → Bibliothèques**. Chaque bibliothèque possède :
- **Type** — `plex`, `jellyfin` ou `emby`
- **Activée** — bascule on/off sans supprimer les identifiants
- **Label** — nom convivial (affiché dans la progression du scan)
- **Paramètres de connexion** — URL, token/clé API, nom de bibliothèque

**Exemple config.yml :**

```yaml
LIBRARIES:
  - id: "plex-main"
    type: "plex"
    enabled: true
    label: "Plex Principal"
    url: "http://192.168.1.10:32400"
    token: "xxxxxxxxxxxx"
    library_name: "Films"
    page_size: 500
    short_movie_limit: 60

  - id: "jellyfin-4k"
    type: "jellyfin"
    enabled: true
    label: "Jellyfin 4K"
    url: "http://192.168.1.20:8096"
    api_key: "xxxxxxxxxxxx"
    library_name: "Films 4K"
    page_size: 500
    short_movie_limit: 60

  - id: "emby-main"
    type: "emby"
    enabled: true
    label: "Emby Principal"
    url: "http://192.168.1.30:8096"
    api_key: "xxxxxxxxxxxx"
    library_name: "Films"
    page_size: 500
    short_movie_limit: 60
```

**Migration automatique depuis v2.x :**

L'ancienne configuration (paramètre unique `MEDIA_SERVER`) migre automatiquement vers le nouveau format `LIBRARIES` au premier démarrage. Aucune action manuelle requise — votre configuration existante continue de fonctionner.

**Performance :**

Avec 2 bibliothèques (1000 films chacune) :
- Séquentiel : 4 secondes (Plex) + 6 secondes (Jellyfin) = 10 secondes
- **Concurrent : ~6 secondes** (scan parallèle)

---

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

### Intégration Trakt.tv

Connectez votre compte Trakt pour afficher votre historique de visionnage sur chaque carte film et masquer optionnellement les films déjà vus dans toutes les grilles.

**Configuration :**
1. Créez une application sur [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications) pour obtenir un **Client ID** et un **Client Secret**.
2. Dans CinePlete, allez dans **Config → Trakt.tv**, saisissez vos identifiants et cliquez sur **Connect**.
3. Un code apparaît — rendez-vous sur [trakt.tv/activate](https://trakt.tv/activate) et entrez-le.
4. CinePlete interroge Trakt automatiquement et sauvegarde vos tokens une fois autorisé.

**Fonctionnalités :**
- 🔴 **Badge Vu** — un ruban rouge apparaît sur chaque carte film présent dans votre historique Trakt
- 🚫 **Masquer les films vus** — activez *Hide watched movies from all grids* pour retirer les films vus des onglets Sagas, Réalisateurs, Acteurs, Classiques et Suggestions (la Wishlist affiche toujours tous les films)
- ⟳ **Actualisation manuelle** — cliquez *Refresh history* pour forcer une mise à jour immédiate (cache serveur de 1 heure)
- 🔌 **Déconnecter** — supprime les tokens de `config.yml` immédiatement ; reconnectez-vous à tout moment

**Référence config :**

```yaml
TRAKT:
  TRAKT_ENABLED: true
  TRAKT_CLIENT_ID: "votre_client_id"
  TRAKT_CLIENT_SECRET: "votre_client_secret"
  TRAKT_ACCESS_TOKEN: ""      # rempli automatiquement après connexion
  TRAKT_REFRESH_TOKEN: ""     # rempli automatiquement après connexion
  TRAKT_USERNAME: ""          # rempli automatiquement après connexion
  TRAKT_HIDE_WATCHED: false
```

> Trakt utilise le flux **Device Code OAuth** — aucun URI de redirection requis, fonctionne derrière NAT et reverse proxies. Les tokens sont rafraîchis automatiquement à l'expiration.

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
| `TMDB_API_KEY` | Clé API TMDB classique (v3) — **pas** le Read Access Token |

> ⚠️ Utiliser la **clé API** disponible sous TMDB → Paramètres → API → **Clé API** (chaîne alphanumérique courte). Ne **pas** utiliser le Read Access Token (longue chaîne JWT commençant par `eyJ`).

**Bibliothèques (v3.0+) :**

Les bibliothèques sont configurées depuis **Config → Bibliothèques** dans l'interface. Chaque entrée inclut :

| Clé | Requis | Description |
|-----|--------|-------------|
| `id` | Oui | Identifiant unique (ex. `plex-0`, `jellyfin-4k`) |
| `type` | Oui | `plex`, `jellyfin` ou `emby` |
| `enabled` | Oui | `true` pour scanner, `false` pour ignorer |
| `label` | Non | Nom convivial affiché dans la progression du scan |
| `url` | Oui | URL du serveur (ex. `http://192.168.1.10:32400`) |
| `token` | Plex uniquement | Token d'authentification Plex |
| `api_key` | Jellyfin / Emby uniquement | Clé API Jellyfin ou Emby |
| `library_name` | Oui | Nom de la bibliothèque films |
| `page_size` | Non | Taille de page API (défaut : 500) |
| `short_movie_limit` | Non | Ignorer les films < N minutes (défaut : 60) |

**Exemple de configuration multi-bibliothèques :**

```yaml
LIBRARIES:
  - id: "plex-main"
    type: "plex"
    enabled: true
    label: "Plex Principal"
    url: "http://192.168.1.10:32400"
    token: "xxxxxxxxxxxx"
    library_name: "Films"

  - id: "jellyfin-4k"
    type: "jellyfin"
    enabled: false
    label: "Jellyfin 4K"
    url: "http://192.168.1.20:8096"
    api_key: "xxxxxxxxxxxx"
    library_name: "Films 4K"

  - id: "emby-main"
    type: "emby"
    enabled: false
    label: "Emby Principal"
    url: "http://192.168.1.30:8096"
    api_key: "xxxxxxxxxxxx"
    library_name: "Films"
```

> **Configuration héritée (v2.x) :** Les anciens paramètres plats `PLEX_URL`, `PLEX_TOKEN`, `JELLYFIN_URL` fonctionnent toujours et migrent automatiquement vers le format `LIBRARIES` au premier chargement.

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

### Option 1 — LXC / VM / Bare Metal générique (Debian · Ubuntu · Raspberry Pi)

En une commande — à exécuter dans votre conteneur ou VM :

```bash
curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | sudo bash
```

Ce script : installe Python 3.11+, crée un utilisateur dédié `cineplete`, télécharge la dernière version, configure un virtualenv Python et enregistre un service systemd qui démarre automatiquement au boot.

**Relancer la même commande suffit pour mettre à jour.**

Gestion après installation :
```bash
journalctl -u cineplete -f          # logs en direct
systemctl restart cineplete          # redémarrer
systemctl status cineplete           # statut
```

---

### Option 2 — LXC Proxmox (une commande sur l'hôte Proxmox)

À exécuter **sur votre hôte Proxmox** en root — crée un LXC Debian 12 non privilégié et installe CinePlete à l'intérieur automatiquement :

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/proxmox-lxc.sh)"
```

**Avec options personnalisées :**
```bash
CT_ID=200 CT_IP=192.168.1.50/24 CT_GW=192.168.1.1 CT_RAM=1024 \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/proxmox-lxc.sh)"
```

| Variable | Défaut | Description |
|----------|--------|-------------|
| `CT_ID` | prochain disponible | ID du conteneur LXC |
| `CT_IP` | `dhcp` | IP statique en notation CIDR (ex. `192.168.1.50/24`) |
| `CT_GW` | _(aucune)_ | Passerelle pour l'IP statique |
| `CT_CORES` | `2` | Nombre de cœurs CPU |
| `CT_RAM` | `512` | RAM en Mo |
| `CT_DISK` | `4` | Disque en Go |
| `CT_BRIDGE` | `vmbr0` | Bridge réseau |
| `PORT` | `7474` | Port d'écoute de l'application |

Gestion après installation depuis l'hôte Proxmox :
```bash
pct exec <CT_ID> -- journalctl -u cineplete -f     # logs en direct
pct exec <CT_ID> -- bash                            # ouvrir un shell
# Mise à jour :
pct exec <CT_ID> -- bash -c "curl -fsSL https://raw.githubusercontent.com/sdblepas/CinePlete/main/install/install.sh | bash"
```

---

### Option 3 — Docker Compose (recommandé)

```bash
docker compose up -d
```

Ouvrir l'interface :

```
http://IP_DU_NAS:8787
```

---

## Architecture

```
Serveur Plex         Serveur Jellyfin         Serveur Emby
     │                      │                      │
     │ API XML               │ API REST HTTP         │ API REST HTTP
     │ (~2s/1000 films)      │ (paginée)             │ (préfixe /emby/)
     ▼                      ▼                      ▼
 plex_xml.py         jellyfin_api.py          emby_api.py
  (IDs TMDB,          (IDs TMDB,               (IDs TMDB,
   réalisateurs,       réalisateurs,            réalisateurs,
   acteurs,            acteurs,                 acteurs,
   doublons)           top 5/film)              top 5/film)
       \                   |                   /
        └──────────── scan_movies() ──────────┘
                           │
                           ▼
            Moteur de scan 8 étapes — scanner.py (thread en arrière-plan)
                           │
     ┌─────────────────────┼──────────────────────┐
     ▼                     ▼                       ▼
  Sagas               Réalisateurs            Acteurs
 (collections TMDB)   (person_credits)        (vote_count ≥ 500)
     │                     │                       │
     └─────────── Client API TMDB — tmdb.py ───────┘
                  (thread-safe, cache disque,
                   clé normalisée, flush/50 appels)
                           │
     ┌─────────────────────┼──────────────────────┐
     ▼                     ▼                       ▼
  Classiques           Suggestions             Scores
 (Top Rated TMDB)    (recommandations        (sagas / réalisateurs /
                      scorées par nombre      classiques / global)
                      de correspondances)
                           │
                           ▼
                     results.json ◄──── overrides.json
                     (volume /data)     (wishlist, ignores,
                           │            letterboxd_urls,
                           ▼            rec_fetched_ids)
                   FastAPI — web.py
                   (42 endpoints API)
         ┌─────────────────┼──────────────────┐
         ▼                 ▼                  ▼
    Radarr / 4K      Overseerr /         Letterboxd
    (ajout, statut,  Jellyseerr          (RSS → TMDB,
     grab poller)    (requête)           fusion multi-URL,
         │                               FlareSolverr)
         ▼
    Telegram
    (résumé scan +
     notifications grab)
                           │
                           ▼
         Application monopage — static/js/
    ┌────────┬────────┬────────┬─────────┬─────────┬────────┬────────┐
    │ app.js │scan.js │ api.js │render.js│config.js│filters │modal.js│
    │routing │polling │ fetch  │onglets/ │config   │recherch│modal   │
    │état    │progres │toast   │cartes / │form /   │filtre/ │détail /│
    │nav     │badges  │utils   │graphes  │cache    │tri     │bande-a │
    └────────┴────────┴────────┴─────────┴─────────┴────────┴────────┘
```

---

## Licence

MIT
