/* ============================================================
   cards.js — pure HTML card builders (no DOM writes, no API)
   Depends on: api.js (escHtml, tag, CONFIG)
============================================================ */

/* ── Poster card (primary grid layout) ─────────────────────── */

function posterCard(m, extraTag = "") {
  const tmdb     = m.tmdb
  const safeName = (m.title || "").replace(/'/g, "\\'").replace(/"/g, "&quot;")

  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="event.stopPropagation();addToRadarr(${tmdb},'${safeName}',this)">+ Radarr</button>`
    : ""
  const radarr4kBtn = CONFIG?.RADARR_4K?.RADARR_4K_ENABLED
    ? `<button class="btn-sm btn-radarr" style="opacity:.75" onclick="event.stopPropagation();addToRadarr4k(${tmdb},'${safeName}',this)">+ 4K</button>`
    : ""
  const overseerrBtn = CONFIG?.OVERSEERR?.OVERSEERR_ENABLED
    ? (overseerrRequested?.has(tmdb)
        ? `<button class="btn-sm" style="color:var(--green)" disabled>✓ Requested</button>`
        : `<button class="btn-sm btn-overseerr" onclick="event.stopPropagation();addToOverseerr(${tmdb},'${safeName}',this)">→ OS</button>`)
    : ""
  const jellyseerrBtn = CONFIG?.JELLYSEERR?.JELLYSEERR_ENABLED
    ? (jellyseerrRequested?.has(tmdb)
        ? `<button class="btn-sm" style="color:var(--green)" disabled>✓ Requested</button>`
        : `<button class="btn-sm btn-jellyseerr" onclick="event.stopPropagation();addToJellyseerr(${tmdb},'${safeName}',this)">→ JS</button>`)
    : ""

  // Encode movie data on the button so add/remove toggles can update DATA without extra API calls
  const movieData = JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,rating:m.rating,wishlist:m.wishlist}).replace(/"/g,'&quot;')
  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" data-movie="${movieData}" onclick="event.stopPropagation();removeWishlist(${tmdb},this)">★</button>`
    : `<button class="btn-sm btn-wishlist"   data-movie="${movieData}" onclick="event.stopPropagation();addWishlist(${tmdb},this)">☆</button>`

  const ignoreBtn = `<button class="btn-sm btn-ignore" title="Don't want this"
    onclick="event.stopPropagation();ignoreMovie(${tmdb},'${safeName}',${m.year||"null"},'${m.poster||""}',this)">🚫</button>`

  const rating = parseFloat(m.rating || 0).toFixed(1)

  const imgHtml = m.poster
    ? `<img class="pc-img" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="pc-no-img"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 2v20M17 2v20M2 12h20"/></svg><span>No Image</span></div>`

  const mSafe = JSON.stringify({ tmdb: m.tmdb, title: m.title, year: m.year, poster: m.poster, wishlist: m.wishlist })
    .replace(/'/g, "\\'")

  return `
  <div class="pc" data-tmdb="${tmdb}" onclick="openMovieModal(${tmdb},${mSafe.replace(/"/g,'&quot;')})">
    <input type="checkbox" class="pc-check"
      data-movie="${mSafe.replace(/"/g,'&quot;')}"
      onclick="event.stopPropagation();toggleSelect(${tmdb},${mSafe.replace(/"/g,'&quot;')},this,event)"
      title="Select"/>
    ${imgHtml}
    <div class="pc-info">
      <div class="pc-title" title="${escHtml(m.title||"")}">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-meta">
        <span class="pc-rating">⭐ ${rating}</span>
        ${m.year ? `<span>${m.year}</span>` : ""}
        ${extraTag}
      </div>
    </div>
    <div class="pc-overlay">
      <div class="pc-overlay-title">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-overlay-actions">${wBtn}${radarrBtn}${radarr4kBtn}${overseerrBtn}${jellyseerrBtn}${ignoreBtn}</div>
    </div>
  </div>`
}

/* ── Legacy horizontal card (kept for backward compat) ─────── */

function movieCard(m, extraTag = ""){
  const poster = m.poster
    ? `<img class="movie-poster" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="movie-poster-placeholder">NO<br>IMG</div>`

  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="addToRadarr(${m.tmdb},'${(m.title||'').replace(/'/g,"\\'")}',this)">+ Radarr</button>`
    : ""

  const _mData = JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,rating:m.rating,wishlist:m.wishlist}).replace(/"/g,'&quot;')
  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" data-movie="${_mData}" onclick="removeWishlist(${m.tmdb},this)">★ Wishlisted</button>`
    : `<button class="btn-sm btn-wishlist"   data-movie="${_mData}" onclick="addWishlist(${m.tmdb},this)">☆ Wishlist</button>`

  const rating = parseFloat(m.rating||0).toFixed(1)
  const pop    = Math.round(m.popularity||0)

  return `
  <div class="movie-card" onclick="openMovieModal(${m.tmdb},${JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,wishlist:m.wishlist}).replace(/"/g,'&quot;')})">
    <div class="movie-card-inner">
      ${poster}
      <div class="movie-body">
        <div class="movie-title">${escHtml(m.title||"Untitled")} <span class="movie-year">${m.year?`(${m.year})`:""}</span></div>
        <div class="movie-meta">
          ${tag(`⭐ ${rating}`,"tag-gold")}
          ${m.votes ? tag(`${(m.votes/1000).toFixed(0)}k votes`) : ""}
          ${pop ? tag(`↑${pop}`) : ""}
          ${extraTag}
        </div>
        <div class="movie-actions">${wBtn}${radarrBtn}</div>
      </div>
    </div>
  </div>`
}

/* ── Letterboxd poster card ─────────────────────────────────── */

function lbPosterCard(m) {
  const tmdb     = m.tmdb
  const safeName = (m.title || "").replace(/'/g, "\\'").replace(/"/g, "&quot;")
  const score    = m.score || 1

  const scoreBadge = score > 1
    ? `<div style="position:absolute;top:6px;right:6px;background:var(--gold);color:#000;
                   font-size:.62rem;font-weight:700;font-family:'Syne',sans-serif;
                   border-radius:5px;padding:2px 7px;z-index:2;line-height:1.5;
                   box-shadow:0 1px 4px rgba(0,0,0,.4)">×${score}</div>`
    : ""

  const _lbData = JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,rating:m.rating,wishlist:m.wishlist}).replace(/"/g,'&quot;')
  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" data-movie="${_lbData}" onclick="event.stopPropagation();removeWishlist(${tmdb},this)">★</button>`
    : `<button class="btn-sm btn-wishlist"   data-movie="${_lbData}" onclick="event.stopPropagation();addWishlist(${tmdb},this)">☆ Wishlist</button>`

  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="event.stopPropagation();addToRadarr(${tmdb},'${safeName}',this)">+ Radarr</button>`
    : ""

  const rating  = parseFloat(m.rating || 0).toFixed(1)
  const imgHtml = m.poster
    ? `<img class="pc-img" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="pc-no-img"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 2v20M17 2v20M2 12h20"/></svg><span>No Image</span></div>`

  const mSafe = JSON.stringify({ tmdb: m.tmdb, title: m.title, year: m.year, poster: m.poster, wishlist: m.wishlist })
    .replace(/'/g, "\\'")

  return `
  <div class="pc" style="position:relative"
    onclick="openMovieModal(${tmdb},${mSafe.replace(/"/g,'&quot;')})">
    ${scoreBadge}
    <input type="checkbox" class="pc-check"
      data-movie="${mSafe.replace(/"/g,'&quot;')}"
      onclick="event.stopPropagation();toggleSelect(${tmdb},${mSafe.replace(/"/g,'&quot;')},this,event)"
      title="Select"/>
    ${imgHtml}
    <div class="pc-info">
      <div class="pc-title" title="${escHtml(m.title||"")}">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-meta">
        <span class="pc-rating">⭐ ${rating}</span>
        ${m.year ? `<span>${m.year}</span>` : ""}
      </div>
    </div>
    <div class="pc-overlay">
      <div class="pc-overlay-title">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-overlay-actions">${wBtn}${radarrBtn}</div>
    </div>
  </div>`
}

/* ── Suggestion poster card ─────────────────────────────────── */

function suggestionCard(m) {
  const tmdb     = m.tmdb
  const safeName = (m.title || "").replace(/'/g, "\\'").replace(/"/g, "&quot;")
  const score    = m.rec_score || 0
  const sources  = m.sources  || []

  const scoreBadge = score
    ? `<div style="position:absolute;top:6px;right:6px;background:rgba(0,0,0,.72);
                   border:1px solid rgba(255,197,61,.4);color:var(--gold);
                   font-size:.62rem;font-weight:700;font-family:'Syne',sans-serif;
                   border-radius:5px;padding:2px 7px;z-index:2;line-height:1.5;
                   box-shadow:0 1px 4px rgba(0,0,0,.5)">⚡${score}</div>`
    : ""

  const radarrBtn   = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="event.stopPropagation();addToRadarr(${tmdb},'${safeName}',this)">+ Radarr</button>`
    : ""
  const radarr4kBtn = CONFIG?.RADARR_4K?.RADARR_4K_ENABLED
    ? `<button class="btn-sm btn-radarr" style="opacity:.75" onclick="event.stopPropagation();addToRadarr4k(${tmdb},'${safeName}',this)">+ 4K</button>`
    : ""
  const overseerrBtn  = CONFIG?.OVERSEERR?.OVERSEERR_ENABLED
    ? (overseerrRequested?.has(tmdb)
        ? `<button class="btn-sm" style="color:var(--green)" disabled>✓ Requested</button>`
        : `<button class="btn-sm btn-overseerr" onclick="event.stopPropagation();addToOverseerr(${tmdb},'${safeName}',this)">→ OS</button>`)
    : ""
  const jellyseerrBtn = CONFIG?.JELLYSEERR?.JELLYSEERR_ENABLED
    ? (jellyseerrRequested?.has(tmdb)
        ? `<button class="btn-sm" style="color:var(--green)" disabled>✓ Requested</button>`
        : `<button class="btn-sm btn-jellyseerr" onclick="event.stopPropagation();addToJellyseerr(${tmdb},'${safeName}',this)">→ JS</button>`)
    : ""

  const movieData = JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,rating:m.rating,wishlist:m.wishlist}).replace(/"/g,'&quot;')
  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" data-movie="${movieData}" onclick="event.stopPropagation();removeWishlist(${tmdb},this)">★</button>`
    : `<button class="btn-sm btn-wishlist"   data-movie="${movieData}" onclick="event.stopPropagation();addWishlist(${tmdb},this)">☆</button>`
  const ignoreBtn = `<button class="btn-sm btn-ignore" title="Don't want this"
    onclick="event.stopPropagation();ignoreMovie(${tmdb},'${safeName}',${m.year||"null"},'${m.poster||""}',this)">🚫</button>`

  const rating  = parseFloat(m.rating || 0).toFixed(1)
  const imgHtml = m.poster
    ? `<img class="pc-img" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="pc-no-img"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 2v20M17 2v20M2 12h20"/></svg><span>No Image</span></div>`

  const mSafe = JSON.stringify({ tmdb: m.tmdb, title: m.title, year: m.year, poster: m.poster, wishlist: m.wishlist })
    .replace(/'/g, "\\'")

  return `
  <div class="pc" data-tmdb="${tmdb}"
    ${sources.length ? `title="From: ${escHtml(sources.join(', '))}"` : ''}
    onclick="openMovieModal(${tmdb},${mSafe.replace(/"/g,'&quot;')})">
    ${scoreBadge}
    <input type="checkbox" class="pc-check"
      data-movie="${mSafe.replace(/"/g,'&quot;')}"
      onclick="event.stopPropagation();toggleSelect(${tmdb},${mSafe.replace(/"/g,'&quot;')},this,event)"
      title="Select"/>
    ${imgHtml}
    <div class="pc-info">
      <div class="pc-title" title="${escHtml(m.title||"")}">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-meta">
        <span class="pc-rating">⭐ ${rating}</span>
        ${m.year ? `<span>${m.year}</span>` : ""}
      </div>
    </div>
    <div class="pc-overlay">
      <div class="pc-overlay-title">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-overlay-actions">${wBtn}${radarrBtn}${radarr4kBtn}${overseerrBtn}${jellyseerrBtn}${ignoreBtn}</div>
    </div>
  </div>`
}

/* ── Quality upgrade card ───────────────────────────────────── */

function upgradeCard(m, qualityBadge = "") {
  const tmdb     = m.tmdb
  const safeName = (m.title || "").replace(/'/g, "\\'").replace(/"/g, "&quot;")
  const rating   = parseFloat(m.rating || 0).toFixed(1)

  const radarr4kBtn = CONFIG?.RADARR_4K?.RADARR_4K_ENABLED
    ? `<button class="btn-sm btn-radarr" style="opacity:.9"
         onclick="event.stopPropagation();upgradeToRadarr4k(${tmdb},'${safeName}',this)">→ 4K</button>`
    : `<span style="font-size:.65rem;color:var(--text3)">Enable Radarr 4K</span>`

  const movieData = JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,rating:m.rating,wishlist:m.wishlist}).replace(/"/g,'&quot;')
  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" data-movie="${movieData}" onclick="event.stopPropagation();removeWishlist(${tmdb},this)">★</button>`
    : `<button class="btn-sm btn-wishlist"   data-movie="${movieData}" onclick="event.stopPropagation();addWishlist(${tmdb},this)">☆</button>`

  const imgHtml = m.poster
    ? `<img class="pc-img" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="pc-no-img"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 2v20M17 2v20M2 12h20"/></svg><span>No Image</span></div>`

  const mSafe = JSON.stringify({ tmdb: m.tmdb, title: m.title, year: m.year, poster: m.poster, wishlist: m.wishlist })
    .replace(/'/g, "\\'")

  // Quality resolution badge — absolute top-left
  const resBadge = m.resolution
    ? `<div style="position:absolute;top:6px;left:6px;background:rgba(0,0,0,.72);
                   border:1px solid rgba(255,255,255,.15);color:var(--text2);
                   font-size:.6rem;font-weight:700;font-family:'Syne',sans-serif;
                   border-radius:4px;padding:2px 6px;z-index:2;line-height:1.5">${m.resolution}p</div>`
    : ""

  return `
  <div class="pc" data-tmdb="${tmdb}" style="position:relative"
    onclick="openMovieModal(${tmdb},${mSafe.replace(/"/g,'&quot;')})">
    ${resBadge}
    <input type="checkbox" class="pc-check"
      data-movie="${mSafe.replace(/"/g,'&quot;')}"
      onclick="event.stopPropagation();toggleSelect(${tmdb},${mSafe.replace(/"/g,'&quot;')},this,event)"
      title="Select"/>
    ${imgHtml}
    <div class="pc-info">
      <div class="pc-title" title="${escHtml(m.title||"")}">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-meta">
        <span class="pc-rating">⭐ ${rating}</span>
        ${m.year ? `<span>${m.year}</span>` : ""}
        ${qualityBadge}
      </div>
    </div>
    <div class="pc-overlay">
      <div class="pc-overlay-title">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-overlay-actions">${wBtn}${radarr4kBtn}</div>
    </div>
  </div>`
}

/* ── Empty state ────────────────────────────────────────────── */

function emptyStateHTML(msg){
  return `<div class="empty-state">
    <div class="empty-icon">🎬</div>
    <div class="empty-title">${msg}</div>
    <div class="empty-sub">Nothing to show here.</div>
  </div>`
}
