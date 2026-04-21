/* ============================================================
   mutations.js — all DATA-mutating and API-calling actions
   Depends on: api.js (api, toast, updateBadges, DATA, CONFIG, ACTIVE_TAB)
               cards.js (no direct dependency but cards call these)
============================================================ */

/* ── Batch selection state ──────────────────────────────────── */

const _selected = new Map() // tmdb_id → movie object
let _lastSelectedTmdb = null  // for Shift+click range selection

function toggleSelect(tmdb, m, checkbox, event) {
  const shiftHeld = event?.shiftKey

  if (shiftHeld && _lastSelectedTmdb && _lastSelectedTmdb !== tmdb) {
    // Range-select: find all .pc cards visible in DOM order
    const allCards = Array.from(document.querySelectorAll(".pc[data-tmdb]"))
    const ids = allCards.map(c => parseInt(c.dataset.tmdb))
    const fromIdx = ids.indexOf(_lastSelectedTmdb)
    const toIdx   = ids.indexOf(tmdb)
    if (fromIdx !== -1 && toIdx !== -1) {
      const lo = Math.min(fromIdx, toIdx)
      const hi = Math.max(fromIdx, toIdx)
      const selecting = !_selected.has(tmdb) // match target card's final state
      for (let i = lo; i <= hi; i++) {
        const card  = allCards[i]
        const cTmdb = ids[i]
        const cChk  = card.querySelector(".pc-check")
        if (selecting) {
          // pull movie data from the card's checkbox data-movie attribute
          let cMovie = { tmdb: cTmdb }
          try { cMovie = JSON.parse(cChk?.dataset?.movie || "{}") } catch {}
          _selected.set(cTmdb, cMovie)
          card.classList.add("selected")
          if (cChk) cChk.checked = true
        } else {
          _selected.delete(cTmdb)
          card.classList.remove("selected")
          if (cChk) cChk.checked = false
        }
      }
      _lastSelectedTmdb = tmdb
      updateBatchBar()
      return
    }
  }

  if (_selected.has(tmdb)) {
    _selected.delete(tmdb)
    checkbox.closest(".pc")?.classList.remove("selected")
  } else {
    _selected.set(tmdb, m)
    checkbox.closest(".pc")?.classList.add("selected")
  }
  _lastSelectedTmdb = tmdb
  updateBatchBar()
}

function clearSelection() {
  _selected.clear()
  _lastSelectedTmdb = null
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

/* Add every movie in the provided array to Radarr (uses picker once if needed) */
async function addAllToRadarr(movies) {
  if (!CONFIG?.RADARR?.RADARR_ENABLED) { toast("Radarr not enabled", "error"); return }
  if (!movies?.length) { toast("No movies to add", "gold"); return }

  // Get picker data once — show modal only if there's a real choice
  let qualityProfileId = null
  let rootFolderPath   = null
  try {
    const d = await _getRadarrPickerData("primary")
    if (d.profiles.length > 1 || d.folders.length > 1) {
      // Show picker once for the whole batch; wait for user choice via callback
      const choice = await new Promise(resolve => {
        _showRadarrPicker(null, `${movies.length} movies`, null, "primary", resolve)
      })
      if (!choice) return   // user cancelled
      qualityProfileId = choice.qualityProfileId
      rootFolderPath   = choice.rootFolderPath
    }
  } catch (e) { /* Radarr unreachable — fall through with no overrides */ }

  toast(`Adding ${movies.length} movies to Radarr…`, "gold")
  let ok = 0, fail = 0
  for (const m of movies) {
    const payload = { tmdb: m.tmdb, title: m.title }
    if (qualityProfileId) payload.qualityProfileId = qualityProfileId
    if (rootFolderPath)   payload.rootFolderPath   = rootFolderPath
    const res = await api("/api/radarr/add", "POST", payload)
    res.ok ? ok++ : fail++
  }
  toast(`Radarr: ${ok} added${fail ? `, ${fail} failed` : ""}`, ok ? "success" : "error")
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

// Cache Radarr picker data (profiles + root folders) per instance to avoid re-fetching
const _radarrPickerCache = {}

async function _getRadarrPickerData(instance) {
  if (_radarrPickerCache[instance]) return _radarrPickerCache[instance]
  const inst = instance === "4k" ? "4k" : "primary"
  const [pRes, rRes] = await Promise.all([
    api(`/api/radarr/profiles?instance=${inst}`),
    api(`/api/radarr/rootfolders?instance=${inst}`),
  ])
  const data = {
    profiles: pRes.ok  ? pRes.profiles : [],
    folders:  rRes.ok  ? rRes.folders  : [],
  }
  _radarrPickerCache[instance] = data
  return data
}

/* callback (optional): if provided, called with {qualityProfileId, rootFolderPath} on confirm
   or null on cancel — used by addAllToRadarr for batch mode. */
function _showRadarrPicker(tmdb, title, btn, instance, callback = null) {
  // Build modal overlay
  const overlay = document.createElement("div")
  overlay.id = "radarrPickerOverlay"
  overlay.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;
    display:flex;align-items:center;justify-content:center;padding:1rem`

  const data    = _radarrPickerCache[instance] || { profiles: [], folders: [] }
  const label   = instance === "4k" ? "Radarr 4K" : "Radarr"
  const cfgQ    = instance === "4k"
    ? CONFIG?.RADARR_4K?.RADARR_4K_QUALITY_PROFILE_ID
    : CONFIG?.RADARR?.RADARR_QUALITY_PROFILE_ID
  const cfgRoot = instance === "4k"
    ? CONFIG?.RADARR_4K?.RADARR_4K_ROOT_FOLDER_PATH
    : CONFIG?.RADARR?.RADARR_ROOT_FOLDER_PATH

  const profileOpts = data.profiles.map(p =>
    `<option value="${p.id}" ${p.id === cfgQ ? "selected" : ""}>${p.name}</option>`
  ).join("")

  const folderOpts = data.folders.map(f => {
    const free = f.freeSpace ? ` (${Math.round(f.freeSpace/1073741824)}GB free)` : ""
    return `<option value="${escHtml(f.path)}" ${f.path === cfgRoot ? "selected" : ""}>${escHtml(f.path)}${free}</option>`
  }).join("")

  overlay.innerHTML = `
    <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:12px;
                padding:1.5rem;min-width:320px;max-width:480px;width:100%">
      <div style="font-size:.85rem;font-weight:600;color:var(--text);margin-bottom:1rem">
        Add to ${label}
        <span style="font-size:.72rem;font-weight:400;color:var(--text3);display:block;margin-top:.2rem">
          ${escHtml(title)}
        </span>
      </div>
      ${data.profiles.length > 1 ? `
      <div style="margin-bottom:.75rem">
        <label style="font-size:.72rem;color:var(--text3);display:block;margin-bottom:.3rem">Quality Profile</label>
        <select id="rpQuality" style="width:100%;background:var(--bg3);border:1px solid var(--border2);
          border-radius:8px;color:var(--text);font-size:.8rem;padding:.4rem .6rem">
          ${profileOpts}
        </select>
      </div>` : `<input type="hidden" id="rpQuality" value="${cfgQ||""}">`}
      ${data.folders.length > 1 ? `
      <div style="margin-bottom:1rem">
        <label style="font-size:.72rem;color:var(--text3);display:block;margin-bottom:.3rem">Root Folder</label>
        <select id="rpFolder" style="width:100%;background:var(--bg3);border:1px solid var(--border2);
          border-radius:8px;color:var(--text);font-size:.8rem;padding:.4rem .6rem">
          ${folderOpts}
        </select>
      </div>` : `<input type="hidden" id="rpFolder" value="${escHtml(cfgRoot||"")}">`}
      <div style="display:flex;gap:.5rem;justify-content:flex-end">
        <button id="rpCancel"
          style="padding:6px 16px;border-radius:7px;border:1px solid var(--border2);
                 background:none;color:var(--text2);cursor:pointer;font-size:.78rem">Cancel</button>
        <button id="rpConfirm"
          style="padding:6px 16px;border-radius:7px;border:1px solid #7B2FBE;
                 background:#7B2FBE;color:#fff;cursor:pointer;font-size:.78rem;font-weight:600">
          Add to ${label}
        </button>
      </div>
    </div>`

  document.body.appendChild(overlay)
  const _dismiss = (result) => { overlay.remove(); if (callback) callback(result) }
  overlay.addEventListener("click", e => { if (e.target === overlay) _dismiss(null) })
  document.getElementById("rpCancel").addEventListener("click", () => _dismiss(null))

  document.getElementById("rpConfirm").addEventListener("click", async () => {
    const qualityProfileId = parseInt(document.getElementById("rpQuality")?.value) || null
    const rootFolderPath   = document.getElementById("rpFolder")?.value || null
    overlay.remove()
    if (callback) {
      callback({ qualityProfileId, rootFolderPath })
    } else {
      await _doAddToRadarr(tmdb, title, btn, instance, qualityProfileId, rootFolderPath)
    }
  })
}

async function _doAddToRadarr(tmdb, title, btn, instance, qualityProfileId, rootFolderPath) {
  const inst    = instance === "4k" ? "?instance=4k" : ""
  const payload = { tmdb, title }
  if (qualityProfileId) payload.qualityProfileId = qualityProfileId
  if (rootFolderPath)   payload.rootFolderPath   = rootFolderPath

  const res = await api(`/api/radarr/add${inst}`, "POST", payload)
  const label = instance === "4k" ? "4K" : "Radarr"
  if (res.ok) {
    btn.textContent = instance === "4k" ? "✓ In 4K" : "✓ In Radarr"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    toast(`${title} sent to ${label}`, "success")
  } else {
    btn.textContent = "✗ Error"; btn.disabled = false
    toast(`${label}: ${res.error || "unknown error"}`, "error")
  }
}

async function addToRadarr(tmdb, title, btn) {
  btn.disabled = true; btn.textContent = "…"
  const data = await _getRadarrPickerData("primary")
  // Show picker only when there's a real choice to make
  if (data.profiles.length > 1 || data.folders.length > 1) {
    btn.disabled = false; btn.textContent = "+ Radarr"
    _showRadarrPicker(tmdb, title, btn, "primary")
  } else {
    await _doAddToRadarr(tmdb, title, btn, "primary", null, null)
  }
}

async function addToRadarr4k(tmdb, title, btn) {
  btn.disabled = true; btn.textContent = "…"
  const data = await _getRadarrPickerData("4k")
  if (data.profiles.length > 1 || data.folders.length > 1) {
    btn.disabled = false; btn.textContent = "+ 4K"
    _showRadarrPicker(tmdb, title, btn, "4k")
  } else {
    await _doAddToRadarr(tmdb, title, btn, "4k", null, null)
  }
}

/* ── Quality upgrade → Radarr 4K ───────────────────────────── */

async function upgradeToRadarr4k(tmdb, title, btn) {
  const orig = btn.textContent
  btn.disabled = true; btn.textContent = "…"
  const data = await _getRadarrPickerData("4k")
  if (!data || (!data.profiles && !data.folders)) {
    toast("Radarr 4K not reachable", "error")
    btn.disabled = false; btn.textContent = orig
    return
  }
  if (data.profiles.length > 1 || data.folders.length > 1) {
    btn.disabled = false; btn.textContent = orig
    _showRadarrPicker(tmdb, title, btn, "4k", async (result) => {
      if (!result) return
      const res = await api("/api/radarr/add?instance=4k", "POST", {
        tmdb, title,
        qualityProfileId: result.qualityProfileId,
        rootFolderPath:   result.rootFolderPath,
      })
      if (res.ok) {
        toast(`${title} → Radarr 4K`, "success")
        btn.textContent = "✓ Queued"
        btn.disabled = true
        // Bust upgrade cache so refresh shows updated state
        api("/api/quality/refresh", "POST")
      } else {
        toast(res.error || "Radarr 4K error", "error")
        btn.disabled = false; btn.textContent = orig
      }
    })
  } else {
    const res = await api("/api/radarr/add?instance=4k", "POST", { tmdb, title })
    if (res.ok) {
      toast(`${title} → Radarr 4K`, "success")
      btn.textContent = "✓ Queued"
      btn.disabled = true
      api("/api/quality/refresh", "POST")
    } else {
      toast(res.error || "Radarr 4K error", "error")
      btn.disabled = false; btn.textContent = orig
    }
  }
}

/* ── Seerr requested state (localStorage) ──────────────────── */

function _makeSeerrStore(key) {
  let _s = null
  return {
    load() {
      if (!_s) {
        try { _s = new Set(JSON.parse(localStorage.getItem(key) || "[]")) }
        catch { _s = new Set() }
      }
      return _s
    },
    add(tmdb)  { this.load().add(tmdb);  this._save() },
    has(tmdb)  { return this.load().has(tmdb) },
    _save()    { try { localStorage.setItem(key, JSON.stringify([...this.load()])) } catch {} },
  }
}
const overseerrRequested   = _makeSeerrStore("cp-overseerr-requested")
const jellyseerrRequested  = _makeSeerrStore("cp-jellyseerr-requested")

async function addToOverseerr(tmdb, title, btn){
  btn.disabled = true; btn.textContent = "…"
  const res = await api("/api/overseerr/add","POST",{tmdb,title})
  if (res.ok){
    overseerrRequested.add(tmdb)
    btn.textContent = "✓ Requested"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    btn.disabled    = true
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
    jellyseerrRequested.add(tmdb)
    btn.textContent = "✓ Requested"
    btn.className   = "btn-sm"
    btn.style.color = "var(--green)"
    btn.disabled    = true
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
      // Explicitly trigger a refresh — adding a URL never auto-starts one
      await triggerLbRefresh()
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
    toast("List removed", "gold")
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
