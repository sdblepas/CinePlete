/* ============================================================
   mutations.js — all DATA-mutating and API-calling actions
   Depends on: api.js (api, toast, updateBadges, DATA, CONFIG, ACTIVE_TAB)
               cards.js (no direct dependency but cards call these)
============================================================ */

/* ── Batch selection state ──────────────────────────────────── */

const _selected = new Map() // tmdb_id → movie object

function toggleSelect(tmdb, m, checkbox) {
  if (_selected.has(tmdb)) {
    _selected.delete(tmdb)
    checkbox.closest(".pc")?.classList.remove("selected")
  } else {
    _selected.set(tmdb, m)
    checkbox.closest(".pc")?.classList.add("selected")
  }
  updateBatchBar()
}

function clearSelection() {
  _selected.clear()
  document.querySelectorAll(".pc-check").forEach(c => {
    c.checked = false
    c.closest(".pc")?.classList.remove("selected")
  })
  updateBatchBar()
}

function updateBatchBar() {
  const bar  = document.getElementById("batchBar")
  const cnt  = document.getElementById("batchCount")
  if (!bar) return
  const n = _selected.size
  if (n > 0) {
    cnt.textContent = `${n} selected`
    bar.classList.add("visible")
    const ovsBtn = document.getElementById("batchOverseerr")
    const jssBtn = document.getElementById("batchJellyseerr")
    const wlBtn  = document.getElementById("batchWishlist")
    if (ovsBtn) ovsBtn.style.display = CONFIG?.OVERSEERR?.OVERSEERR_ENABLED   ? "" : "none"
    if (jssBtn) jssBtn.style.display = CONFIG?.JELLYSEERR?.JELLYSEERR_ENABLED ? "" : "none"
    // On Wishlist tab: swap "Add to Wishlist" → "Remove from Wishlist"
    if (wlBtn) {
      if (ACTIVE_TAB === "wishlist") {
        wlBtn.textContent = "✕ Remove from Wishlist"
        wlBtn.classList.remove("btn-wishlist")
        wlBtn.classList.add("btn-ignore")
      } else {
        wlBtn.textContent = "☆ Wishlist"
        wlBtn.classList.add("btn-wishlist")
        wlBtn.classList.remove("btn-ignore")
      }
    }
  } else {
    bar.classList.remove("visible")
  }
}

/* ── Batch operations ───────────────────────────────────────── */

function batchWishlistAction() {
  if (ACTIVE_TAB === "wishlist") batchRemoveFromWishlist()
  else batchAddToWishlist()
}

async function batchRemoveFromWishlist() {
  const n = _selected.size
  for (const [tmdb] of _selected) {
    await api("/api/wishlist/remove", "POST", { tmdb })
    document.querySelector(`.pc[data-tmdb="${tmdb}"]`)?.remove()
  }
  // Keep DATA consistent so switching tabs doesn't restore the removed movies
  const removedSet = new Set(_selected.keys())
  DATA.wishlist = (DATA.wishlist || []).filter(w => !removedSet.has(w.tmdb))
  toast(`${n} movie${n !== 1 ? "s" : ""} removed from Wishlist`, "gold")
  clearSelection()
}

async function batchIgnoreMovies() {
  const n = _selected.size
  for (const [tmdb, m] of _selected) {
    await api("/api/ignore", "POST", {
      kind: "movie", value: tmdb,
      title: m.title, year: m.year, poster: m.poster,
    })
    _purgeFromData(tmdb)
    document.querySelector(`.pc[data-tmdb="${tmdb}"]`)?.remove()
  }
  toast(`${n} movie${n !== 1 ? "s" : ""} ignored`, "gold")
  clearSelection()
}

async function batchAddToRadarr() {
  if (!CONFIG?.RADARR?.RADARR_ENABLED) { toast("Radarr not enabled", "error"); return }
  let ok = 0, fail = 0
  for (const [tmdb, m] of _selected) {
    const res = await api("/api/radarr/add", "POST", { tmdb, title: m.title })
    res.ok ? ok++ : fail++
  }
  toast(`Radarr: ${ok} added${fail ? `, ${fail} failed` : ""}`, ok ? "success" : "error")
  clearSelection()
}

async function batchAddToWishlist() {
  const n = _selected.size
  for (const [tmdb, m] of _selected) {
    await api("/api/wishlist/add", "POST", { tmdb })
    if (!DATA.wishlist) DATA.wishlist = []
    if (!DATA.wishlist.find(w => w.tmdb === tmdb))
      DATA.wishlist.push({ ...m, wishlist: true })
  }
  toast(`${n} movie${n !== 1 ? "s" : ""} added to Wishlist`, "gold")
  clearSelection()
}

async function batchAddToOverseerr() {
  if (!CONFIG?.OVERSEERR?.OVERSEERR_ENABLED) { toast("Overseerr not enabled", "error"); return }
  let ok = 0, fail = 0
  for (const [tmdb] of _selected) {
    const res = await api("/api/overseerr/add", "POST", { tmdb })
    res.ok ? ok++ : fail++
  }
  toast(`Overseerr: ${ok} requested${fail ? `, ${fail} failed` : ""}`, ok ? "success" : "error")
  clearSelection()
}

async function batchAddToJellyseerr() {
  if (!CONFIG?.JELLYSEERR?.JELLYSEERR_ENABLED) { toast("Jellyseerr not enabled", "error"); return }
  let ok = 0, fail = 0
  for (const [tmdb] of _selected) {
    const res = await api("/api/jellyseerr/add", "POST", { tmdb })
    res.ok ? ok++ : fail++
  }
  toast(`Jellyseerr: ${ok} requested${fail ? `, ${fail} failed` : ""}`, ok ? "success" : "error")
  clearSelection()
}

/* ── In-memory DATA helpers ─────────────────────────────────── */

/**
 * Remove a movie from every DATA array so tab re-renders reflect the change
 * immediately without requiring a rescan.
 */
function _purgeFromData(tmdb) {
  // Flat arrays
  ;["classics","suggestions","wishlist"].forEach(key => {
    if (Array.isArray(DATA[key]))
      DATA[key] = DATA[key].filter(m => m.tmdb !== tmdb)
  })
  // Grouped arrays — remove from each group's .missing list
  ;["franchises","directors","actors"].forEach(key => {
    ;(DATA[key] || []).forEach(group => {
      if (Array.isArray(group.missing))
        group.missing = group.missing.filter(m => m.tmdb !== tmdb)
    })
  })
}

/* ── Wishlist actions ───────────────────────────────────────── */

async function addWishlist(tmdb, btn){
  await api("/api/wishlist/add","POST",{tmdb})
  btn.className   = "btn-sm btn-wishlisted"
  btn.textContent = "★"
  btn.onclick     = () => removeWishlist(tmdb, btn)
  toast("Added to Wishlist","gold")
  // Reflect in DATA immediately so Wishlist tab shows the movie without rescan
  try {
    const m = JSON.parse(btn.dataset.movie || "{}")
    if (m.tmdb) {
      if (!DATA.wishlist) DATA.wishlist = []
      if (!DATA.wishlist.find(w => w.tmdb === tmdb))
        DATA.wishlist.push({ ...m, wishlist: true })
    }
  } catch (_) {}
  updateBadges()
}

async function removeWishlist(tmdb, btn){
  await api("/api/wishlist/remove","POST",{tmdb})
  btn.className   = "btn-sm btn-wishlist"
  btn.textContent = "☆"
  btn.onclick     = () => addWishlist(tmdb, btn)
  toast("Removed from Wishlist")
  // Remove from DATA immediately
  DATA.wishlist = (DATA.wishlist || []).filter(w => w.tmdb !== tmdb)
  updateBadges()
}

/* ── Ignore / Unignore ──────────────────────────────────────── */

async function ignoreMovie(tmdb, title, year, poster, btn) {
  btn.disabled = true
  const res = await api("/api/ignore", "POST", { kind: "movie", value: tmdb, title, year, poster })
  if (res.ok) {
    toast(`"${title}" hidden — won't appear again`, "success")
    _purgeFromData(tmdb)   // keep DATA consistent so tab re-renders don't show it again
    const card = btn.closest(".pc")
    if (card) {
      card.style.transition = "opacity .3s, transform .3s"
      card.style.opacity = "0"
      card.style.transform = "scale(.95)"
      setTimeout(() => card.remove(), 320)
    }
  } else {
    btn.disabled = false
    toast(`Could not ignore: ${res.error || "unknown error"}`, "error")
  }
}

async function unignoreMovie(tmdb, title, btn) {
  btn.disabled = true
  const res = await api("/api/unignore", "POST", { kind: "movie", value: tmdb })
  if (res.ok) {
    toast(`"${title}" restored`, "success")
    const card = document.getElementById(`ignored-${tmdb}`)
    if (card) {
      card.style.transition = "opacity .3s"
      card.style.opacity    = "0"
      setTimeout(() => { card.remove() }, 320)
    }
  } else {
    btn.disabled = false
    toast(`Could not restore: ${res.error || "unknown error"}`, "error")
  }
}

/* ── Integration actions ────────────────────────────────────── */

async function addToRadarr(tmdb, title, btn){
  btn.disabled = true; btn.textContent = "…"
  const res = await api("/api/radarr/add","POST",{tmdb,title})
  if (res.ok){
    btn.textContent = "✓ In Radarr"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    toast(`${title} sent to Radarr`,"success")
  } else {
    btn.textContent = "✗ Error"; btn.disabled = false
    toast(`Radarr: ${res.error||"unknown error"}`,"error")
  }
}

async function addToRadarr4k(tmdb, title, btn){
  btn.disabled = true; btn.textContent = "…"
  const res = await api("/api/radarr/add?instance=4k","POST",{tmdb,title})
  if (res.ok){
    btn.textContent = "✓ In 4K"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    toast(`${title} sent to Radarr 4K`,"success")
  } else {
    btn.textContent = "✗ 4K"; btn.disabled = false
    toast(`Radarr 4K: ${res.error||"unknown error"}`,"error")
  }
}

async function addToOverseerr(tmdb, title, btn){
  btn.disabled = true; btn.textContent = "…"
  const res = await api("/api/overseerr/add","POST",{tmdb,title})
  if (res.ok){
    btn.textContent = "✓ Requested"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    toast(`${title} → Overseerr`,"success")
  } else {
    btn.textContent = "✗"; btn.disabled = false
    toast(`Overseerr: ${res.error||"unknown error"}`,"error")
  }
}

async function addToJellyseerr(tmdb, title, btn){
  btn.disabled = true; btn.textContent = "…"
  const res = await api("/api/jellyseerr/add","POST",{tmdb,title})
  if (res.ok){
    btn.textContent = "✓ Requested"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    toast(`${title} → Jellyseerr`,"success")
  } else {
    btn.textContent = "✗"; btn.disabled = false
    toast(`Jellyseerr: ${res.error||"unknown error"}`,"error")
  }
}

/* ── Ignore-group actions ───────────────────────────────────── */

async function ignoreFranchise(name, btn){
  await api("/api/ignore","POST",{kind:"franchise",value:name})
  if (!DATA._ignored_franchises) DATA._ignored_franchises=[]
  if (!DATA._ignored_franchises.includes(name)) DATA._ignored_franchises.push(name)
  DATA.franchises = (DATA.franchises||[]).filter(f => f.name !== name)
  btn.closest(".mb-group").remove()
  updateFilterBar()
  toast(`"${name}" ignored`,"info")
}

async function ignoreDirector(name, btn){
  await api("/api/ignore","POST",{kind:"director",value:name})
  DATA.directors = (DATA.directors||[]).filter(d=>d.name!==name)
  btn.closest(".mb-group").remove()
  updateFilterBar()
  toast(`Director "${name}" ignored`)
}

async function ignoreActor(name, btn){
  await api("/api/ignore","POST",{kind:"actor",value:name})
  DATA.actors = (DATA.actors||[]).filter(a=>a.name!==name)
  btn.closest(".mb-group").remove()
  updateFilterBar()
  toast(`Actor "${name}" ignored`)
}

/* ── Letterboxd URL management ──────────────────────────────── */

async function addLbUrl(input) {
  const url = (input?.value || "").trim()
  if (!url) { toast("Paste a Letterboxd URL first", "error"); return }

  const btn = input?.nextElementSibling
  if (btn) { btn.disabled = true; btn.textContent = "…" }

  try {
    const res = await api("/api/letterboxd/urls", "POST", { url })
    if (res.ok) {
      input.value = ""
      if (btn) { btn.disabled = false; btn.textContent = "+ Add" }
      toast("List added — fetching in background…", "gold")
      // Re-render immediately (shows new URL in list, cached movies stay)
      await renderLetterboxd()
      // Server already started a refresh; poll for when it finishes
      _startLbPoll()
    } else {
      toast(res.error || "Failed to add URL", "error")
      if (btn) { btn.disabled = false; btn.textContent = "+ Add" }
    }
  } catch(e) {
    toast("Failed to add URL", "error")
    if (btn) { btn.disabled = false; btn.textContent = "+ Add" }
  }
}

async function removeLbUrl(url, btn) {
  btn.disabled = true
  try {
    await api("/api/letterboxd/urls/remove", "POST", { url })
    btn.disabled = false
    toast("List removed — refreshing in background…", "gold")
    // Re-render immediately (URL gone from list, movies still cached)
    await renderLetterboxd()
    _startLbPoll()
  } catch(e) {
    toast(`Failed to remove: ${e?.message || "unknown error"}`, "error")
    btn.disabled = false
  }
}

async function triggerLbRefresh() {
  try {
    await api("/api/letterboxd/refresh", "POST", {})
    toast("Refreshing Letterboxd lists…", "gold")
    _startLbPoll()
    await renderLetterboxd()   // re-render to show "↻ Refreshing…" badge
  } catch(e) {
    toast("Refresh failed", "error")
  }
}
