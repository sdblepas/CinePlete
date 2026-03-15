/* ============================================================
   CINEPLETE — app.js
   Cinematic dark-luxury UI · DM Mono + Syne · Gold accent
============================================================ */

let DATA       = null
let CONFIG     = null
let CONFIGURED = false
let ACTIVE_TAB = "dashboard"
let _pollTimer = null

const GROUP_TABS = new Set(["franchises","directors","actors"])

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
}

/* ============================================================
   TOAST
============================================================ */

function toast(msg, type = "info"){
  const colors = { info: "#9090a0", success: "#22c55e", error: "#ef4444", gold: "#F5C518" }
  const el = document.createElement("div")
  el.className = "toast"
  el.innerHTML = `
    <div class="toast-dot" style="background:${colors[type]||colors.info}"></div>
    <span>${msg}</span>`
  document.getElementById("toastContainer").appendChild(el)
  setTimeout(() => {
    el.classList.add("fade-out")
    el.addEventListener("animationend", () => el.remove())
  }, 3000)
}

/* ============================================================
   API
============================================================ */

async function api(path, method = "GET", body = null){
  const opts = { method, headers:{} }
  if (body){ opts.headers["Content-Type"]="application/json"; opts.body=JSON.stringify(body) }
  const r = await fetch(path, opts)
  return r.json()
}

/* ============================================================
   DATA LOADING
============================================================ */

async function loadConfig(){
  CONFIG = await api("/api/config")
}

async function loadStatus(){
  const s = await api("/api/config/status")
  CONFIGURED = !!s.configured
}

async function loadResults(){
  setStatus("Loading…")
  const data = await api("/api/results")
  if (data.scanning){
    setStatus("Scan in progress…")
    startPolling()
    renderSkeleton()
    return
  }
  DATA = data
  setStatus(`Updated ${fmtDate(DATA.generated_at)}`)
  updateBadges()
  render()
}

function fmtDate(iso){
  if (!iso) return ""
  try {
    return new Date(iso).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"})
  } catch(e){ return iso }
}

function fmtDuration(s){
  if (!s && s !== 0) return ""
  if (s < 60) return `${s}s`
  const m = Math.floor(s/60), sec = s%60
  return sec ? `${m}m ${sec}s` : `${m}m`
}

function setStatus(txt){ document.getElementById("status").textContent = txt }

/* ============================================================
   BADGES
============================================================ */

function updateBadges(){
  if (!DATA) return
  const b = (id, n) => {
    const el = document.getElementById(id)
    if (!el) return
    if (n > 0){ el.textContent = n > 99 ? "99+" : n; el.style.display = "" }
    else el.style.display = "none"
  }
  b("badge-notmdb",  (DATA.no_tmdb_guid   || []).length)
  b("badge-nomatch", (DATA.tmdb_not_found || []).length)
  b("badge-wishlist",(DATA.wishlist       || []).length)
}

/* ============================================================
   SCAN + POLLING
============================================================ */

async function rescan(){
  if (!CONFIGURED){ toast("Complete setup first.", "error"); return }
  const res = await api("/api/scan","POST")
  if (!res.ok){ toast(res.error || "Could not start scan","error"); return }
  startPolling()
}

function startPolling(){
  stopPolling()
  renderScanProgress(null)
  _pollTimer = setInterval(pollScanStatus, 1500)
}

function stopPolling(){
  if (_pollTimer){ clearInterval(_pollTimer); _pollTimer = null }
}

async function pollScanStatus(){
  let s
  try { s = await api("/api/scan/status") } catch(e){ return }
  renderScanProgress(s)
  if (!s.running){
    stopPolling()
    document.getElementById("scanProgress")?.remove()
    if (s.error){ toast(`Scan failed: ${s.error}`,"error"); return }
    const data = await api("/api/results")
    DATA = data
    const dur = s.last_duration ? ` · took ${fmtDuration(s.last_duration)}` : ""
    setStatus(`Updated ${fmtDate(DATA.generated_at)}${dur}`)
    const durEl = document.getElementById("last-duration")
    if (durEl && s.last_duration) durEl.textContent = `Last scan took ${fmtDuration(s.last_duration)}`
    updateBadges()
    toast("Scan complete","success")
    render()
  }
}

function renderScanProgress(s){
  let el = document.getElementById("scanProgress")
  if (!el){
    el = document.createElement("div"); el.id = "scanProgress"
    document.body.appendChild(el)
  }
  if (!s || !s.running){
    el.innerHTML = `<div style="display:flex;align-items:center;gap:.6rem;color:var(--text2);font-size:.78rem">
      <div style="width:12px;height:12px;border:2px solid var(--border2);border-top-color:var(--gold);border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0"></div>
      Starting scan…
    </div>
    <style>@keyframes spin{to{transform:rotate(360deg)}}</style>`
    return
  }
  const pct = s.step_total ? Math.round(s.step_index/s.step_total*100) : 0
  el.innerHTML = `
  <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
  <div style="display:flex;justify-content:space-between;margin-bottom:.5rem">
    <span style="font-size:.72rem;font-family:'Syne',sans-serif;font-weight:700;color:var(--text)">Scanning…</span>
    <span style="font-size:.68rem;color:var(--text3)">${s.step_index}/${s.step_total}</span>
  </div>
  <div style="height:3px;background:var(--border);border-radius:3px;margin-bottom:.6rem;overflow:hidden">
    <div style="height:3px;width:${pct}%;background:var(--gold);border-radius:3px;transition:width .4s ease"></div>
  </div>
  <div style="font-size:.7rem;color:var(--text3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
    ${s.step||""}${s.detail?` — ${s.detail}`:""}
  </div>`
  setStatus(`${s.step||"Scanning…"} (${pct}%)`)
}

/* ============================================================
   SKELETON LOADER
============================================================ */

function renderSkeleton(){
  const c = document.getElementById("content")
  const bar = h => `<div class="skeleton" style="height:${h}px;border-radius:6px"></div>`
  c.innerHTML = `
  <div class="grid-4" style="margin-bottom:.85rem">
    ${[1,2,3,4].map(()=>`<div class="score-card">${bar(20)}<div style="margin-top:.8rem">${bar(40)}</div>${bar(3)}</div>`).join("")}
  </div>
  <div class="grid-3" style="margin-bottom:.85rem">
    ${[1,2,3].map(()=>`<div class="card">${bar(16)}<div style="margin-top:.85rem">${bar(180)}</div></div>`).join("")}
  </div>
  <div class="grid-2">
    ${[1,2].map(()=>`<div class="card">${bar(16)}<div style="margin-top:.85rem">${bar(120)}</div></div>`).join("")}
  </div>`
}

/* ============================================================
   HELPERS
============================================================ */

function yearBucket(y){
  const yr = parseInt(y||"0",10)
  if (!yr)       return ""
  if (yr >= 2020) return "2020s"
  if (yr >= 2010) return "2010s"
  if (yr >= 2000) return "2000s"
  if (yr >= 1990) return "1990s"
  return "older"
}

function tag(text, cls=""){
  return `<span class="tag ${cls}">${text}</span>`
}

/* ============================================================
   MOVIE CARD  (poster-first design)
============================================================ */

function movieCard(m, extraTag = ""){
  const poster = m.poster
    ? `<img class="movie-poster" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="movie-poster-placeholder">NO<br>IMG</div>`

  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="addToRadarr(${m.tmdb},'${(m.title||'').replace(/'/g,"\\'")}',this)">+ Radarr</button>`
    : ""

  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" onclick="removeWishlist(${m.tmdb},this)">★ Wishlisted</button>`
    : `<button class="btn-sm btn-wishlist"   onclick="addWishlist(${m.tmdb},this)">☆ Wishlist</button>`

  const rating = parseFloat(m.rating||0).toFixed(1)
  const pop    = Math.round(m.popularity||0)

  return `
  <div class="movie-card">
    <div class="movie-card-inner">
      ${poster}
      <div class="movie-body">
        <div class="movie-title">${m.title||"Untitled"} <span class="movie-year">${m.year?`(${m.year})`:""}</span></div>
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

/* ============================================================
   WISHLIST / RADARR ACTIONS
============================================================ */

async function addWishlist(tmdb, btn){
  await api("/api/wishlist/add","POST",{tmdb})
  btn.className  = "btn-sm btn-wishlisted"
  btn.textContent = "★ Wishlisted"
  btn.onclick     = () => removeWishlist(tmdb,btn)
  toast("Added to Wishlist","gold")
}

async function removeWishlist(tmdb, btn){
  await api("/api/wishlist/remove","POST",{tmdb})
  btn.className  = "btn-sm btn-wishlist"
  btn.textContent = "☆ Wishlist"
  btn.onclick     = () => addWishlist(tmdb,btn)
  toast("Removed from Wishlist")
}

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
    toast("Radarr error","error")
  }
}

/* ============================================================
   CHART REGISTRY
============================================================ */

const _charts = {}
function destroyChart(id){ if(_charts[id]){_charts[id].destroy();delete _charts[id]} }
function mkChart(id,cfg){ destroyChart(id); _charts[id]=new Chart(document.getElementById(id),cfg); return _charts[id] }

/* ============================================================
   FILTERS
============================================================ */

function getGroupFilter(){ return document.getElementById("groupFilter")?.value || "" }
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

/* ============================================================
   FILTER BAR  (tab-aware)
============================================================ */

function updateFilterBar(){
  const bar = document.getElementById("topFilters")
  const hiddenTabs = new Set(["dashboard","config","notmdb","nomatch"])
  if (hiddenTabs.has(ACTIVE_TAB)){ bar.style.display="none"; return }
  bar.style.display="flex"

  if (GROUP_TABS.has(ACTIVE_TAB)){
    const prevGroup = document.getElementById("groupFilter")?.value || ""
    const prevSort  = document.getElementById("sort")?.value || "popularity"
    const groups = getGroupsForTab(ACTIVE_TAB).filter(g=>(g.missing||[]).length>0)
    const opts   = groups.map(g=>{
      const n = g.name||""; return `<option value="${n}"${n===prevGroup?" selected":""}>${n}</option>`
    }).join("")

    bar.innerHTML = `
      <select id="groupFilter" style="min-width:200px">
        <option value="">All ${ACTIVE_TAB}</option>${opts}
      </select>
      ${sortSelect(prevSort)}`
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

/* ============================================================
   DASHBOARD
============================================================ */

function renderDashboard(){
  const c = document.getElementById("content")
  const s = DATA.scores||{}
  const p = DATA.plex  ||{}

  const ignoredFranchises = new Set(DATA._ignored_franchises||[])
  let fComplete=0,fOne=0,fMore=0
  ;(DATA.franchises||[]).filter(f=>!ignoredFranchises.has(f.name)).forEach(f=>{
    const n=(f.missing||[]).length
    if(n===0) fComplete++; else if(n===1) fOne++; else fMore++
  })

  const classicsMiss  = (DATA.classics||[]).length
  const classicsTotal = Math.round(classicsMiss/(1-(s.classics_proxy_pct||0)/100))||classicsMiss
  const classicsHave  = Math.max(0,classicsTotal-classicsMiss)

  const noGuid  = p.no_tmdb_guid||0
  const noMatch = (DATA.tmdb_not_found||[]).length
  const okMovies= Math.max(0,(p.indexed_tmdb||0)-noMatch)

  const dBuckets = {"0":0,"1–2":0,"3–5":0,"6–10":0,"10+":0}
  ;(DATA.directors||[]).forEach(d=>{
    const n=(d.missing||[]).length
    if(n===0)      dBuckets["0"]++
    else if(n<=2)  dBuckets["1–2"]++
    else if(n<=5)  dBuckets["3–5"]++
    else if(n<=10) dBuckets["6–10"]++
    else           dBuckets["10+"]++
  })

  const topActors = (DATA.charts?.top_actors||[]).slice(0,10)

  const scoreCardHTML = (label, val, color, tab="") => {
    const v = parseFloat(val)||0
    const click = tab ? `onclick="setActiveTab('${tab}')" style="cursor:pointer"` : ""
    return `
    <div class="score-card" ${click}>
      <div class="score-label">${label}</div>
      <div class="score-value" style="color:${color}">${v}<span style="font-size:1rem;opacity:.6">%</span></div>
      <div class="score-bar-wrap"><div class="score-bar" style="width:0%;background:${color}" data-pct="${v}"></div></div>
    </div>`
  }

  const srow = (label,val,color="")=>`
  <div class="stat-row">
    <span class="stat-label">${label}</span>
    <span class="stat-val"${color?` style="color:${color}"`:""}>${val}</span>
  </div>`

  const leg = (col,label,val,tab="",filter="")=>{
    const click = tab ? `onclick="setActiveTab('${tab}')" style="cursor:pointer;user-select:none"` : ""
    return `<div style="display:flex;align-items:center;gap:.5rem;padding:.2rem 0;font-size:.78rem" ${click}>
      <span style="width:8px;height:8px;border-radius:50%;background:${col};flex-shrink:0;display:inline-block"></span>
      <span style="color:var(--text2);flex:1">${label}</span>
      <b style="color:var(--text)">${val}</b>
    </div>`
  }

  c.innerHTML = `
  <div class="grid-4" style="margin-bottom:.85rem">
    ${scoreCardHTML("Franchise Completion", s.franchise_completion_pct??0, "#F5C518", "franchises")}
    ${scoreCardHTML("Directors Score",      s.directors_proxy_pct     ??0, "#3b82f6", "directors")}
    ${scoreCardHTML("Classics Coverage",    s.classics_proxy_pct      ??0, "#a855f7", "classics")}
    ${scoreCardHTML("Global Score",         s.global_cinema_score     ??0, "#22c55e")}
  </div>

  <div class="grid-3" style="margin-bottom:.85rem">
    <div class="card">
      <div class="card-title">Franchise Status</div>
      <canvas id="cFranchise" height="170"></canvas>
      <div style="margin-top:.85rem">
        ${leg("#22c55e","Complete",   fComplete,  "franchises")}
        ${leg("#F5C518","Missing 1",  fOne,       "franchises")}
        ${leg("#ef4444","Missing 2+", fMore,      "franchises")}
      </div>
    </div>
    <div class="card">
      <div class="card-title">Classics Coverage</div>
      <canvas id="cClassics" height="170"></canvas>
      <div style="margin-top:.85rem">
        ${leg("#a855f7","In Library", classicsHave, "classics")}
        ${leg("#2a2a30","Missing",    classicsMiss, "classics")}
      </div>
    </div>
    <div class="card">
      <div class="card-title">Metadata Health</div>
      <canvas id="cMeta" height="170"></canvas>
      <div style="margin-top:.85rem">
        ${leg("#22c55e","Valid TMDB", okMovies)}
        ${leg("#F5C518","No GUID",    noGuid,   "notmdb")}
        ${leg("#ef4444","No Match",   noMatch,  "nomatch")}
      </div>
    </div>
  </div>

  <div class="grid-31">
    <div class="card">
      <div class="card-title">Top Actors in Library</div>
      <canvas id="cActors" height="200"></canvas>
    </div>
    <div class="card">
      <div class="card-title">Directors — Missing Films</div>
      <canvas id="cDirs" height="200"></canvas>
    </div>
    <div class="card">
      <div class="card-title">Library Stats</div>
      ${srow("Scanned items",      p.scanned_items??0)}
      ${srow("Indexed TMDB",       p.indexed_tmdb ??0)}
      ${srow("Shorts skipped",     p.skipped_short??0)}
      ${srow("No TMDB GUID",       noGuid,  noGuid  ?"var(--amber)":"")}
      ${srow("TMDB no match",      noMatch, noMatch ?"var(--red)":"")}
      ${srow("Franchises tracked", (DATA.franchises||[]).filter(f=>!ignoredFranchises.has(f.name)).length)}
      ${srow("Directors tracked",  (DATA.directors ||[]).length)}
      ${srow("Wishlist",           (DATA.wishlist  ||[]).length)}
    </div>
  </div>`

  // animate score bars
  requestAnimationFrame(()=>{
    document.querySelectorAll(".score-bar").forEach(el=>{
      setTimeout(()=>{ el.style.width = el.dataset.pct+"%" }, 80)
    })

    Chart.defaults.color       = "#606070"
    Chart.defaults.font.family = "'DM Mono',monospace"
    Chart.defaults.font.size   = 11

    const doughnut = (labels,data,colors,onClick)=>({
      type:"doughnut",
      data:{labels,datasets:[{data,backgroundColor:colors,borderColor:"#141416",borderWidth:3,hoverOffset:6}]},
      options:{
        cutout:"65%", animation:{duration:700},
        plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>`${ctx.label}: ${ctx.parsed}`}}},
        onClick: (e,els)=>{ if(els.length&&onClick) onClick(els[0].index) }
      }
    })

    mkChart("cFranchise", doughnut(
      ["Complete","Missing 1","Missing 2+"],
      [fComplete,fOne,fMore],
      ["#22c55e","#F5C518","#ef4444"],
      i=>{ if(i>0) setActiveTab("franchises") }
    ))
    mkChart("cClassics", doughnut(
      ["In Library","Missing"],
      [classicsHave,classicsMiss],
      ["#a855f7","#27272a"],
      i=>{ if(i===1) setActiveTab("classics") }
    ))
    mkChart("cMeta", doughnut(
      ["Valid TMDB","No GUID","No Match"],
      [okMovies,noGuid,noMatch],
      ["#22c55e","#F5C518","#ef4444"],
      i=>{ if(i===1) setActiveTab("notmdb"); else if(i===2) setActiveTab("nomatch") }
    ))

    mkChart("cActors",{
      type:"bar",
      data:{
        labels:topActors.map(a=>a.name),
        datasets:[{data:topActors.map(a=>a.count),
          backgroundColor:topActors.map((_,i)=>`hsl(${42+i*3},90%,${58-i*2}%)`),
          borderRadius:4,borderSkipped:false}]
      },
      options:{
        indexAxis:"y", animation:{duration:700},
        scales:{
          x:{grid:{color:"#1a1a1e"},ticks:{color:"#606070"}},
          y:{grid:{display:false},ticks:{color:"#9090a0"}}
        },
        plugins:{legend:{display:false}}
      }
    })

    mkChart("cDirs",{
      type:"bar",
      data:{
        labels:Object.keys(dBuckets),
        datasets:[{data:Object.values(dBuckets),
          backgroundColor:["#2a2a30","#3b82f6","#F5C518","#ef4444","#7f1d1d"],
          borderRadius:4,borderSkipped:false}]
      },
      options:{
        animation:{duration:700},
        scales:{
          x:{grid:{display:false},ticks:{color:"#9090a0"}},
          y:{grid:{color:"#1a1a1e"},ticks:{color:"#606070"}}
        },
        plugins:{legend:{display:false},tooltip:{callbacks:{title:ctx=>`Missing: ${ctx[0].label} films`}}}
      }
    })
  })
}

/* ============================================================
   GROUPED LIST  (franchises / directors / actors)
============================================================ */

function renderGroupedList({ groups, nameKey, nameIcon, ignoreHandler, emptyMsg }){
  const c          = document.getElementById("content")
  const groupFilter = getGroupFilter()
  const sort        = getSort()

  let html = ""

  groups.forEach(g => {
    const name = g[nameKey]||""
    if (groupFilter && name !== groupFilter) return

    const sorted = [...(g.missing||[])].sort((a,b)=>{
      if(sort==="title")  return (a.title||"").localeCompare(b.title||"")
      if(sort==="year")   return parseInt(b.year||0)-parseInt(a.year||0)
      if(sort==="rating") return (b.rating||0)-(a.rating||0)
      if(sort==="votes")  return (b.votes||0)-(a.votes||0)
      return (b.popularity||0)-(a.popularity||0)
    })
    if (!sorted.length) return

    html += `
    <div class="mb-group" style="margin-bottom:2rem">
      <div class="group-header">
        <div>
          <span class="group-name">${nameIcon} ${name}</span>
          ${g.have!==undefined
            ? `<span class="group-count">${g.have}/${g.total} in library</span>`
            : `<span class="group-count">${sorted.length} missing</span>`}
        </div>
        <button class="btn-sm btn-ignore"
          onclick="${ignoreHandler}('${name.replace(/'/g,"\\'")}',this)">Ignore</button>
      </div>
      <div class="grid-2">${sorted.map(movieCard).join("")}</div>
    </div>`
  })

  c.innerHTML = html || emptyStateHTML(emptyMsg)
}

function emptyStateHTML(msg){
  return `<div class="empty-state">
    <div class="empty-icon">🎬</div>
    <div class="empty-title">${msg}</div>
    <div class="empty-sub">Nothing to show here.</div>
  </div>`
}

/* ============================================================
   FRANCHISES
============================================================ */

function renderFranchises(){
  renderGroupedList({
    groups: DATA.franchises||[], nameKey:"name", nameIcon:"🎬",
    ignoreHandler:"ignoreFranchise", emptyMsg:"No missing franchise movies 🎉"
  })
}

async function ignoreFranchise(name, btn){
  await api("/api/ignore","POST",{kind:"franchise",value:name})
  if (!DATA._ignored_franchises) DATA._ignored_franchises=[]
  if (!DATA._ignored_franchises.includes(name)) DATA._ignored_franchises.push(name)
  btn.closest(".mb-group").remove()
  updateFilterBar()
  toast(`"${name}" ignored`,"info")
}

/* ============================================================
   DIRECTORS
============================================================ */

function renderDirectors(){
  renderGroupedList({
    groups: DATA.directors||[], nameKey:"name", nameIcon:"🎬",
    ignoreHandler:"ignoreDirector", emptyMsg:"No missing director films found"
  })
}

async function ignoreDirector(name, btn){
  await api("/api/ignore","POST",{kind:"director",value:name})
  DATA.directors = (DATA.directors||[]).filter(d=>d.name!==name)
  btn.closest(".mb-group").remove()
  updateFilterBar()
  toast(`Director "${name}" ignored`)
}

/* ============================================================
   ACTORS
============================================================ */

function renderActors(){
  renderGroupedList({
    groups: DATA.actors||[], nameKey:"name", nameIcon:"🎭",
    ignoreHandler:"ignoreActor", emptyMsg:"No actor suggestions found"
  })
}

async function ignoreActor(name, btn){
  await api("/api/ignore","POST",{kind:"actor",value:name})
  DATA.actors = (DATA.actors||[]).filter(a=>a.name!==name)
  btn.closest(".mb-group").remove()
  updateFilterBar()
  toast(`Actor "${name}" ignored`)
}

/* ============================================================
   CLASSICS
============================================================ */

function renderClassics(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.classics||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("No missing classics 🎉"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} classic films missing from your library</p>
    <div class="grid-2">${list.map(movieCard).join("")}</div>`
}

/* ============================================================
   SUGGESTIONS
============================================================ */

function renderSuggestions(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.suggestions||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("No suggestions available"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} films recommended by your library</p>
    <div class="grid-2">${list.map(m => movieCard(m, m.rec_score
      ? `<span class="tag tag-gold" style="font-size:.6rem">⚡ ${m.rec_score} match${m.rec_score>1?"es":""}</span>`
      : ""
    )).join("")}</div>`
}

/* ============================================================
   WISHLIST
============================================================ */

function renderWishlist(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.wishlist||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("Wishlist is empty"); return }
  c.innerHTML = `<div class="grid-2">${list.map(movieCard).join("")}</div>`
}

/* ============================================================
   NO TMDB GUID
============================================================ */

function renderNoTmdb(){
  const c    = document.getElementById("content")
  const list = DATA.no_tmdb_guid||[]
  if (!list.length){ c.innerHTML=emptyStateHTML("All movies have a TMDB GUID 🎉"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} movies without a TMDB GUID — fix via Plex → Fix Match → TheMovieDB</p>
    <div style="display:flex;flex-direction:column;gap:.4rem">
      ${list.map(m=>`
      <div class="meta-item">
        <span class="tag tag-red" style="flex-shrink:0">NO GUID</span>
        <span class="meta-item-title">${m.title||"Unknown"}</span>
        ${m.year?`<span class="meta-item-year">(${m.year})</span>`:""}
      </div>`).join("")}
    </div>`
}

/* ============================================================
   TMDB NO MATCH
============================================================ */

function renderNoMatch(){
  const c    = document.getElementById("content")
  const list = DATA.tmdb_not_found||[]
  if (!list.length){ c.innerHTML=emptyStateHTML("All TMDB matches resolved 🎉"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} movies with invalid TMDB metadata</p>
    <div style="display:flex;flex-direction:column;gap:.4rem">
      ${list.map(m=>`
      <div class="meta-item">
        <span class="tag tag-red" style="flex-shrink:0">NO MATCH</span>
        <span class="meta-item-title">${m.title || "Unknown title"}</span>
        <span class="meta-item-year">${tag(`tmdb:${m.tmdb}`)}</span>
      </div>`).join("")}
    </div>`
}

/* ============================================================
   CONFIG
============================================================ */

function _ageStr(s){
  if (s < 3600)       return `${Math.floor(s/60)}m ago`
  if (s < 86400)      return `${Math.floor(s/3600)}h ago`
  return `${Math.floor(s/86400)}d ago`
}

async function loadCacheInfo(){
  try {
    const [info, bkp] = await Promise.all([
      api("/api/cache/info"),
      api("/api/cache/backup/info"),
    ])
    const el = document.getElementById("cache-info")
    if (!el) return

    let html = ""
    if (!info.exists){
      html += `<div>No cache yet — will be created on first scan.</div>`
    } else {
      html += `<div>Cache: <span style="color:var(--text)">${info.size_mb} MB</span> · updated <span style="color:var(--text)">${_ageStr(info.age_seconds)}</span></div>`
    }
    if (bkp.exists){
      html += `<div style="margin-top:.3rem">Backup: <span style="color:var(--text)">${bkp.size_mb} MB</span> · saved <span style="color:var(--text)">${_ageStr(bkp.age_seconds)}</span></div>`
    } else {
      html += `<div style="margin-top:.3rem;color:var(--text3)">No backup yet</div>`
    }
    el.innerHTML = html
  } catch(e) {}
}

async function backupCache(){
  const res = await api("/api/cache/backup","POST",{})
  if (res.ok){
    toast(`Cache backed up (${res.size_mb} MB)`,"success")
    loadCacheInfo()
  } else {
    toast("Backup failed: " + res.error,"error")
  }
}

async function restoreCache(){
  if (!confirm("Restore cache from backup? Current cache will be overwritten.")) return
  const res = await api("/api/cache/restore","POST",{})
  if (res.ok){
    toast(`Cache restored (${res.size_mb} MB)`,"success")
    loadCacheInfo()
  } else {
    toast("Restore failed: " + res.error,"error")
  }
}

async function clearCache(){
  if (!confirm("Clear the TMDB cache? The next scan will re-fetch all data from TMDB.")) return
  const res = await api("/api/cache/clear","POST",{})
  if (res.ok){
    toast("TMDB cache cleared","success")
    loadCacheInfo()
  } else {
    toast("Failed to clear cache: " + res.error,"error")
  }
}

function renderConfig(){
  const c     = document.getElementById("content")
  const cfg   = CONFIG||{}
  const plex  = cfg.PLEX        ||{}
  const tmdb  = cfg.TMDB        ||{}
  const radarr= cfg.RADARR      ||{}
  const cls   = cfg.CLASSICS    ||{}
  const act   = cfg.ACTOR_HITS  ||{}
  const auto  = cfg.AUTOMATION  ||{}

  const field = (id, label, value, type="text") => `
  <div class="form-group">
    <label class="form-label" for="${id}">${label}</label>
    <input class="form-input" id="${id}" type="${type}" value="${value??""}" />
  </div>`

  c.innerHTML = `
  <div style="max-width:520px">
    <div class="form-section">
      <div class="form-section-title">Plex</div>
      ${field("cfg_plex_url",   "Plex URL",     plex.PLEX_URL    ||"")}
      ${field("cfg_plex_token", "Plex Token",   plex.PLEX_TOKEN  ||"")}
      ${field("cfg_library",    "Library Name", plex.LIBRARY_NAME||"")}
    </div>

    <div class="form-section">
      <div class="form-section-title">TMDB</div>
      ${field("cfg_tmdb_key","TMDB API Key", tmdb.TMDB_API_KEY||"")}
    </div>

    <details class="form-section">
      <summary style="display:flex;align-items:center;justify-content:space-between">
        <span class="form-section-title" style="margin-bottom:0">Advanced Settings</span>
        <svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text3)" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
      </summary>
      <div style="margin-top:1rem">
        <p style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin-bottom:.75rem">Classics</p>
        ${field("cfg_classics_pages",  "Pages to fetch",    cls.CLASSICS_PAGES      ??4,    "number")}
        ${field("cfg_classics_votes",  "Minimum votes",     cls.CLASSICS_MIN_VOTES  ??5000, "number")}
        ${field("cfg_classics_rating", "Minimum rating",    cls.CLASSICS_MIN_RATING ??8.0,  "number")}
        ${field("cfg_classics_max",    "Max results",       cls.CLASSICS_MAX_RESULTS??120,  "number")}
        <p style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:1rem 0 .75rem">Actors</p>
        ${field("cfg_actor_votes", "Min votes per film",    act.ACTOR_MIN_VOTES            ??500, "number")}
        ${field("cfg_actor_max",   "Max results per actor", act.ACTOR_MAX_RESULTS_PER_ACTOR??10,  "number")}
        <p style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:1rem 0 .75rem">TMDB</p>
        ${field("cfg_tmdb_workers","Concurrent workers (1–10)", tmdb.TMDB_WORKERS??6,"number")}
        <p style="font-size:.68rem;color:var(--text3);margin-top:-.25rem;margin-bottom:.5rem">Higher = faster first scan. Default 6, max 10.</p>
        <p style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:1rem 0 .75rem">Plex Scanner</p>
        ${field("cfg_plex_page_size","Page size",               plex.PLEX_PAGE_SIZE   ??500, "number")}
        ${field("cfg_short_limit",  "Short movie limit (min)", plex.SHORT_MOVIE_LIMIT??60,  "number")}
      </div>
    </details>

    <div class="form-section">
      <div class="form-section-title">Radarr <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span></div>
      <div class="form-group" style="display:flex;align-items:center;gap:.6rem">
        <input type="checkbox" id="cfg_radarr_enabled" ${radarr.RADARR_ENABLED?"checked":""}
          style="accent-color:var(--gold);width:14px;height:14px;cursor:pointer"/>
        <label for="cfg_radarr_enabled" class="form-label" style="margin:0;cursor:pointer">Enabled</label>
      </div>
      ${field("cfg_radarr_url",     "Radarr URL",         radarr.RADARR_URL              ||"")}
      ${field("cfg_radarr_key",     "Radarr API Key",     radarr.RADARR_API_KEY          ||"")}
      ${field("cfg_radarr_root",    "Root Folder Path",   radarr.RADARR_ROOT_FOLDER_PATH ||"")}
      ${field("cfg_radarr_quality", "Quality Profile ID", radarr.RADARR_QUALITY_PROFILE_ID??6,"number")}
      <div class="form-group" style="display:flex;align-items:center;gap:.6rem">
        <input type="checkbox" id="cfg_radarr_search" ${radarr.RADARR_SEARCH_ON_ADD?"checked":""}
          style="accent-color:var(--gold);width:14px;height:14px;cursor:pointer"/>
        <label for="cfg_radarr_search" class="form-label" style="margin:0;cursor:pointer">Search &amp; download on add</label>
      </div>
    </div>

    <div class="form-section">
      <div class="form-section-title">Automation</div>
      ${field("cfg_poll_interval","Library poll interval (min, 0 = disabled)", auto.LIBRARY_POLL_INTERVAL??30,"number")}
      <p style="font-size:.68rem;color:var(--text3);margin-top:-.25rem">Cineplete will auto-scan when your Plex library size changes.</p>
    </div>

    <div class="form-section" id="cache-section">
      <div class="form-section-title">TMDB Cache</div>
      <div id="cache-info" style="font-size:.75rem;color:var(--text3);margin-bottom:.75rem">Loading…</div>
      <div style="display:flex;gap:.5rem;flex-wrap:wrap">
        <button class="btn-sm" style="font-size:.72rem;padding:5px 14px;border-color:rgba(34,197,94,.3);color:var(--green)" onclick="backupCache()">💾 Backup</button>
        <button class="btn-sm" style="font-size:.72rem;padding:5px 14px;border-color:rgba(59,130,246,.3);color:var(--blue)" onclick="restoreCache()">↩ Restore</button>
        <button class="btn-sm btn-ignore" style="font-size:.72rem;padding:5px 14px" onclick="clearCache()">🗑 Clear</button>
      </div>
    </div>

    <button class="btn-primary" onclick="saveConfig()">Save Configuration</button>
    <div id="cfgStatus" style="font-size:.75rem;color:var(--text3);margin-top:.6rem;text-align:center"></div>
  </div>`
}

async function saveConfig(){
  const v  = id => document.getElementById(id)?.value?.trim()||""
  const vi = id => parseInt(v(id))||0
  const vf = id => parseFloat(v(id))||0

  const payload = {
    PLEX:{
      PLEX_URL:         v("cfg_plex_url"),
      PLEX_TOKEN:       v("cfg_plex_token"),
      LIBRARY_NAME:     v("cfg_library"),
      PLEX_PAGE_SIZE:   vi("cfg_plex_page_size"),
      SHORT_MOVIE_LIMIT:vi("cfg_short_limit"),
    },
    TMDB:{ TMDB_API_KEY: v("cfg_tmdb_key"), TMDB_WORKERS: vi("cfg_tmdb_workers") },
    CLASSICS:{
      CLASSICS_PAGES:      vi("cfg_classics_pages"),
      CLASSICS_MIN_VOTES:  vi("cfg_classics_votes"),
      CLASSICS_MIN_RATING: vf("cfg_classics_rating"),
      CLASSICS_MAX_RESULTS:vi("cfg_classics_max"),
    },
    ACTOR_HITS:{
      ACTOR_MIN_VOTES:             vi("cfg_actor_votes"),
      ACTOR_MAX_RESULTS_PER_ACTOR: vi("cfg_actor_max"),
    },
    RADARR:{
      RADARR_ENABLED:           document.getElementById("cfg_radarr_enabled")?.checked||false,
      RADARR_URL:               v("cfg_radarr_url"),
      RADARR_API_KEY:           v("cfg_radarr_key"),
      RADARR_ROOT_FOLDER_PATH:  v("cfg_radarr_root"),
      RADARR_QUALITY_PROFILE_ID:vi("cfg_radarr_quality"),
      RADARR_SEARCH_ON_ADD:     document.getElementById("cfg_radarr_search")?.checked||false,
    },
    AUTOMATION:{
      LIBRARY_POLL_INTERVAL: vi("cfg_poll_interval"),
    },
  }

  const res = await api("/api/config","POST",payload)
  const st  = document.getElementById("cfgStatus")
  if (res.ok){
    st.textContent = "✓ Saved"
    st.style.color = "var(--green)"
    toast("Configuration saved","success")
    if (res.configured){
      CONFIGURED = true
      CONFIG     = await api("/api/config")
      await loadResults()
    }
  } else {
    st.textContent = "✗ Error saving"
    st.style.color = "var(--red)"
    toast("Error saving config","error")
  }
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
   LOGS
============================================================ */

async function renderLogs(){
  const c = document.getElementById("content")
  c.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem">
      <p style="color:var(--text3);font-size:.78rem">Last 200 lines of <code style="color:var(--gold)">/data/cineplete.log</code></p>
      <button onclick="renderLogs()" style="font-size:.65rem;padding:3px 10px;border-radius:5px;border:1px solid var(--border2);background:var(--bg3);color:var(--text2);cursor:pointer;font-family:'DM Mono',monospace">↻ Refresh</button>
    </div>
    <div id="log-box" style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:1rem;font-family:'DM Mono',monospace;font-size:.72rem;line-height:1.7;overflow-x:auto;max-height:75vh;overflow-y:auto">
      <span style="color:var(--text3)">Loading...</span>
    </div>`

  try {
    const res  = await fetch("/api/logs?lines=200")
    const data = await res.json()
    const box  = document.getElementById("log-box")

    box.innerHTML = data.lines.map(line => {
      let color = "var(--text2)"
      if (line.includes("[ERROR   ]"))   color = "var(--red)"
      else if (line.includes("[WARNING ]")) color = "var(--amber)"
      else if (line.includes("[DEBUG   ]")) color = "var(--text3)"
      else if (line.includes("[INFO    ]")) color = "var(--text)"
      return `<div style="color:${color};white-space:pre-wrap;word-break:break-all">${escHtml(line)}</div>`
    }).join("")

    // Auto-scroll to bottom
    box.scrollTop = box.scrollHeight
  } catch(e) {
    document.getElementById("log-box").innerHTML =
      `<span style="color:var(--red)">Failed to fetch logs: ${e.message}</span>`
  }
}

function escHtml(str){
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
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

  // Display real version from server
  try {
    const v = await api("/api/version")
    document.querySelector(".version").textContent = `${v.version} · Cineplete`
  } catch(e) {}

  if (CONFIGURED) await loadResults()
  else { setStatus("Setup required"); render() }
}

document.getElementById("scanBtn").addEventListener("click", rescan)
boot()