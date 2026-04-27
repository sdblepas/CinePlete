/* ============================================================
   modal.js — movie detail modal
============================================================ */

let _modalOpen  = false
let _modalMovie = null   // current modal's movie data — used by wishlist handlers to update DATA

async function openMovieModal(tmdb, fallback = {}) {
  const modal   = document.getElementById("movieModal")
  const info    = document.getElementById("movieModalInfo")
  const bdEl    = document.getElementById("movieModalBackdrop")
  const posterEl= document.getElementById("movieModalPoster")
  const posterPH= document.getElementById("movieModalPosterPH")

  // Show modal immediately with skeleton while fetching
  modal.classList.add("open")
  _modalOpen = true
  document.body.style.overflow = "hidden"

  info.innerHTML = `
    <div class="skeleton" style="height:28px;width:70%;border-radius:6px"></div>
    <div class="skeleton" style="height:14px;width:40%;border-radius:6px;margin-top:.5rem"></div>
    <div style="display:flex;gap:.4rem;margin-top:.5rem">
      ${[1,2,3].map(()=>'<div class="skeleton" style="height:20px;width:60px;border-radius:20px"></div>').join("")}
    </div>
    <div class="skeleton" style="height:80px;border-radius:6px;margin-top:.5rem"></div>`

  // Show fallback poster while loading
  if (fallback.poster) {
    posterPH.style.display = "none"
    const img = document.createElement("img")
    img.id = "movieModalPoster"
    img.src = fallback.poster
    img.alt = ""
    img.style.cssText = "width:150px;flex-shrink:0;object-fit:cover;border-right:1px solid var(--border)"
    const existing = document.getElementById("movieModalPoster")
    if (existing) existing.replaceWith(img)
    else posterPH.insertAdjacentElement("afterend", img)
  }

  let md
  try {
    md = await api(`/api/movie/${tmdb}`)
  } catch(e) {
    md = {}
  }

  if (!_modalOpen) return // user closed modal before fetch completed

  // Backdrop
  if (md.backdrop) {
    bdEl.src = md.backdrop
    bdEl.style.display = "block"
  } else {
    bdEl.style.display = "none"
  }

  // Poster
  const pEl = document.getElementById("movieModalPoster")
  if (md.poster) {
    if (pEl) {
      pEl.src = md.poster
    } else {
      posterPH.style.display = "none"
      const img = document.createElement("img")
      img.id = "movieModalPoster"
      img.src = md.poster
      img.alt = ""
      img.style.cssText = "width:150px;flex-shrink:0;object-fit:cover;border-right:1px solid var(--border)"
      posterPH.insertAdjacentElement("afterend", img)
    }
  } else {
    if (pEl) { pEl.remove() }
    posterPH.style.display = "flex"
  }

  const runtime = md.runtime ? `${md.runtime}m` : ""
  const year    = md.year    ? `(${md.year})`    : ""

  const genresHtml = (md.genres || []).map(g =>
    `<span class="modal-genre-chip">${g}</span>`
  ).join("") || ""

  const statsHtml = `
    <div class="modal-stats">
      ${md.rating ? `<span>⭐ <strong>${parseFloat(md.rating).toFixed(1)}</strong></span>` : ""}
      ${md.votes  ? `<span><strong>${(md.votes/1000).toFixed(0)}k</strong> votes</span>` : ""}
      ${runtime   ? `<span>🕐 <strong>${runtime}</strong></span>`  : ""}
      ${md.year   ? `<span>📅 <strong>${md.year}</strong></span>` : ""}
    </div>`

  const castHtml = (md.cast || []).length ? `
    <div>
      <div style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin-bottom:.5rem">Cast</div>
      <div class="modal-cast">
        ${(md.cast || []).map(c => `
          <div class="cast-card">
            ${c.profile
              ? `<img src="${c.profile}" alt="" loading="lazy"/>`
              : `<div class="cast-no-photo">?</div>`}
            <div class="cast-name" title="${escHtml(c.name)}">${escHtml(c.name)}</div>
            <div class="cast-char" title="${escHtml(c.character||"")}">${escHtml(c.character||"")}</div>
          </div>`).join("")}
      </div>
    </div>` : ""

  const safeTitle = escHtml((md.title||"").replace(/'/g,"\\'"))
  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="addToRadarr(${tmdb},'${safeTitle}',this)">+ Radarr</button>`
    : ""
  const radarr4kBtn = CONFIG?.RADARR_4K?.RADARR_4K_ENABLED
    ? `<button class="btn-sm btn-radarr" style="opacity:.75" onclick="addToRadarr4k(${tmdb},'${safeTitle}',this)">+ 4K</button>`
    : ""
  const overseerrBtn = CONFIG?.OVERSEERR?.OVERSEERR_ENABLED
    ? `<button class="btn-sm btn-overseerr" onclick="addToOverseerr(${tmdb},'${safeTitle}',this)">→ Overseerr</button>`
    : ""
  const jellyseerrBtn = CONFIG?.JELLYSEERR?.JELLYSEERR_ENABLED
    ? `<button class="btn-sm btn-jellyseerr" onclick="addToJellyseerr(${tmdb},'${safeTitle}',this)">→ Jellyseerr</button>`
    : ""
  const seerrBtn = CONFIG?.SEERR?.SEERR_ENABLED
    ? `<button class="btn-sm btn-seerr" onclick="addToSeerr(${tmdb},'${safeTitle}',this)">→ Seerr</button>`
    : ""
  const trailerBtn = md.trailer_key
    ? `<button class="btn-sm btn-trailer" onclick="toggleModalTrailer('${md.trailer_key}')">▶ Trailer</button>`
    : ""

  // Stash movie data so wishlist handlers can update DATA without an extra API call
  _modalMovie = {
    tmdb,
    title:  md.title  || fallback.title  || "",
    year:   md.year   || fallback.year   || null,
    poster: md.poster || fallback.poster || "",
    rating: md.rating || fallback.rating || 0,
  }

  const wInWishlist = fallback.wishlist
  const wBtn = wInWishlist
    ? `<button class="btn-sm btn-wishlisted" id="modal-wbtn" onclick="modalRemoveWishlist(${tmdb})">★ Wishlisted</button>`
    : `<button class="btn-sm btn-wishlist"   id="modal-wbtn" onclick="modalAddWishlist(${tmdb})">☆ Wishlist</button>`

  info.innerHTML = `
    <div>
      <div id="movieModalTitle">${escHtml(md.title || fallback.title || "Unknown")}</div>
      ${md.tagline ? `<div id="movieModalTagline">${escHtml(md.tagline)}</div>` : ""}
    </div>
    ${genresHtml ? `<div class="modal-genres">${genresHtml}</div>` : ""}
    ${statsHtml}
    ${md.overview ? `<div id="movieModalOverview">${escHtml(md.overview)}</div>` : ""}
    ${castHtml}
    <div class="modal-actions">
      ${wBtn}
      ${radarrBtn}
      ${radarr4kBtn}
      ${overseerrBtn}
      ${jellyseerrBtn}
      ${seerrBtn}
      ${trailerBtn}
      <a href="${md.tmdb_url || `https://www.themoviedb.org/movie/${tmdb}`}"
         target="_blank" rel="noopener"
         class="btn-sm" style="text-decoration:none">↗ TMDB</a>
    </div>
    <div id="trailerWrap" style="display:none;margin-top:.75rem;border-radius:8px;overflow:hidden;
      position:relative;padding-bottom:56.25%;height:0">
      <iframe id="trailerFrame" src="" frameborder="0" allowfullscreen
        allow="autoplay; encrypted-media"
        style="position:absolute;top:0;left:0;width:100%;height:100%;border-radius:8px"></iframe>
    </div>
    <div id="streamingSection"></div>`

  // Lazy-load streaming providers without blocking the modal render
  _loadStreamingProviders(tmdb)
}

async function _loadStreamingProviders(tmdb) {
  const el = document.getElementById("streamingSection")
  if (!el) return
  try {
    const res = await api(`/api/streaming/${tmdb}`)
    if (!_modalOpen || document.getElementById("streamingSection") !== el) return
    if (!res.ok || !res.providers?.length) return

    const TYPE_LABEL = { flatrate: "Stream", free: "Free", rent: "Rent", buy: "Buy" }
    const byType = {}
    for (const p of res.providers) {
      ;(byType[p.type] = byType[p.type] || []).push(p)
    }

    const jwLink = res.link || ""
    const sections = Object.entries(byType).map(([type, providers]) => {
      const logos = providers.slice(0, 6).map(p =>
        p.logo
          ? `<a href="${jwLink||"https://www.justwatch.com"}" target="_blank" rel="noopener"
               title="${escHtml(p.name)}" style="display:inline-block;line-height:0">
               <img src="${p.logo}" alt="${escHtml(p.name)}"
                 style="width:32px;height:32px;border-radius:6px;object-fit:cover;
                        transition:opacity .15s" loading="lazy"
                 onmouseover="this.style.opacity='.75'" onmouseout="this.style.opacity='1'"/>
             </a>`
          : `<span style="font-size:.72rem;color:var(--text2)">${escHtml(p.name)}</span>`
      ).join("")
      return `<span style="font-size:.72rem;color:var(--text3);margin-right:.4rem">${escHtml(TYPE_LABEL[type]||type)}:</span>${logos}`
    }).join('<span style="margin:0 .5rem;color:var(--border2)">·</span>')

    const link = res.link
      ? ` <a href="${res.link}" target="_blank" rel="noopener"
            style="font-size:.7rem;color:var(--text3);text-decoration:none;margin-left:.5rem">JustWatch ↗</a>`
      : ""

    el.innerHTML = `
      <div style="margin-top:.75rem;padding:.6rem .75rem;background:var(--bg3);
                  border:1px solid var(--border2);border-radius:8px;
                  display:flex;align-items:center;flex-wrap:wrap;gap:.4rem">
        <span style="font-size:.72rem;font-weight:600;color:var(--text2);margin-right:.2rem">📺 Where to watch:</span>
        ${sections}${link}
      </div>`
  } catch {}
}

function toggleModalTrailer(key) {
  const wrap  = document.getElementById("trailerWrap")
  const frame = document.getElementById("trailerFrame")
  const btn   = document.querySelector(".btn-trailer")
  if (!wrap || !frame) return
  if (wrap.style.display === "none") {
    frame.src = `https://www.youtube-nocookie.com/embed/${key}?autoplay=1`
    wrap.style.display = "block"
    if (btn) btn.textContent = "✕ Trailer"
  } else {
    frame.src = ""
    wrap.style.display = "none"
    if (btn) btn.textContent = "▶ Trailer"
  }
}

function closeMovieModal() {
  const modal = document.getElementById("movieModal")
  modal.classList.remove("open")
  _modalOpen  = false
  _modalMovie = null
  document.body.style.overflow = ""
  // Stop any playing trailer immediately
  const frame = document.getElementById("trailerFrame")
  if (frame) frame.src = ""
  // Small delay to let animation play before clearing content
  setTimeout(() => {
    if (!_modalOpen) {
      document.getElementById("movieModalInfo").innerHTML = ""
      document.getElementById("movieModalBackdrop").style.display = "none"
      document.getElementById("movieModalBackdrop").src = ""
    }
  }, 250)
}

function handleModalBgClick(e) {
  if (e.target === document.getElementById("movieModal")) closeMovieModal()
}

async function modalAddWishlist(tmdb) {
  await api("/api/wishlist/add", "POST", { tmdb })
  const btn = document.getElementById("modal-wbtn")
  if (btn) {
    btn.className   = "btn-sm btn-wishlisted"
    btn.textContent = "★ Wishlisted"
    btn.onclick     = () => modalRemoveWishlist(tmdb)
  }
  toast("Added to Wishlist", "gold")
  // Reflect in DATA so Wishlist tab shows the movie without rescan
  if (_modalMovie?.tmdb) {
    if (!DATA.wishlist) DATA.wishlist = []
    if (!DATA.wishlist.find(w => w.tmdb === tmdb))
      DATA.wishlist.push({ ..._modalMovie, wishlist: true })
  }
  updateBadges()
}

async function modalRemoveWishlist(tmdb) {
  await api("/api/wishlist/remove", "POST", { tmdb })
  const btn = document.getElementById("modal-wbtn")
  if (btn) {
    btn.className   = "btn-sm btn-wishlist"
    btn.textContent = "☆ Wishlist"
    btn.onclick     = () => modalAddWishlist(tmdb)
  }
  toast("Removed from Wishlist")
  // Reflect in DATA immediately
  DATA.wishlist = (DATA.wishlist || []).filter(w => w.tmdb !== tmdb)
  updateBadges()
}
