/* ============================================================
   filters.js — filter bar, sort helpers, year bucketing
============================================================ */

const GROUP_TABS = new Set(["franchises","directors","actors"])

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

function getGroupFilter(){
  const val = document.getElementById("groupFilter")?.value || ""
  // Only filter if value exactly matches a group name (datalist selection)
  // This allows partial typing without hiding everything
  if (!val) return ""
  const groups = getGroupsForTab(ACTIVE_TAB)
  const exact = groups.find(g => (g.name||"").toLowerCase() === val.toLowerCase())
  return exact ? exact.name : val
}
function getSort(){ return document.getElementById("sort")?.value || "popularity" }

function applyFilters(list){
  const search = (document.getElementById("search")?.value||"").toLowerCase().trim()
  const year   = document.getElementById("yearFilter")?.value || ""
  const sort   = getSort()

  let out = list.filter(m => {
    if (search && !(m.title||"").toLowerCase().includes(search)) return false
    if (year && yearBucket(m.year) !== year) return false
    return true
  })

  out.sort((a,b) => {
    if (sort==="title")  return (a.title||"").localeCompare(b.title||"")
    if (sort==="year")   return parseInt(b.year||0)-parseInt(a.year||0)
    if (sort==="rating") return (b.rating||0)-(a.rating||0)
    if (sort==="votes")  return (b.votes||0)-(a.votes||0)
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
    const prevGroup = document.getElementById("groupFilter")?.value || ""
    const prevSort  = document.getElementById("sort")?.value || "popularity"
    // Sort A→Z, only groups with missing films
    const groups = getGroupsForTab(ACTIVE_TAB)
      .filter(g=>(g.missing||[]).length>0)
      .sort((a,b)=>(a.name||"").localeCompare(b.name||""))
    const datalistId = `dl-${ACTIVE_TAB}`
    const opts = groups.map(g=>`<option value="${g.name||""}"></option>`).join("")

    bar.innerHTML = `
      <div style="position:relative">
        <input id="groupFilter" list="${datalistId}" placeholder="Filter ${ACTIVE_TAB}…"
          value="${prevGroup}"
          style="min-width:220px;background:var(--bg3);border:1px solid var(--border2);
                 border-radius:8px;color:var(--text);font-family:'DM Mono',monospace;
                 font-size:.78rem;padding:.4rem .75rem;outline:none"/>
        <datalist id="${datalistId}">${opts}</datalist>
      </div>
      ${sortSelect(prevSort)}`

    // Clear button support — if input cleared, re-render
    document.getElementById("groupFilter")?.addEventListener("input", () => render())
  } else {
    const prevSearch = document.getElementById("search")?.value || ""
    const prevYear   = document.getElementById("yearFilter")?.value || ""
    const prevSort   = document.getElementById("sort")?.value || "popularity"
    const yearOpts   = [["","All years"],["2020s","2020s"],["2010s","2010s"],["2000s","2000s"],["1990s","1990s"],["older","Older"]]

    bar.innerHTML = `
      <input id="search" placeholder="Search…" value="${prevSearch}"/>
      <select id="yearFilter">
        ${yearOpts.map(([v,l])=>`<option value="${v}"${prevYear===v?" selected":""}>${l}</option>`).join("")}
      </select>
      ${sortSelect(prevSort)}`
  }
}

function sortSelect(cur){
  const opts = [["popularity","Popularity"],["rating","Rating"],["votes","Votes"],["year","Year"],["title","Title"]]
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