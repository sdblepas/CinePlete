"""
Letterboxd tab + watchlist import routes.
  POST /api/import/watchlist
  GET  /api/letterboxd/urls
  POST /api/letterboxd/urls
  POST /api/letterboxd/urls/remove
  GET  /api/letterboxd/movies
  POST /api/letterboxd/refresh
"""
import threading as _threading
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Body

from app.config import load_config
from app.overrides import load_json, save_json, add_unique
from app.scanner import load_snapshot
from app.routers._shared import (
    log, OVERRIDES_FILE, LETTERBOXD_CACHE_FILE, _validate_url_for_fetch,
)

router = APIRouter()

# --------------------------------------------------
# Background refresh state
# --------------------------------------------------

_lb_lock       = _threading.Lock()
_lb_refreshing = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tmdb_search(api_key: str, title: str, year=None) -> int | None:
    """Search TMDB by title+year, return first matching TMDB ID or None."""
    params = {"api_key": api_key, "query": title, "include_adult": "false"}
    if year:
        params["year"] = str(year)
    try:
        r = requests.get(
            "https://api.themoviedb.org/3/search/movie",
            params=params,
            timeout=8,
        )
        results = r.json().get("results", [])
        return results[0]["id"] if results else None
    except Exception:
        return None


def _fetch_via_flaresolverr(rss_url: str, flaresolverr_url: str) -> bytes | None:
    """
    Route a request through FlareSolverr to bypass Cloudflare.
    Returns raw response bytes on success, None on failure.
    """
    if err := _validate_url_for_fetch(rss_url):
        log.warning(f"FlareSolverr fetch blocked ({err}): {rss_url}")
        return None
    base = flaresolverr_url.rstrip("/")
    try:
        resp = requests.post(
            f"{base}/v1",
            json={"cmd": "request.get", "url": rss_url, "maxTimeout": 60000},
            headers={"Content-Type": "application/json"},
            timeout=70,
        )
        data = resp.json()
        status = data.get("status")
        if status == "ok":
            content = data.get("solution", {}).get("response", "")
            if not content:
                log.debug(f"FlareSolverr: empty response body for {rss_url}")
                return None
            encoded = content.encode("utf-8") if isinstance(content, str) else content
            log.debug(f"FlareSolverr: got {len(encoded)} bytes for {rss_url}")
            return encoded
        else:
            log.debug(
                f"FlareSolverr: non-ok status '{status}' for {rss_url} — "
                f"message: {data.get('message','(none)')}"
            )
    except Exception as e:
        log.debug(f"FlareSolverr error for {rss_url}: {e}")
    return None


def _parse_films_from_html(html_text: str) -> list[dict]:
    """
    Extract film slugs/titles from Letterboxd HTML. Handles three formats:

    1. RSS description HTML — absolute URLs with inline title text:
         <a href="https://letterboxd.com/film/slug/">Title</a>

    2. List page poster grid — data-film-slug attribute:
         <div data-film-slug="the-godfather" ...>

    3. List page poster grid — data-target-link attribute (primary Letterboxd format):
         <div data-target-link="/film/the-godfather/" ...>

    Formats 2 and 3 convert slug → approximate title for TMDB fuzzy search.
    """
    import re
    skip = {"View the full list on Letterboxd", "here", "letterboxd.com"}
    seen: set = set()
    results = []

    # Format 1: absolute film URLs with visible title text (RSS description HTML)
    abs_pattern = re.compile(
        r'href="https://letterboxd\.com/film/([^/"]+)/"[^>]*>([^<]{1,120})</a>',
        re.IGNORECASE,
    )
    for m in abs_pattern.finditer(html_text):
        title = m.group(2).strip()
        slug  = m.group(1)
        if title and title not in skip and slug not in seen:
            seen.add(slug)
            results.append({"title": title})

    if results:
        return results

    # Format 2: data-film-slug attributes (poster divs on list/watchlist pages)
    slug_pattern = re.compile(r'data-film-slug="([^"]+)"', re.IGNORECASE)
    for m in slug_pattern.finditer(html_text):
        slug = m.group(1)
        if slug not in seen:
            seen.add(slug)
            results.append({"title": slug.replace("-", " ")})

    # Format 3: data-target-link="/film/slug/" (primary poster grid format)
    target_pattern = re.compile(r'data-target-link="/film/([^/"]+)/"', re.IGNORECASE)
    for m in target_pattern.finditer(html_text):
        slug = m.group(1)
        if slug not in seen:
            seen.add(slug)
            results.append({"title": slug.replace("-", " ")})

    log.debug(f"_parse_films_from_html: extracted {len(results)} films")
    return results


def _fetch_list_page_with_pagination(
    list_url: str, first_page_html: str, flaresolverr: str
) -> list[dict]:
    """
    Parse page 1 of a Letterboxd list page, then fetch pages 2..N if paginated.
    Letterboxd shows max 100 films per page.
    """
    films = _parse_films_from_html(first_page_html)

    import re
    page_nums = re.findall(r'/page/(\d+)/', first_page_html)
    if not page_nums:
        return films

    max_page = min(max(int(p) for p in page_nums), 20)  # safety cap at 20 pages
    if max_page < 2:
        return films

    log.debug(f"Letterboxd: list has {max_page} pages, fetching pages 2-{max_page}")
    base = list_url.rstrip("/")

    for page in range(2, max_page + 1):
        page_url     = f"{base}/page/{page}/"
        page_content = _fetch_via_flaresolverr(page_url, flaresolverr)
        if not page_content:
            log.debug(f"Letterboxd: failed to fetch page {page}, stopping pagination")
            break
        page_html  = page_content.decode("utf-8", errors="replace")
        page_films = _parse_films_from_html(page_html)
        if not page_films:
            log.debug(f"Letterboxd: page {page} returned 0 films, stopping")
            break
        log.debug(f"Letterboxd: page {page}/{max_page} → {len(page_films)} films")
        films.extend(page_films)

    return films


def _fetch_letterboxd_rss(url: str, _depth: int = 0, flaresolverr: str = "") -> list[dict]:
    """
    Fetch movies from a Letterboxd RSS feed.

    Accepts any public Letterboxd URL and derives the RSS endpoint:
      /username/watchlist/      → /username/watchlist/rss/
      /username/list/my-list/   → /username/list/my-list/rss/
      /username/rss/            → used as-is (diary or curator lists feed)
      /username/films/          → /username/rss/ (no /films/rss/ endpoint)

    Auto-expansion for curator accounts: if the RSS is a "lists feed" (items
    link to /list/ pages with no filmTitle/movieId), each linked list's RSS is
    fetched (one level deep, max 10 lists).
    """
    import defusedxml.ElementTree as ET

    path = urlparse(url).path.rstrip("/")

    if path.endswith("/rss"):
        rss_url = url.rstrip("/") + "/"
    elif path.endswith("/films"):
        username = path.lstrip("/").split("/")[0]
        rss_url = f"https://letterboxd.com/{username}/rss/"
    else:
        rss_url = url.rstrip("/") + "/rss/"

    # Guard against SSRF before making any outbound request
    if err := _validate_url_for_fetch(rss_url):
        log.warning(f"Letterboxd fetch blocked ({err}): {rss_url}")
        return []

    content: bytes | None = None
    try:
        resp = requests.get(
            rss_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; CinePlete/1.0)"},
            timeout=15,
            allow_redirects=True,
        )
        # Re-validate after redirect to guard against SSRF via open redirects
        if resp.url != rss_url:
            if err := _validate_url_for_fetch(resp.url):
                log.warning(f"Letterboxd redirect blocked ({err}): {resp.url}")
                return []

        if resp.status_code == 200:
            content = resp.content
        elif resp.status_code in (403, 404) and flaresolverr:
            # 403 = Cloudflare block, 404 = RSS endpoint doesn't exist for this list.
            # In both cases, fall through to the web page fallback below.
            log.debug(f"Letterboxd: HTTP {resp.status_code} on {rss_url}, will try list page via FlareSolverr")
        else:
            log.debug(f"Letterboxd: HTTP {resp.status_code} for {rss_url}")
    except requests.exceptions.RequestException:
        pass

    # If RSS fetch failed or returned no content, try the list web page directly.
    if not content and flaresolverr and rss_url.endswith("/rss/"):
        web_url     = rss_url[: -len("rss/")]
        log.debug(f"Letterboxd: no RSS content — fetching list page {web_url}")
        web_content = _fetch_via_flaresolverr(web_url, flaresolverr)
        if web_content:
            web_html = web_content.decode("utf-8", errors="replace")
            films    = _fetch_list_page_with_pagination(web_url, web_html, flaresolverr)
            if films:
                log.debug(f"Letterboxd: list page extracted {len(films)} titles from {web_url}")
                return films
        log.debug(f"Letterboxd: no films found for {rss_url}")
        return []

    if not content:
        return []

    # Detect whether we have XML or HTML before attempting parse
    content_str = content.decode("utf-8", errors="replace")
    is_xml = "<rss" in content_str[:500].lower() or "<?xml" in content_str[:500].lower()

    if not is_xml:
        # FlareSolverr returned HTML (browser-rendered RSS or Cloudflare page).
        # Try parsing for film anchor links directly in the rendered HTML.
        fallback = _parse_films_from_html(content_str)
        if fallback:
            log.debug(
                f"Letterboxd: non-XML response for {rss_url} — "
                f"extracted {len(fallback)} titles from rendered HTML"
            )
            return fallback
        log.warning(f"Letterboxd: no film links found in HTML response for {rss_url}")
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        log.warning(f"Letterboxd: XML parse error for {rss_url}")
        return _parse_films_from_html(content_str)

    def local(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    movies: list[dict] = []
    list_links: list[tuple[str, str]] = []

    for item in root.findall(".//item"):
        tmdb_id = title = year = None
        item_link: str | None = None
        item_desc: str        = ""

        for child in item:
            lname = local(child.tag)
            text  = (child.text or "").strip()
            if lname == "movieId" and text:
                try:
                    tmdb_id = int(text)
                except (ValueError, TypeError):
                    pass
            elif lname == "filmTitle" and text:
                title = text
            elif lname == "filmYear" and text:
                try:
                    year = int(text)
                except ValueError:
                    pass
            elif lname == "link" and text and "/list/" in text:
                item_link = text
            elif lname == "description" and text:
                item_desc = text

        if tmdb_id:
            movies.append({"tmdb_id": tmdb_id})
        elif title:
            movies.append({"title": title, "year": year})
        elif item_link:
            list_links.append((item_link, item_desc))

    _MAX_MOVIES_PER_FEED = 500   # cap to prevent thousands of TMDB calls per URL

    if not movies and list_links and _depth == 0:
        log.debug(
            f"Letterboxd: lists feed at {rss_url} — expanding {len(list_links)} lists"
        )
        for list_url, desc_html in list_links[:10]:
            if len(movies) >= _MAX_MOVIES_PER_FEED:
                log.debug(f"Letterboxd: reached {_MAX_MOVIES_PER_FEED}-movie cap, stopping expansion")
                break
            child_movies = _fetch_letterboxd_rss(list_url, _depth=1, flaresolverr=flaresolverr)
            if child_movies:
                movies.extend(child_movies)
            elif desc_html:
                fallback = _parse_films_from_html(desc_html)
                log.debug(
                    f"Letterboxd: list RSS blocked for {list_url}, "
                    f"extracted {len(fallback)} titles from description"
                )
                movies.extend(fallback)

    return movies[:_MAX_MOVIES_PER_FEED]


def _validate_letterboxd_url(url: str):
    """Return (cleaned_url, error_string_or_None)."""
    url = url.strip()
    if not url:
        return None, "URL is required"
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None, "Invalid URL"
    host = parsed.netloc.lower().replace("www.", "")
    if "letterboxd.com" not in host:
        return None, "Only Letterboxd URLs are supported"
    return url, None


def _lb_do_refresh() -> None:
    """Background worker: fetches all saved Letterboxd URLs and writes cache."""
    global _lb_refreshing
    try:
        from app.tmdb import TMDB
        from collections import Counter as _Counter

        cfg          = load_config()
        api_key      = cfg.get("TMDB", {}).get("TMDB_API_KEY", "")
        flaresolverr = cfg.get("FLARESOLVERR", {}).get("FLARESOLVERR_URL", "").rstrip("/")
        if not api_key:
            log.warning("Letterboxd refresh skipped — TMDB API key not configured")
            return

        ov   = load_json(OVERRIDES_FILE)
        urls = ov.get("letterboxd_urls", [])
        if not urls:
            save_json(LETTERBOXD_CACHE_FILE, {
                "ok": True, "movies": [], "urls": [], "unique": 0,
                "owned_count": 0, "url_status": [], "fetched_at": _now_iso(),
            })
            return

        counts:     _Counter      = _Counter()
        url_status: list[dict]    = []

        for lb_url in urls:
            raw      = _fetch_letterboxd_rss(lb_url, flaresolverr=flaresolverr)
            seen:set = set()
            resolved = 0
            for item in raw:
                tid = item.get("tmdb_id")
                if not tid and item.get("title"):
                    tid = _tmdb_search(api_key, item["title"], item.get("year"))
                if tid and tid not in seen:
                    counts[tid] += 1
                    seen.add(tid)
                    resolved += 1
            url_status.append({"url": lb_url, "raw": len(raw), "resolved": resolved})
            log.debug(f"Letterboxd refresh: {lb_url} → {len(raw)} raw, {resolved} resolved")

        t           = TMDB(api_key)
        wishlist    = set(ov.get("wishlist_movies", []))
        ignored     = set(ov.get("ignore_movies",  []))
        owned       = load_snapshot()
        movies      = []
        owned_count = 0

        for tid, score in counts.most_common():
            if tid in ignored:
                continue
            if tid in owned:
                owned_count += 1
                continue
            md = t.get(f"https://api.themoviedb.org/3/movie/{tid}?api_key={api_key}")
            if not md or md.get("success") is False:
                continue
            movies.append({
                "tmdb":     tid,
                "title":    md.get("title"),
                "year":     (md.get("release_date") or "")[:4],
                "poster":   t.poster_url(md.get("poster_path")),
                "rating":   md.get("vote_average", 0),
                "score":    score,
                "wishlist": tid in wishlist,
            })

        movies.sort(key=lambda m: (-m["score"], -(m["rating"] or 0)))

        save_json(LETTERBOXD_CACHE_FILE, {
            "ok":          True,
            "movies":      movies,
            "urls":        urls,
            "unique":      len(counts),
            "owned_count": owned_count,
            "url_status":  url_status,
            "fetched_at":  _now_iso(),
        })
        log.info(
            f"Letterboxd refresh complete: {len(movies)} movies "
            f"(owned filtered: {owned_count})"
        )

    except Exception:
        log.exception("Letterboxd background refresh failed")
    finally:
        with _lb_lock:
            _lb_refreshing = False


def _lb_start_refresh() -> bool:
    """Spawn a background refresh thread. Returns True if started, False if already running."""
    global _lb_refreshing
    with _lb_lock:
        if _lb_refreshing:
            return False
        _lb_refreshing = True
    _threading.Thread(target=_lb_do_refresh, daemon=True, name="lb-refresh").start()
    log.debug("Letterboxd background refresh started")
    return True


# --------------------------------------------------
# Watchlist import (legacy single-shot endpoint)
# --------------------------------------------------

@router.post("/api/import/watchlist")
def import_watchlist(payload: dict = Body(...)):
    """
    Import movies from a public Letterboxd URL into the wishlist via RSS.
    Supports: watchlist, named lists, diary feed (/rss/), and /films/ pages.
    """
    url = str(payload.get("url", "")).strip()
    if not url:
        return {"ok": False, "error": "URL is required"}

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return {"ok": False, "error": "Invalid URL"}

    host = parsed.netloc.lower().replace("www.", "")
    if "letterboxd.com" not in host:
        return {"ok": False, "error": "Only Letterboxd URLs are supported"}

    cfg          = load_config()
    api_key      = cfg.get("TMDB", {}).get("TMDB_API_KEY", "")
    flaresolverr = cfg.get("FLARESOLVERR", {}).get("FLARESOLVERR_URL", "").rstrip("/")

    raw = _fetch_letterboxd_rss(url, flaresolverr=flaresolverr)
    if not raw:
        return {"ok": False, "error": "No movies found — check the URL is a public Letterboxd list or watchlist"}

    ov       = load_json(OVERRIDES_FILE)
    existing = set(ov.get("wishlist_movies", []))
    added    = 0
    skipped  = 0

    for item in raw:
        tmdb_id = item.get("tmdb_id")
        if not tmdb_id:
            if not api_key:
                skipped += 1
                continue
            tmdb_id = _tmdb_search(api_key, item["title"], item.get("year"))
        if not tmdb_id or tmdb_id in existing:
            skipped += 1
            continue
        add_unique(ov["wishlist_movies"], tmdb_id)
        existing.add(tmdb_id)
        added += 1

    save_json(OVERRIDES_FILE, ov)
    return {"ok": True, "added": added, "skipped": skipped, "total": added + skipped}


# --------------------------------------------------
# Letterboxd tab — persistent URL list + scored movies
# --------------------------------------------------

@router.get("/api/letterboxd/urls")
def letterboxd_get_urls():
    ov = load_json(OVERRIDES_FILE)
    return {"ok": True, "urls": ov.get("letterboxd_urls", [])}


@router.post("/api/letterboxd/urls")
def letterboxd_add_url(payload: dict = Body(...)):
    url, err = _validate_letterboxd_url(str(payload.get("url", "")))
    if err:
        return {"ok": False, "error": err}
    ov = load_json(OVERRIDES_FILE)
    ov.setdefault("letterboxd_urls", [])
    if len(ov["letterboxd_urls"]) >= 50:
        return {"ok": False, "error": "Maximum 50 Letterboxd URLs allowed"}
    if url not in ov["letterboxd_urls"]:
        ov["letterboxd_urls"].append(url)
        save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@router.post("/api/letterboxd/urls/remove")
def letterboxd_remove_url(payload: dict = Body(...)):
    url  = str(payload.get("url", "")).strip()
    ov   = load_json(OVERRIDES_FILE)
    urls = ov.get("letterboxd_urls", [])
    if url in urls:
        urls.remove(url)
        save_json(OVERRIDES_FILE, ov)
    return {"ok": True}


@router.get("/api/letterboxd/movies")
def letterboxd_get_movies():
    """
    Return cached Letterboxd movies immediately — never fetches live.
    Cache is written by _lb_do_refresh() running in a background thread.
    """
    with _lb_lock:
        currently_refreshing = _lb_refreshing
    cache = load_json(LETTERBOXD_CACHE_FILE)
    if not cache:
        ov   = load_json(OVERRIDES_FILE)
        urls = ov.get("letterboxd_urls", [])
        return {
            "ok":            True,
            "movies":        [],
            "urls":          urls,
            "fetched_at":    None,
            "refreshing":    currently_refreshing,
            "needs_refresh": bool(urls) and not currently_refreshing,
        }
    return {**cache, "refreshing": currently_refreshing}


@router.post("/api/letterboxd/refresh")
def letterboxd_trigger_refresh():
    """Kick off a background refresh of all Letterboxd URLs. Returns immediately."""
    started = _lb_start_refresh()
    with _lb_lock:
        refreshing = _lb_refreshing
    return {"ok": True, "started": started, "refreshing": refreshing}
