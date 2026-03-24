/* ============================================================
   filters.js — filter bar, sort helpers, year bucketing
============================================================ */

const GROUP_TABS = new Set(["franchises","directors","actors"])
let _activeGroupFilter = ""
let _activeGenreFilter = ""

/* Static TMDB genre ID map — stable, no API call needed */
const GENRE_MAP = {
  28:"Action", 12:"Adventure", 16:"Animation", 35:"Comedy",
  80:"Crime", 99:"Documentary", 18:"Drama", 10751:"Family",
  14:"Fantasy", 36:"History", 27:"Horror", 10402:"Music",
  9648:"Mystery", 10749:"Romance", 878:"Sci-Fi", 53:"Thriller",
  10752:"War", 37:"Western"
}

function getGenreFilter() { return _activeGenreFilter }

function yearBucket(y){
  const yr = parseInt(y||"0",10)
  if (!yr)        return ""
  if (yr >= 2020) return "2020s"
  if (yr >= 2010) return "2010s"
  if (yr >= 2000) return "2000s"
  if (yr >= 1990) return "1990s"
  return "older"
}

function tag(text, cls=""){
  return `<span class="tag ${cls}">${text}</span>`
}

function getGroupFilter(){ return _activeGroupFilter }

function clearGroupFilter(){
  _activeGroupFilter = ""
  const inp = document.getElementById("groupFilterSearch")
  if (inp) inp.value = ""
  const clr = document.getElementById("groupFilterClear")
  if (clr) clr.style.display = "none"
  render()
}

function _initGroupFilter(groups){
  const inp  = document.getElementById("groupFilterSearch")
  const drop = document.getElementById("groupFilterDropdown")
  const clr  = document.getElementById("groupFilterClear")
  if (!inp || !drop) return

  // Restore previous selection display
  if (_activeGroupFilter) inp.value = _activeGroupFilter

  function showDropdown(filter){
    const f = (filter||"").toLowerCase()
    const matched = groups.filter(g => !f || (g.name||"").toLowerCase().includes(f))
    if (!matched.length){ drop.style.display = "none"; return }
    drop.innerHTML = matched.map(g => {
      const n = g.name||""
      const active = n === inp.dataset.selected
      return `<div class="gf-opt" data-name="${n.replace(/"/g,"&quot;")}"
        style="padding:.5rem .85rem;font-size:.78rem;cursor:pointer;
               color:${active?"var(--gold)":"var(--text2)"};
               background:${active?"var(--gold-glow)":"transparent"}"
        onmouseover="this.style.background='var(--bg3)'"
        onmouseout="this.style.background='${active?"var(--gold-glow)":"transparent"}'"
        >${n}</div>`
    }).join("")
    drop.style.display = "block"

    drop.querySelectorAll(".gf-opt").forEach(el => {
      el.addEventListener("mousedown", e => {
        e.preventDefault()
        const name = el.dataset.name
        _activeGroupFilter = name
        inp.value = name
        drop.style.display = "none"
        if (clr) clr.style.display = ""
        render()
      })
    })
  }

  inp.addEventListener("input", () => {
    _activeGroupFilter = ""
    if (clr) clr.style.display = inp.value ? "" : "none"
    showDropdown(inp.value)
  })
  inp.addEventListener("focus", () => showDropdown(inp.value))
  inp.addEventListener("blur",  () => setTimeout(() => { drop.style.display = "none" }, 150))

  // Show dropdown on first render if already has a value
  if (inp.value) showDropdown(inp.value)
}
function getSort(){ return document.getElementById("sort")?.value || "popularity" }

function applyFilters(list){
  const search = (document.getElementById("search")?.value||"").toLowerCase().trim()
  const year   = document.getElementById("yearFilter")?.value || ""
  const sort   = getSort()

  let out = list.filter(m => {
    if (search && !(m.title||"").toLowerCase().includes(search)) return false
    if (year && yearBucket(m.year) !== year) return false
    if (_activeGenreFilter && !(m.genre_ids||[]).includes(parseInt(_activeGenreFilter))) return false
    return true
  })

  out.sort((a,b) => {
    if (sort==="title")   return (a.title||"").localeCompare(b.title||"")
    if (sort==="year")    return parseInt(b.year||0)-parseInt(a.year||0)
    if (sort==="rating")  return (b.rating||0)-(a.rating||0)
    if (sort==="votes")   return (b.votes||0)-(a.votes||0)
    if (sort==="matches") return (b.rec_score||0)-(a.rec_score||0)
    return (b.popularity||0)-(a.popularity||0)
  })
  return out
}

function sortList(list){
  const sort = getSort()
  return [...list].sort((a,b) => {
    if (sort==="title")  return (a.title||"").localeCompare(b.title||"")
    if (sort==="year")   return parseInt(b.year||0)-parseInt(a.year||0)
    if (sort==="rating") return (b.rating||0)-(a.rating||0)
    if (sort==="votes")  return (b.votes||0)-(a.votes||0)
    return (b.popularity||0)-(a.popularity||0)
  })
}

function updateFilterBar(){
  const bar = document.getElementById("topFilters")
  const hiddenTabs = new Set(["dashboard","config","notmdb","nomatch"])
  if (hiddenTabs.has(ACTIVE_TAB)){ bar.style.display="none"; return }
  bar.style.display="flex"

  if (GROUP_TABS.has(ACTIVE_TAB)){
    const prevGroup = _activeGroupFilter
    const prevSort  = document.getElementById("sort")?.value || "popularity"
    const groups = getGroupsForTab(ACTIVE_TAB)
      .filter(g=>(g.missing||[]).length>0)
      .sort((a,b)=>(a.name||"").localeCompare(b.name||""))

    const prevGenreG = _activeGenreFilter

    bar.innerHTML = `
      <div style="position:relative" id="groupFilterWrap">
        <input id="groupFilterSearch" placeholder="Filter ${ACTIVE_TAB}… (A→Z)"
          value="${prevGroup}" autocomplete="off"
          style="min-width:200px;background:var(--bg3);border:1px solid var(--border2);
                 border-radius:8px;color:var(--text);font-family:'DM Mono',monospace;
                 font-size:.78rem;padding:.4rem 2rem .4rem .75rem;outline:none"/>
        <span id="groupFilterClear" onclick="clearGroupFilter()"
          style="position:absolute;right:.5rem;top:50%;transform:translateY(-50%);
                 color:var(--text3);cursor:pointer;font-size:.9rem;display:${prevGroup?"":"none"}">✕</span>
        <div id="groupFilterDropdown" style="
          display:none;position:absolute;top:calc(100% + 4px);left:0;min-width:200px;
          max-height:260px;overflow-y:auto;background:var(--bg2);border:1px solid var(--border2);
          border-radius:8px;z-index:200;box-shadow:0 8px 24px rgba(0,0,0,.5)">
        </div>
      </div>
      <select id="genreFilter">
        <option value="">All genres</option>
        ${Object.entries(GENRE_MAP).map(([id,name])=>`<option value="${id}"${prevGenreG===id?" selected":""}>${name}</option>`).join("")}
      </select>
      ${sortSelect(prevSort)}`

    _initGroupFilter(groups)
    updateExportBtn()
  } else {
    const prevSearch = document.getElementById("search")?.value || ""
    const prevYear   = document.getElementById("yearFilter")?.value || ""
    const prevSort   = document.getElementById("sort")?.value || "popularity"
    const prevGenre  = _activeGenreFilter
    const yearOpts   = [["","All years"],["2020s","2020s"],["2010s","2010s"],["2000s","2000s"],["1990s","1990s"],["older","Older"]]

    bar.innerHTML = `
      <input id="search" placeholder="Search…" value="${prevSearch}"/>
      <select id="yearFilter">
        ${yearOpts.map(([v,l])=>`<option value="${v}"${prevYear===v?" selected":""}>${l}</option>`).join("")}
      </select>
      <select id="genreFilter">
        <option value="">All genres</option>
        ${Object.entries(GENRE_MAP).map(([id,name])=>`<option value="${id}"${prevGenre===id?" selected":""}>${name}</option>`).join("")}
      </select>
      ${sortSelect(prevSort)}`
  }
  updateExportBtn()
}

function onGenreFilterChange(val) {
  _activeGenreFilter = val
  render()
}

function sortSelect(cur){
  const opts = [["popularity","Popularity"],["matches","Matches"],["rating","Rating"],["votes","Votes"],["year","Year"],["title","Title"]]
  return `<select id="sort">
    ${opts.map(([v,l])=>`<option value="${v}"${cur===v?" selected":""}>${l}</option>`).join("")}
  </select>`
}

function getGroupsForTab(tab){
  if (tab==="franchises") return DATA.franchises||[]
  if (tab==="directors")  return DATA.directors ||[]
  if (tab==="actors")     return DATA.actors    ||[]
  return []
}