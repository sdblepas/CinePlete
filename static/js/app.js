/* ============================================================
   app.js — globals, render router, navigation, boot
   Loads after: api.js, scan.js, filters.js, render.js, modal.js, config.js
============================================================ */

let DATA       = null
let CONFIG     = null
let CONFIGURED = false
let ACTIVE_TAB = "dashboard"

const PAGE_TITLES = {
  dashboard:   "Dashboard",
  franchises:  "Franchises",
  directors:   "Directors",
  actors:      "Actors",
  classics:    "Classics",
  suggestions: "Suggestions",
  notmdb:      "No TMDB GUID",
  nomatch:     "TMDB No Match",
  wishlist:    "Wishlist",
  config:      "Configuration",
  logs:        "Logs",
}

const TAB_KEYS = {
  "1": "dashboard", "2": "franchises", "3": "directors",
  "4": "actors",    "5": "classics",   "6": "suggestions",
  "7": "wishlist",  "8": "notmdb",     "9": "nomatch",
}

/* ============================================================
   RENDER ROUTER
============================================================ */

function render(){
  if (!DATA && !["config","logs"].includes(ACTIVE_TAB)){
    renderSkeleton()
    return
  }

  if (!CONFIGURED){
    document.getElementById("topFilters").style.display = "none"
    ACTIVE_TAB = "config"
    document.getElementById("page-title").textContent = PAGE_TITLES.config
    setNavActive("config")
    return renderConfig()
  }

  document.getElementById("page-title").textContent = PAGE_TITLES[ACTIVE_TAB]||ACTIVE_TAB
  updateFilterBar()
  updateExportBtn()
  saveState()

  if (ACTIVE_TAB==="dashboard")   return renderDashboard()
  if (ACTIVE_TAB==="franchises")  return renderFranchises()
  if (ACTIVE_TAB==="directors")   return renderDirectors()
  if (ACTIVE_TAB==="actors")      return renderActors()
  if (ACTIVE_TAB==="classics")    return renderClassics()
  if (ACTIVE_TAB==="suggestions") return renderSuggestions()
  if (ACTIVE_TAB==="notmdb")      return renderNoTmdb()
  if (ACTIVE_TAB==="nomatch")     return renderNoMatch()
  if (ACTIVE_TAB==="wishlist")    return renderWishlist()
  if (ACTIVE_TAB==="config")      return renderConfig()
  if (ACTIVE_TAB==="logs")        return renderLogs()
}

/* ============================================================
   NAVIGATION
============================================================ */

function setNavActive(tab){
  document.querySelectorAll(".nav").forEach(b=>b.classList.remove("active"))
  document.querySelector(`.nav[data-tab="${tab}"]`)?.classList.add("active")
}

function setActiveTab(tab){
  ACTIVE_TAB = tab
  setNavActive(tab)
  if (typeof _activeGroupFilter !== "undefined") _activeGroupFilter = ""
  if (typeof _activeGenreFilter !== "undefined") _activeGenreFilter = ""
  const sortEl = document.getElementById("sort")
  if (sortEl){
    if (tab === "suggestions" && sortEl.value === "popularity") sortEl.value = "matches"
    if (tab !== "suggestions" && sortEl.value === "matches")    sortEl.value = "popularity"
  }
  clearSelection()
  render()
}

document.addEventListener("click", e=>{
  const btn = e.target.closest(".nav")
  if (!btn) return
  setActiveTab(btn.dataset.tab)
})

document.addEventListener("input", e=>{
  if (["search","groupFilter","sort"].includes(e.target.id)) render()
})
document.addEventListener("change", e=>{
  if (["yearFilter","groupFilter","sort"].includes(e.target.id)) render()
  if (e.target.id === "genreFilter") onGenreFilterChange(e.target.value)
})

/* ============================================================
   KEYBOARD SHORTCUTS
============================================================ */

document.addEventListener("keydown", e=>{
  const tag = document.activeElement.tagName
  const inInput = ["INPUT","TEXTAREA","SELECT"].includes(tag)

  // Esc — close any open overlay
  if (e.key === "Escape") {
    if (_modalOpen)               { closeMovieModal();     return }
    if (isGlobalSearchOpen())     { closeGlobalSearch();   return }
    if (isShortcutsOpen())        { closeShortcuts();      return }
    return
  }

  // / or Cmd+K — open global search
  if (e.key === "/" && !inInput) { e.preventDefault(); openGlobalSearch(); return }
  if (e.key === "k" && (e.metaKey||e.ctrlKey)) { e.preventDefault(); openGlobalSearch(); return }

  if (inInput) return   // don't steal keypresses from inputs below this line

  // ? — keyboard shortcuts help
  if (e.key === "?") { openShortcuts(); return }

  // R — rescan
  if (e.key === "r" || e.key === "R") { rescan(); return }

  // 1–9 — switch tabs
  if (TAB_KEYS[e.key] && CONFIGURED) { setActiveTab(TAB_KEYS[e.key]); return }
})

/* ============================================================
   THEME TOGGLE
============================================================ */

function toggleTheme() {
  const html   = document.documentElement
  const isLight= html.getAttribute("data-theme") === "light"
  html.setAttribute("data-theme", isLight ? "dark" : "light")
  document.getElementById("themeSunIcon").style.display  = isLight ? "none"  : ""
  document.getElementById("themeMoonIcon").style.display = isLight ? ""      : "none"
  localStorage.setItem("cp-theme", isLight ? "dark" : "light")
}

function applyStoredTheme() {
  const t = localStorage.getItem("cp-theme") || "dark"
  document.documentElement.setAttribute("data-theme", t)
  document.getElementById("themeSunIcon").style.display  = t === "dark"  ? "none" : ""
  document.getElementById("themeMoonIcon").style.display = t === "light" ? "none" : ""
}

/* ============================================================
   STATE PERSISTENCE
============================================================ */

function saveState() {
  try {
    localStorage.setItem("cp-state", JSON.stringify({
      tab:    ACTIVE_TAB,
      sort:   document.getElementById("sort")?.value    || "popularity",
      year:   document.getElementById("yearFilter")?.value || "",
      search: document.getElementById("search")?.value || "",
    }))
  } catch(e) {}
}

function restoreState() {
  try {
    const s = JSON.parse(localStorage.getItem("cp-state") || "{}")
    if (s.tab && PAGE_TITLES[s.tab]) ACTIVE_TAB = s.tab
  } catch(e) {}
}

/* ============================================================
   GLOBAL SEARCH
============================================================ */

let _gsDebounce    = null
let _gsFocusIndex  = -1
let _gsResults     = []

function isGlobalSearchOpen() {
  return document.getElementById("globalSearch")?.classList.contains("open")
}

function openGlobalSearch() {
  const modal = document.getElementById("globalSearch")
  modal.classList.add("open")
  const inp = document.getElementById("gsInput")
  inp.value = ""
  _gsResults = []
  _gsFocusIndex = -1
  document.getElementById("gsResults").innerHTML = ""
  document.getElementById("gsEmpty") && (document.getElementById("gsEmpty").textContent = "")
  setTimeout(() => inp.focus(), 50)
}

function closeGlobalSearch() {
  document.getElementById("globalSearch")?.classList.remove("open")
}

function handleGsBgClick(e) {
  if (e.target === document.getElementById("globalSearch")) closeGlobalSearch()
}

async function _gsSearch(q) {
  if (!q || q.length < 2) {
    document.getElementById("gsResults").innerHTML =
      `<div id="gsEmpty">Type to search across all tabs…</div>`
    return
  }
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(q)}`)
    _gsResults = data.results || []
    _renderGsResults()
  } catch(e) {}
}

const TAB_LABELS = {
  franchises:"Franchise", directors:"Director", actors:"Actor",
  classics:"Classic", suggestions:"Suggestion", wishlist:"Wishlist"
}

function _renderGsResults() {
  const box = document.getElementById("gsResults")
  if (!_gsResults.length) {
    box.innerHTML = `<div id="gsEmpty">No results found.</div>`
    return
  }
  box.innerHTML = _gsResults.map((m, i) => `
    <div class="gs-item${i===_gsFocusIndex?" gs-focused":""}" data-idx="${i}"
      onclick="gsSelectResult(${i})">
      ${m.poster
        ? `<img src="${m.poster}" alt="" loading="lazy"/>`
        : `<img src="" alt="" style="background:var(--bg3)"/>`}
      <div class="gs-item-info">
        <div class="gs-title">${escHtml(m.title||"")}</div>
        <div class="gs-meta">${m.year||""} ${m._group ? `· ${escHtml(m._group)}` : ""}</div>
      </div>
      <span class="gs-tab">${TAB_LABELS[m._tab]||m._tab||""}</span>
    </div>`).join("")
}

function gsSelectResult(idx) {
  const m = _gsResults[idx]
  if (!m) return
  closeGlobalSearch()
  if (m._tab && PAGE_TITLES[m._tab]) setActiveTab(m._tab)
  setTimeout(() => openMovieModal(m.tmdb, m), 100)
}

// Wire up search input
document.addEventListener("DOMContentLoaded", () => {
  const inp = document.getElementById("gsInput")
  if (!inp) return

  inp.addEventListener("input", e => {
    clearTimeout(_gsDebounce)
    _gsDebounce = setTimeout(() => _gsSearch(e.target.value.trim()), 200)
  })

  inp.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") {
      _gsFocusIndex = Math.min(_gsFocusIndex + 1, _gsResults.length - 1)
      _renderGsResults()
      e.preventDefault()
    } else if (e.key === "ArrowUp") {
      _gsFocusIndex = Math.max(_gsFocusIndex - 1, -1)
      _renderGsResults()
      e.preventDefault()
    } else if (e.key === "Enter" && _gsFocusIndex >= 0) {
      gsSelectResult(_gsFocusIndex)
    } else if (e.key === "Escape") {
      closeGlobalSearch()
    }
  })
})

/* ============================================================
   KEYBOARD SHORTCUTS MODAL
============================================================ */

function openShortcuts()  { document.getElementById("shortcutsModal")?.classList.add("open") }
function closeShortcuts() { document.getElementById("shortcutsModal")?.classList.remove("open") }
function isShortcutsOpen(){ return document.getElementById("shortcutsModal")?.classList.contains("open") }

/* ============================================================
   BOOT
============================================================ */

async function boot(){
  applyStoredTheme()
  restoreState()

  await loadConfig()
  await loadStatus()

  try {
    const v = await api("/api/version")
    document.querySelector(".version").textContent = `${v.version} · Cineplete`
  } catch(e) {}

  if (CONFIGURED) await loadResults()
  else { setStatus("Setup required"); render() }
}

document.getElementById("scanBtn").addEventListener("click", rescan)
boot()
