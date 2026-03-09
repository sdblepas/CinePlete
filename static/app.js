let DATA = null
let CONFIG = null
let CONFIGURED = false
let ACTIVE_TAB = "dashboard"

const statusEl = () => document.getElementById("status")
const topFilters = () => document.getElementById("topFilters")

/* -------------------------------------------------- */
/* helpers */
/* -------------------------------------------------- */

function yearBucket(y){
  const year = parseInt(y || "0",10)
  if(!year) return ""
  if(year >= 2020) return "2020s"
  if(year >= 2010) return "2010s"
  if(year >= 2000) return "2000s"
  if(year >= 1990) return "1990s"
  return "older"
}

function pill(text){
  return `<span class="text-xs px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-200">${text}</span>`
}

function scorePill(label,value){
  return `
  <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
    <div class="text-sm text-zinc-400">${label}</div>
    <div class="text-2xl font-semibold">${value}%</div>
  </div>`
}

/* -------------------------------------------------- */
/* API */
/* -------------------------------------------------- */

async function api(path,method="GET",body=null){
  const opts={method,headers:{}}
  if(body){
    opts.headers["Content-Type"]="application/json"
    opts.body=JSON.stringify(body)
  }
  const r=await fetch(path,opts)
  return await r.json()
}

/* -------------------------------------------------- */
/* data loading */
/* -------------------------------------------------- */

async function loadConfig(){
  CONFIG=await api("/api/config")
}

async function loadStatus(){
  const s=await api("/api/config/status")
  CONFIGURED=!!s.configured
}

async function loadResults(){
  statusEl().textContent="Loading…"
  DATA=await api("/api/results")
  statusEl().textContent=`Loaded • ${DATA.generated_at || ""}`
  render()
}

async function rescan(){
  if(!CONFIGURED){
    alert("Complete setup first.")
    return
  }
  statusEl().textContent="Scanning…"
  DATA=await api("/api/scan","POST")
  statusEl().textContent=`Rescanned • ${DATA.generated_at}`
  render()
}

/* -------------------------------------------------- */
/* cards */
/* -------------------------------------------------- */

function movieCard(m){
  const poster=m.poster
    ? `<img src="${m.poster}" class="w-24 h-36 object-cover rounded bg-zinc-800"/>`
    : `<div class="w-24 h-36 rounded bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">No poster</div>`

  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button onclick="addToRadarr(${m.tmdb},'${(m.title||'').replace(/'/g,"\\'")}',this)"
         class="text-xs px-2 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white">+ Radarr</button>`
    : ""

  const wishlistBtn = m.wishlist
    ? `<button onclick="removeWishlist(${m.tmdb},this)"
         class="text-xs px-2 py-1 rounded bg-yellow-700 hover:bg-yellow-600 text-white">★ Wishlisted</button>`
    : `<button onclick="addWishlist(${m.tmdb},this)"
         class="text-xs px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-white">☆ Wishlist</button>`

  return `
  <div class="flex gap-3 bg-zinc-900 border border-zinc-800 rounded p-3">
    ${poster}
    <div class="flex-1">
      <div class="font-semibold">
        ${m.title || "Untitled"}
        ${m.year ? `<span class="text-zinc-400 font-normal">(${m.year})</span>`:""}
      </div>
      <div class="text-xs text-zinc-400 mt-1 flex flex-wrap gap-2">
        ${m.tmdb ? pill(`tmdb:${m.tmdb}`):""}
        ${pill(`pop ${Math.round(m.popularity||0)}`)}
        ${pill(`⭐ ${m.rating||0}`)}
        ${pill(`votes ${m.votes||0}`)}
      </div>
      <div class="flex gap-2 mt-2">
        ${wishlistBtn}
        ${radarrBtn}
      </div>
    </div>
  </div>`
}

/* -------------------------------------------------- */
/* wishlist / radarr actions */
/* -------------------------------------------------- */

async function addWishlist(tmdb, btn){
  await api("/api/wishlist/add","POST",{tmdb})
  btn.textContent="★ Wishlisted"
  btn.className="text-xs px-2 py-1 rounded bg-yellow-700 hover:bg-yellow-600 text-white"
  btn.onclick = () => removeWishlist(tmdb, btn)
}

async function removeWishlist(tmdb, btn){
  await api("/api/wishlist/remove","POST",{tmdb})
  btn.textContent="☆ Wishlist"
  btn.className="text-xs px-2 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-white"
  btn.onclick = () => addWishlist(tmdb, btn)
}

async function addToRadarr(tmdb, title, btn){
  btn.disabled = true
  btn.textContent = "Adding…"
  const res = await api("/api/radarr/add","POST",{tmdb, title})
  if(res.ok){
    btn.textContent = "✓ Added"
    btn.className = "text-xs px-2 py-1 rounded bg-zinc-600 text-white cursor-default"
  } else {
    btn.textContent = "✗ Error"
    btn.disabled = false
  }
}

/* -------------------------------------------------- */
/* dashboard */
/* -------------------------------------------------- */

function renderDashboard(){
  const c=document.getElementById("content")
  const s=DATA.scores || {}
  const p=DATA.plex || {}

  c.innerHTML=`
  <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
    ${scorePill("Franchise completion",s.franchise_completion_pct ?? 0)}
    ${scorePill("Directors score",s.directors_proxy_pct ?? 0)}
    ${scorePill("Classics coverage",s.classics_proxy_pct ?? 0)}
    ${scorePill("Global cinema score",s.global_cinema_score ?? 0)}
  </div>

  <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
    <div class="font-semibold mb-2">Plex stats</div>
    <div class="text-sm text-zinc-300 space-y-1">
      <div>Scanned items: <b>${p.scanned_items ?? 0}</b></div>
      <div>Indexed TMDB: <b>${p.indexed_tmdb ?? 0}</b></div>
      <div>Shorts skipped: <b>${p.skipped_short ?? 0}</b></div>
      <div>No TMDB GUID: <b>${p.no_tmdb_guid ?? 0}</b></div>
    </div>
  </div>`
}

/* -------------------------------------------------- */
/* franchises */
/* -------------------------------------------------- */

function renderFranchises(){
  const c=document.getElementById("content")
  const list=DATA.franchises || []

  let html=""
  list.forEach(f=>{
    if(!f.missing || !f.missing.length) return
    html+=`
    <div class="mb-6">
      <div class="flex justify-between items-center mb-2">
        <div class="font-semibold">${f.name} (${f.have}/${f.total})</div>
        <button onclick="ignoreFranchise('${f.name.replace(/'/g,"\\'")}',this)"
          class="text-xs px-2 py-1 rounded bg-zinc-700 hover:bg-red-700 text-zinc-300">Ignore</button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        ${f.missing.map(movieCard).join("")}
      </div>
    </div>`
  })

  c.innerHTML = html || `<div class="text-zinc-400">No missing franchise movies 🎉</div>`
}

async function ignoreFranchise(name, btn){
  await api("/api/ignore","POST",{kind:"franchise", value:name})
  btn.closest(".mb-6").remove()
}

/* -------------------------------------------------- */
/* directors */
/* -------------------------------------------------- */

function renderDirectors(){
  const c=document.getElementById("content")
  const list=DATA.directors || []

  if(!list.length){
    c.innerHTML=`<div class="text-zinc-400">No missing director films found.</div>`
    return
  }

  let html=""
  list.forEach(d=>{
    if(!d.missing || !d.missing.length) return
    html+=`
    <div class="mb-6">
      <div class="flex justify-between items-center mb-2">
        <div class="font-semibold">🎬 ${d.name}</div>
        <button onclick="ignoreDirector('${d.name.replace(/'/g,"\\'")}',this)"
          class="text-xs px-2 py-1 rounded bg-zinc-700 hover:bg-red-700 text-zinc-300">Ignore</button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        ${d.missing.map(movieCard).join("")}
      </div>
    </div>`
  })

  c.innerHTML = html || `<div class="text-zinc-400">No missing director films found.</div>`
}

async function ignoreDirector(name, btn){
  await api("/api/ignore","POST",{kind:"director", value:name})
  btn.closest(".mb-6").remove()
}

/* -------------------------------------------------- */
/* actors */
/* -------------------------------------------------- */

function renderActors(){
  const c=document.getElementById("content")
  const list=DATA.actors || []

  if(!list.length){
    c.innerHTML=`<div class="text-zinc-400">No actor suggestions found.</div>`
    return
  }

  let html=""
  list.forEach(a=>{
    if(!a.missing || !a.missing.length) return
    html+=`
    <div class="mb-6">
      <div class="flex justify-between items-center mb-2">
        <div class="font-semibold">🎭 ${a.name}</div>
        <button onclick="ignoreActor('${a.name.replace(/'/g,"\\'")}',this)"
          class="text-xs px-2 py-1 rounded bg-zinc-700 hover:bg-red-700 text-zinc-300">Ignore</button>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        ${a.missing.map(movieCard).join("")}
      </div>
    </div>`
  })

  c.innerHTML = html || `<div class="text-zinc-400">No actor suggestions found.</div>`
}

async function ignoreActor(name, btn){
  await api("/api/ignore","POST",{kind:"actor", value:name})
  btn.closest(".mb-6").remove()
}

/* -------------------------------------------------- */
/* classics */
/* -------------------------------------------------- */

function renderClassics(){
  const c=document.getElementById("content")
  const list=DATA.classics || []

  if(!list.length){
    c.innerHTML=`<div class="text-zinc-400">No missing classics found 🎉</div>`
    return
  }

  c.innerHTML=`
  <div class="mb-3 text-zinc-400 text-sm">${list.length} classic films missing from your library</div>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
    ${list.map(movieCard).join("")}
  </div>`
}

/* -------------------------------------------------- */
/* suggestions */
/* -------------------------------------------------- */

function renderSuggestions(){
  const c=document.getElementById("content")
  const list=DATA.suggestions || []

  if(!list.length){
    c.innerHTML=`<div class="text-zinc-400">No TMDB suggestions available.</div>`
    return
  }

  c.innerHTML=`
  <div class="mb-3 text-zinc-400 text-sm">${list.length} suggestions from TMDB Top Rated</div>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
    ${list.map(movieCard).join("")}
  </div>`
}

/* -------------------------------------------------- */
/* no tmdb guid */
/* -------------------------------------------------- */

function renderNoTmdb(){
  const c=document.getElementById("content")
  const list=DATA.no_tmdb_guid || []

  if(!list.length){
    c.innerHTML=`<div class="text-zinc-400">All movies have a TMDB GUID 🎉</div>`
    return
  }

  c.innerHTML=`
  <div class="mb-3 text-zinc-400 text-sm">${list.length} movies without a TMDB GUID — fix via Plex → Fix Match → TheMovieDB</div>
  <div class="space-y-2">
    ${list.map(m=>`
    <div class="bg-zinc-900 border border-zinc-800 rounded p-3">
      <span class="font-medium">${m.title || "Unknown"}</span>
      ${m.year ? `<span class="text-zinc-400 ml-2">(${m.year})</span>` : ""}
    </div>`).join("")}
  </div>`
}

/* -------------------------------------------------- */
/* tmdb no match */
/* -------------------------------------------------- */

function renderNoMatch(){
  const c=document.getElementById("content")
  const list=DATA.tmdb_not_found || []

  if(!list.length){
    c.innerHTML=`<div class="text-zinc-400">All TMDB matches resolved 🎉</div>`
    return
  }

  c.innerHTML=`
  <div class="mb-3 text-zinc-400 text-sm">${list.length} movies with invalid TMDB metadata — refresh metadata or fix match in Plex</div>
  <div class="space-y-2">
    ${list.map(m=>`
    <div class="bg-zinc-900 border border-zinc-800 rounded p-3">
      ${pill(`tmdb:${m.tmdb}`)}
    </div>`).join("")}
  </div>`
}

/* -------------------------------------------------- */
/* wishlist */
/* -------------------------------------------------- */

function renderWishlist(){
  const c=document.getElementById("content")
  const list=DATA.wishlist || []

  c.innerHTML=(list.length
    ? `<div class="grid grid-cols-1 md:grid-cols-2 gap-3">${list.map(movieCard).join("")}</div>`
    : `<div class="text-zinc-400">Wishlist empty</div>`)
}

/* -------------------------------------------------- */
/* config */
/* -------------------------------------------------- */

function renderConfig(){
  const c=document.getElementById("content")
  const cfg=CONFIG || {}
  const plex=cfg.PLEX || {}
  const tmdb=cfg.TMDB || {}
  const radarr=cfg.RADARR || {}
  const classics=cfg.CLASSICS || {}
  const actor=cfg.ACTOR_HITS || {}

  c.innerHTML=`
  <div class="max-w-xl space-y-6">

    <div class="bg-zinc-900 border border-zinc-800 rounded p-4 space-y-3">
      <div class="font-semibold text-zinc-200">Plex</div>
      <label class="block text-sm text-zinc-400">Plex URL
        <input id="cfg_plex_url" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${plex.PLEX_URL||''}"/>
      </label>
      <label class="block text-sm text-zinc-400">Plex Token
        <input id="cfg_plex_token" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${plex.PLEX_TOKEN||''}"/>
      </label>
      <label class="block text-sm text-zinc-400">Library Name
        <input id="cfg_library" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${plex.LIBRARY_NAME||''}"/>
      </label>
    </div>

    <div class="bg-zinc-900 border border-zinc-800 rounded p-4 space-y-3">
      <div class="font-semibold text-zinc-200">TMDB</div>
      <label class="block text-sm text-zinc-400">TMDB API Key
        <input id="cfg_tmdb_key" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${tmdb.TMDB_API_KEY||''}"/>
      </label>
    </div>

    <div class="bg-zinc-900 border border-zinc-800 rounded p-4 space-y-3">
      <div class="font-semibold text-zinc-200">Radarr <span class="text-xs font-normal text-zinc-400">(optional)</span></div>
      <label class="flex items-center gap-2 text-sm text-zinc-400">
        <input type="checkbox" id="cfg_radarr_enabled" ${radarr.RADARR_ENABLED ? "checked":""}/> Enabled
      </label>
      <label class="block text-sm text-zinc-400">Radarr URL
        <input id="cfg_radarr_url" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${radarr.RADARR_URL||''}"/>
      </label>
      <label class="block text-sm text-zinc-400">Radarr API Key
        <input id="cfg_radarr_key" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${radarr.RADARR_API_KEY||''}"/>
      </label>
      <label class="block text-sm text-zinc-400">Root Folder Path
        <input id="cfg_radarr_root" class="mt-1 w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-100"
          value="${radarr.RADARR_ROOT_FOLDER_PATH||''}"/>
      </label>
    </div>

    <button onclick="saveConfig()"
      class="w-full px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-black font-semibold">
      Save Configuration
    </button>
    <div id="cfgStatus" class="text-sm text-zinc-400"></div>
  </div>`
}

async function saveConfig(){
  const payload={
    PLEX:{
      PLEX_URL: document.getElementById("cfg_plex_url").value.trim(),
      PLEX_TOKEN: document.getElementById("cfg_plex_token").value.trim(),
      LIBRARY_NAME: document.getElementById("cfg_library").value.trim(),
    },
    TMDB:{
      TMDB_API_KEY: document.getElementById("cfg_tmdb_key").value.trim(),
    },
    RADARR:{
      RADARR_ENABLED: document.getElementById("cfg_radarr_enabled").checked,
      RADARR_URL: document.getElementById("cfg_radarr_url").value.trim(),
      RADARR_API_KEY: document.getElementById("cfg_radarr_key").value.trim(),
      RADARR_ROOT_FOLDER_PATH: document.getElementById("cfg_radarr_root").value.trim(),
    }
  }

  const res=await api("/api/config","POST",payload)
  document.getElementById("cfgStatus").textContent = res.ok ? "✓ Saved" : "✗ Error saving"

  if(res.configured){
    CONFIGURED=true
    await loadResults()
  }
}

/* -------------------------------------------------- */
/* search / filter / sort */
/* -------------------------------------------------- */

function getFilters(){
  return {
    search: (document.getElementById("search")?.value||"").toLowerCase(),
    year: document.getElementById("yearFilter")?.value||"",
    sort: document.getElementById("sort")?.value||"popularity"
  }
}

function applyFilters(list){
  const {search,year,sort}=getFilters()

  let out=list.filter(m=>{
    if(search && !(m.title||"").toLowerCase().includes(search)) return false
    if(year && yearBucket(m.year)!==year) return false
    return true
  })

  out.sort((a,b)=>{
    if(sort==="title") return (a.title||"").localeCompare(b.title||"")
    if(sort==="year") return parseInt(b.year||0)-parseInt(a.year||0)
    if(sort==="rating") return (b.rating||0)-(a.rating||0)
    if(sort==="votes") return (b.votes||0)-(a.votes||0)
    return (b.popularity||0)-(a.popularity||0)
  })

  return out
}

/* -------------------------------------------------- */
/* render */
/* -------------------------------------------------- */

function render(){
  if(!CONFIGURED){
    topFilters().style.display="none"
    ACTIVE_TAB="config"
    return renderConfig()
  }

  topFilters().style.display="flex"

  if(ACTIVE_TAB==="dashboard")    return renderDashboard()
  if(ACTIVE_TAB==="franchises")   return renderFranchises()
  if(ACTIVE_TAB==="directors")    return renderDirectors()
  if(ACTIVE_TAB==="actors")       return renderActors()
  if(ACTIVE_TAB==="classics")     return renderClassics()
  if(ACTIVE_TAB==="suggestions")  return renderSuggestions()
  if(ACTIVE_TAB==="notmdb")       return renderNoTmdb()
  if(ACTIVE_TAB==="nomatch")      return renderNoMatch()
  if(ACTIVE_TAB==="wishlist")     return renderWishlist()
  if(ACTIVE_TAB==="config")       return renderConfig()
}

/* -------------------------------------------------- */
/* navigation */
/* -------------------------------------------------- */

function setActiveTab(tab){
  ACTIVE_TAB=tab
  document.querySelectorAll(".nav").forEach(b=>b.classList.remove("bg-zinc-800"))
  document.querySelector(`.nav[data-tab="${tab}"]`)?.classList.add("bg-zinc-800")
  render()
}

document.addEventListener("click",e=>{
  const btn=e.target.closest(".nav")
  if(!btn) return
  setActiveTab(btn.dataset.tab)
})

/* live filter/sort re-render */
document.addEventListener("input",e=>{
  if(["search","yearFilter","sort"].includes(e.target.id)) render()
})
document.addEventListener("change",e=>{
  if(e.target.id==="yearFilter"||e.target.id==="sort") render()
})

/* -------------------------------------------------- */
/* boot */
/* -------------------------------------------------- */

async function boot(){
  await loadConfig()
  await loadStatus()

  if(CONFIGURED)
    await loadResults()
  else{
    statusEl().textContent="Setup required"
    render()
  }
}

document.getElementById("scanBtn")?.addEventListener("click",rescan)

boot()