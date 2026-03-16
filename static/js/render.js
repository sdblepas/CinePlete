/* ============================================================
   render.js — all tab renderers, movie card, charts, actions
============================================================ */

/* ── Chart registry ──────────────────────────────────────── */

const _charts = {}
function destroyChart(id){ if(_charts[id]){_charts[id].destroy();delete _charts[id]} }
function mkChart(id,cfg){ destroyChart(id); _charts[id]=new Chart(document.getElementById(id),cfg); return _charts[id] }

/* ── Movie card ──────────────────────────────────────────── */

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

/* ── Wishlist / Radarr actions ───────────────────────────── */

async function addWishlist(tmdb, btn){
  await api("/api/wishlist/add","POST",{tmdb})
  btn.className   = "btn-sm btn-wishlisted"
  btn.textContent = "★ Wishlisted"
  btn.onclick     = () => removeWishlist(tmdb,btn)
  toast("Added to Wishlist","gold")
}

async function removeWishlist(tmdb, btn){
  await api("/api/wishlist/remove","POST",{tmdb})
  btn.className   = "btn-sm btn-wishlist"
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

/* ── Empty state ─────────────────────────────────────────── */

function emptyStateHTML(msg){
  return `<div class="empty-state">
    <div class="empty-icon">🎬</div>
    <div class="empty-title">${msg}</div>
    <div class="empty-sub">Nothing to show here.</div>
  </div>`
}

/* ── Dashboard ───────────────────────────────────────────── */

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

  const leg = (col,label,val,tab="")=>{
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

/* ── Grouped list (franchises / directors / actors) ─────── */

function renderGroupedList({ groups, nameKey, nameIcon, ignoreHandler, emptyMsg }){
  const c           = document.getElementById("content")
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

/* ── Franchises ──────────────────────────────────────────── */

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

/* ── Directors ───────────────────────────────────────────── */

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

/* ── Actors ──────────────────────────────────────────────── */

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

/* ── Classics ────────────────────────────────────────────── */

function renderClassics(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.classics||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("No missing classics 🎉"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} classic films missing from your library</p>
    <div class="grid-2">${list.map(movieCard).join("")}</div>`
}

/* ── Suggestions ─────────────────────────────────────────── */

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

/* ── Wishlist ────────────────────────────────────────────── */

function renderWishlist(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.wishlist||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("Wishlist is empty"); return }
  c.innerHTML = `<div class="grid-2">${list.map(movieCard).join("")}</div>`
}

/* ── No TMDB GUID ────────────────────────────────────────── */

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

/* ── TMDB No Match ───────────────────────────────────────── */

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

/* ── Logs ────────────────────────────────────────────────── */

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
    // Build log lines safely using textContent to prevent XSS
    box.innerHTML = ""
    data.lines.forEach(line => {
      let color = "var(--text2)"
      if (line.includes("[ERROR   ]"))    color = "var(--red)"
      else if (line.includes("[WARNING ]")) color = "var(--amber)"
      else if (line.includes("[DEBUG   ]")) color = "var(--text3)"
      else if (line.includes("[INFO    ]")) color = "var(--text)"
      const div = document.createElement("div")
      div.style.cssText = `color:${color};white-space:pre-wrap;word-break:break-all`
      div.textContent = line   // textContent never parses HTML — safe against XSS
      box.appendChild(div)
    })
    box.scrollTop = box.scrollHeight
  } catch(e) {
    document.getElementById("log-box").innerHTML =
      `<span style="color:var(--red)">Failed to fetch logs: ${e.message}</span>`
  }
}