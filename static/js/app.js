/* ============================================================
   app.js — globals, render router, navigation, boot
   Loads after: api.js, scan.js, filters.js, render.js, config.js
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

/* ============================================================
   RENDER ROUTER
============================================================ */

function render(){
  if (!DATA && !["config"].includes(ACTIVE_TAB)){
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
  // Default sort for suggestions is matches, everything else is popularity
  const sortEl = document.getElementById("sort")
  if (sortEl){
    if (tab === "suggestions" && sortEl.value === "popularity") sortEl.value = "matches"
    if (tab !== "suggestions" && sortEl.value === "matches")    sortEl.value = "popularity"
  }
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
})

// Keyboard shortcut: R = rescan
document.addEventListener("keydown", e=>{
  if (e.key==="r" && !e.ctrlKey && !e.metaKey && document.activeElement.tagName!=="INPUT"){
    rescan()
  }
})

/* ============================================================
   BOOT
============================================================ */

async function boot(){
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