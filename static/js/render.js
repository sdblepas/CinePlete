/* ============================================================
   render.js — all tab renderers, movie card, charts, actions
============================================================ */

/* ── Chart registry ──────────────────────────────────────── */

const _charts = {}
function destroyChart(id){ if(_charts[id]){_charts[id].destroy();delete _charts[id]} }
function mkChart(id,cfg){ destroyChart(id); _charts[id]=new Chart(document.getElementById(id),cfg); return _charts[id] }

/* ── Batch selection state ───────────────────────────────── */

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
  const bar = document.getElementById("batchBar")
  const cnt = document.getElementById("batchCount")
  if (!bar) return
  const n = _selected.size
  if (n > 0) {
    cnt.textContent = `${n} selected`
    bar.classList.add("visible")
  } else {
    bar.classList.remove("visible")
  }
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
  for (const [tmdb] of _selected) {
    await api("/api/wishlist/add", "POST", { tmdb })
  }
  toast(`${_selected.size} movies added to Wishlist`, "gold")
  clearSelection()
  if (DATA) {
    const wIds = new Set((DATA.wishlist || []).map(w => w.tmdb))
    _selected.forEach((_, t) => wIds.add(t))
  }
}

/* ── Poster card (new visual layout) ────────────────────── */

function posterCard(m, extraTag = "") {
  const tmdb     = m.tmdb
  const safeName = (m.title || "").replace(/'/g, "\\'").replace(/"/g, "&quot;")

  const radarrBtn = CONFIG?.RADARR?.RADARR_ENABLED
    ? `<button class="btn-sm btn-radarr" onclick="event.stopPropagation();addToRadarr(${tmdb},'${safeName}',this)">+ Radarr</button>`
    : ""

  const wBtn = m.wishlist
    ? `<button class="btn-sm btn-wishlisted" onclick="event.stopPropagation();removeWishlist(${tmdb},this)">★</button>`
    : `<button class="btn-sm btn-wishlist"   onclick="event.stopPropagation();addWishlist(${tmdb},this)">☆</button>`

  const rating = parseFloat(m.rating || 0).toFixed(1)

  const imgHtml = m.poster
    ? `<img class="pc-img" src="${m.poster}" loading="lazy" alt=""/>`
    : `<div class="pc-no-img"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 2v20M17 2v20M2 12h20"/></svg><span>No Image</span></div>`

  const mSafe = JSON.stringify({ tmdb: m.tmdb, title: m.title, year: m.year, poster: m.poster, wishlist: m.wishlist })
    .replace(/'/g, "\\'")

  return `
  <div class="pc" onclick="openMovieModal(${tmdb},${mSafe.replace(/"/g,'&quot;')})">
    <input type="checkbox" class="pc-check"
      onclick="event.stopPropagation();toggleSelect(${tmdb},${mSafe.replace(/"/g,'&quot;')},this)"
      title="Select"/>
    ${imgHtml}
    <div class="pc-info">
      <div class="pc-title" title="${escHtml(m.title||"")}">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-meta">
        <span class="pc-rating">⭐ ${rating}</span>
        ${m.year ? `<span>${m.year}</span>` : ""}
        ${extraTag}
      </div>
    </div>
    <div class="pc-overlay">
      <div class="pc-overlay-title">${escHtml(m.title||"Untitled")}</div>
      <div class="pc-overlay-actions">${wBtn}${radarrBtn}</div>
    </div>
  </div>`
}

/* ── Legacy horizontal card (kept for backward compat) ──── */

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
  <div class="movie-card" onclick="openMovieModal(${m.tmdb},${JSON.stringify({tmdb:m.tmdb,title:m.title,year:m.year,poster:m.poster,wishlist:m.wishlist}).replace(/"/g,'&quot;')})">
    <div class="movie-card-inner">
      ${poster}
      <div class="movie-body">
        <div class="movie-title">${escHtml(m.title||"Untitled")} <span class="movie-year">${m.year?`(${m.year})`:""}</span></div>
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
  const p = DATA.media_server || DATA.plex || {}

  const ignoredFranchises = new Set(DATA._ignored_franchises||[])
  const activeFranchises  = (DATA.franchises||[]).filter(f=>!ignoredFranchises.has(f.name))
  let fComplete=0,fOne=0,fMore=0
  activeFranchises.forEach(f=>{
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

  // Aggregate all unique missing movies for analysis
  const seenMissing = new Set()
  const allMissing  = []
  const pushUniq    = m=>{ if(m.tmdb&&!seenMissing.has(m.tmdb)){ seenMissing.add(m.tmdb); allMissing.push(m) } }
  activeFranchises.forEach(f=>(f.missing||[]).forEach(pushUniq))
  ;(DATA.directors||[]).forEach(d=>(d.missing||[]).forEach(pushUniq))
  ;(DATA.actors   ||[]).forEach(a=>(a.missing||[]).forEach(pushUniq))
  ;(DATA.classics ||[]).forEach(pushUniq)

  // Missing by decade
  const decades={"Pre-1970":0,"1970s":0,"1980s":0,"1990s":0,"2000s":0,"2010s":0,"2020s":0}
  allMissing.forEach(m=>{
    const yr=parseInt(m.year||0)
    if(!yr) return
    if(yr>=2020)      decades["2020s"]++
    else if(yr>=2010) decades["2010s"]++
    else if(yr>=2000) decades["2000s"]++
    else if(yr>=1990) decades["1990s"]++
    else if(yr>=1980) decades["1980s"]++
    else if(yr>=1970) decades["1970s"]++
    else              decades["Pre-1970"]++
  })

  // Genre gap (top 8 genres in missing movies)
  const genreCounts={}
  allMissing.forEach(m=>(m.genre_ids||[]).forEach(gid=>{
    if(GENRE_MAP[gid]) genreCounts[gid]=(genreCounts[gid]||0)+1
  }))
  const topGenres=Object.entries(genreCounts)
    .sort((a,b)=>b[1]-a[1]).slice(0,8)
    .map(([id,n])=>({name:GENRE_MAP[id],count:n}))

  // Top incomplete franchises (by absolute missing count)
  const topIncomplete=activeFranchises
    .filter(f=>(f.missing||[]).length>0)
    .sort((a,b)=>(b.missing||[]).length-(a.missing||[]).length)
    .slice(0,7)

  const totalMissing = allMissing.length

  // helpers
  const kpi=(val,label,color,tab="",sub="")=>{
    const click=tab?`onclick="setActiveTab('${tab}')" style="cursor:pointer"`:"style=\"\""
    return `<div class="kpi-tile" ${click}>
      <div class="kpi-value" style="color:${color}">${val}</div>
      <div class="kpi-label">${label}</div>
      ${sub?`<div class="kpi-sub">${sub}</div>`:""}
    </div>`
  }

  const leg=(col,label,val,tab="")=>{
    const click=tab?`onclick="setActiveTab('${tab}')" style="cursor:pointer"`:"style=\"\""
    return `<div class="legend-row" ${click}>
      <span class="legend-dot" style="background:${col}"></span>
      <span class="legend-label">${label}</span>
      <b class="legend-val">${val}</b>
    </div>`
  }

  const srow=(label,val,color="")=>`
  <div class="stat-row">
    <span class="stat-label">${label}</span>
    <span class="stat-val"${color?` style="color:${color}"`:""}>${val}</span>
  </div>`

  c.innerHTML=`
  <!-- KPI Strip -->
  <div class="kpi-strip">
    ${kpi(Math.round(s.franchise_completion_pct??0)+"%","Franchise","#F5C518","franchises",`${fComplete} complete · ${fOne+fMore} gaps`)}
    ${kpi(Math.round(s.directors_proxy_pct??0)+"%","Directors","#3b82f6","directors",`${(DATA.directors||[]).length} tracked`)}
    ${kpi(Math.round(s.classics_proxy_pct??0)+"%","Classics","#a855f7","classics",`${classicsHave}/${classicsTotal} in library`)}
    ${kpi(Math.round(s.global_cinema_score??0)+"%","Global Score","#22c55e","","composite")}
    ${kpi(totalMissing,"Total Missing","var(--text)","franchises","unique films")}
    ${kpi((DATA.wishlist||[]).length,"Wishlist","var(--gold)","wishlist","saved for later")}
  </div>

  <!-- Doughnuts row -->
  <div class="db-row" style="margin-bottom:.75rem">
    <div class="card card-compact">
      <div class="card-title">Franchise Status</div>
      <div class="chart-duo">
        <canvas id="cFranchise" width="110" height="110" style="flex-shrink:0"></canvas>
        <div class="legend-stack">
          ${leg("#22c55e","Complete",fComplete,"franchises")}
          ${leg("#F5C518","Missing 1",fOne,"franchises")}
          ${leg("#ef4444","Missing 2+",fMore,"franchises")}
        </div>
      </div>
    </div>
    <div class="card card-compact">
      <div class="card-title">Classics Coverage</div>
      <div class="chart-duo">
        <canvas id="cClassics" width="110" height="110" style="flex-shrink:0"></canvas>
        <div class="legend-stack">
          ${leg("#a855f7","In Library",classicsHave,"classics")}
          ${leg("#27272a","Missing",classicsMiss,"classics")}
        </div>
      </div>
    </div>
    <div class="card card-compact">
      <div class="card-title">Metadata Health</div>
      <div class="chart-duo">
        <canvas id="cMeta" width="110" height="110" style="flex-shrink:0"></canvas>
        <div class="legend-stack">
          ${leg("#22c55e","Valid TMDB",okMovies)}
          ${leg("#F5C518","No GUID",noGuid,"notmdb")}
          ${leg("#ef4444","No Match",noMatch,"nomatch")}
        </div>
      </div>
    </div>
  </div>

  <!-- Analysis row: decade + genre gap -->
  <div class="db-row db-row-2" style="margin-bottom:.75rem">
    <div class="card card-compact">
      <div class="card-title">Missing by Decade</div>
      <canvas id="cDecade" height="150"></canvas>
    </div>
    <div class="card card-compact">
      <div class="card-title">Genre Gap — Top Missing</div>
      <canvas id="cGenre" height="150"></canvas>
    </div>
  </div>

  <!-- Bottom row: actors + franchise bars + library stats -->
  <div class="db-row">
    <div class="card card-compact">
      <div class="card-title">Top Actors in Library</div>
      <canvas id="cActors" height="200"></canvas>
    </div>
    <div class="card card-compact">
      <div class="card-title">Most Incomplete Franchises</div>
      <div class="franchise-bars">
        ${topIncomplete.map(f=>{
          const pct=f.total?Math.round((f.have/f.total)*100):100
          return `<div class="fbr" onclick="setActiveTab('franchises')" style="cursor:pointer">
            <div class="fbr-header">
              <span class="fbr-name" title="${escHtml(f.name)}">${escHtml(f.name)}</span>
              <span class="fbr-count">${f.have}/${f.total}</span>
            </div>
            <div class="fbr-track"><div class="fbr-fill" style="width:0%" data-pct="${pct}"></div></div>
          </div>`
        }).join("")||`<div style="color:var(--text3);font-size:.8rem;padding:.5rem 0">All franchises complete 🎉</div>`}
      </div>
    </div>
    <div class="card card-compact">
      <div class="card-title">Library Stats</div>
      <div>
        ${srow("Scanned",     p.scanned_items??0)}
        ${srow("Indexed",     p.indexed_tmdb ??0)}
        ${srow("Shorts skip", p.skipped_short??0)}
        ${srow("No GUID",     noGuid,  noGuid ?"var(--amber)":"")}
        ${srow("No match",    noMatch, noMatch?"var(--red)":"")}
        ${srow("Franchises",  activeFranchises.length)}
        ${srow("Directors",   (DATA.directors||[]).length)}
        ${srow("Suggestions", (DATA.suggestions||[]).length)}
      </div>
      <div class="card-title" style="margin-top:1rem">Director Coverage</div>
      <canvas id="cDirs" height="75"></canvas>
    </div>
  </div>`

  requestAnimationFrame(()=>{
    // Animate franchise progress bars
    document.querySelectorAll(".fbr-fill").forEach(el=>{
      setTimeout(()=>{ el.style.width=el.dataset.pct+"%" },80)
    })

    Chart.defaults.color       = "#606070"
    Chart.defaults.font.family = "'DM Mono',monospace"
    Chart.defaults.font.size   = 11

    const doughnut=(labels,data,colors,onClick)=>({
      type:"doughnut",
      data:{labels,datasets:[{data,backgroundColor:colors,borderColor:"#141416",borderWidth:3,hoverOffset:6}]},
      options:{
        cutout:"65%", animation:{duration:700},
        plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>`${ctx.label}: ${ctx.parsed}`}}},
        onClick:(e,els)=>{ if(els.length&&onClick) onClick(els[0].index) }
      }
    })

    mkChart("cFranchise",doughnut(
      ["Complete","Missing 1","Missing 2+"],[fComplete,fOne,fMore],
      ["#22c55e","#F5C518","#ef4444"],i=>{ if(i>0) setActiveTab("franchises") }
    ))
    mkChart("cClassics",doughnut(
      ["In Library","Missing"],[classicsHave,classicsMiss],
      ["#a855f7","#27272a"],i=>{ if(i===1) setActiveTab("classics") }
    ))
    mkChart("cMeta",doughnut(
      ["Valid TMDB","No GUID","No Match"],[okMovies,noGuid,noMatch],
      ["#22c55e","#F5C518","#ef4444"],i=>{ if(i===1) setActiveTab("notmdb"); else if(i===2) setActiveTab("nomatch") }
    ))

    // Missing by decade
    const dLabels=Object.keys(decades).filter(k=>decades[k]>0)
    mkChart("cDecade",{
      type:"bar",
      data:{labels:dLabels,datasets:[{data:dLabels.map(k=>decades[k]),
        backgroundColor:dLabels.map((_,i)=>`hsl(${210+i*18},65%,${48+i*3}%)`),
        borderRadius:5,borderSkipped:false}]},
      options:{
        animation:{duration:700},
        scales:{
          x:{grid:{display:false},ticks:{color:"#9090a0"}},
          y:{grid:{color:"#1a1a1e"},ticks:{color:"#606070",precision:0}}
        },
        plugins:{legend:{display:false}}
      }
    })

    // Genre gap
    mkChart("cGenre",{
      type:"bar",
      data:{labels:topGenres.map(g=>g.name),datasets:[{data:topGenres.map(g=>g.count),
        backgroundColor:topGenres.map((_,i)=>`hsl(${280+i*14},60%,${62-i*3}%)`),
        borderRadius:5,borderSkipped:false}]},
      options:{
        indexAxis:"y", animation:{duration:700},
        scales:{
          x:{grid:{color:"#1a1a1e"},ticks:{color:"#606070",precision:0}},
          y:{grid:{display:false},ticks:{color:"#9090a0"}}
        },
        plugins:{legend:{display:false}}
      }
    })

    // Top actors
    mkChart("cActors",{
      type:"bar",
      data:{labels:topActors.map(a=>a.name),datasets:[{data:topActors.map(a=>a.count),
        backgroundColor:topActors.map((_,i)=>`hsl(${42+i*3},90%,${58-i*2}%)`),
        borderRadius:4,borderSkipped:false}]},
      options:{
        indexAxis:"y", animation:{duration:700},
        scales:{
          x:{grid:{color:"#1a1a1e"},ticks:{color:"#606070"}},
          y:{grid:{display:false},ticks:{color:"#9090a0"}}
        },
        plugins:{legend:{display:false}}
      }
    })

    // Directors spread
    mkChart("cDirs",{
      type:"bar",
      data:{labels:Object.keys(dBuckets),datasets:[{data:Object.values(dBuckets),
        backgroundColor:["#2a2a30","#3b82f6","#F5C518","#ef4444","#7f1d1d"],
        borderRadius:4,borderSkipped:false}]},
      options:{
        animation:{duration:700},
        scales:{
          x:{grid:{display:false},ticks:{color:"#9090a0"}},
          y:{grid:{color:"#1a1a1e"},ticks:{color:"#606070",precision:0}}
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
  const genreFilter = getGenreFilter()

  let html = ""

  groups.forEach(g => {
    const name = g[nameKey]||""
    if (groupFilter && name !== groupFilter) return

    let sorted = [...(g.missing||[])].sort((a,b)=>{
      if(sort==="title")  return (a.title||"").localeCompare(b.title||"")
      if(sort==="year")   return parseInt(b.year||0)-parseInt(a.year||0)
      if(sort==="rating") return (b.rating||0)-(a.rating||0)
      if(sort==="votes")  return (b.votes||0)-(a.votes||0)
      return (b.popularity||0)-(a.popularity||0)
    })

    if (genreFilter) {
      sorted = sorted.filter(m => (m.genre_ids||[]).includes(parseInt(genreFilter)))
    }

    if (!sorted.length) return

    html += `
    <div class="mb-group" style="margin-bottom:2rem">
      <div class="group-header">
        <div>
          <span class="group-name">${nameIcon} ${escHtml(name)}</span>
          ${g.have!==undefined
            ? `<span class="group-count">${g.have}/${g.total} in library</span>`
            : `<span class="group-count">${sorted.length} missing</span>`}
        </div>
        <button class="btn-sm btn-ignore"
          onclick="${ignoreHandler}('${name.replace(/'/g,"\\'")}',this)">Ignore</button>
      </div>
      <div class="grid-posters">${sorted.map(m=>posterCard(m)).join("")}</div>
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
  let list   = applyFilters(DATA.classics||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("No missing classics 🎉"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} classic films missing from your library</p>
    <div class="grid-posters">${list.map(m=>posterCard(m)).join("")}</div>`
}

/* ── Suggestions ─────────────────────────────────────────── */

function renderSuggestions(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.suggestions||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("No suggestions available"); return }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">${list.length} films recommended by your library</p>
    <div class="grid-posters">${list.map(m => posterCard(m, m.rec_score
      ? `<span style="color:var(--gold);font-size:.6rem">⚡${m.rec_score}</span>`
      : ""
    )).join("")}</div>`
}

/* ── Wishlist ────────────────────────────────────────────── */

function renderWishlist(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.wishlist||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("Wishlist is empty"); return }
  c.innerHTML = `<div class="grid-posters">${list.map(m=>posterCard(m)).join("")}</div>`
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
        <span class="meta-item-title">${escHtml(m.title||"Unknown")}</span>
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
        <span class="meta-item-title">${escHtml(m.title || "Unknown title")}</span>
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
    box.innerHTML = ""
    data.lines.forEach(line => {
      let color = "var(--text2)"
      if (line.includes("[ERROR   ]"))    color = "var(--red)"
      else if (line.includes("[WARNING ]")) color = "var(--amber)"
      else if (line.includes("[DEBUG   ]")) color = "var(--text3)"
      else if (line.includes("[INFO    ]")) color = "var(--text)"
      const div = document.createElement("div")
      div.style.cssText = `color:${color};white-space:pre-wrap;word-break:break-all`
      div.textContent = line
      box.appendChild(div)
    })
    box.scrollTop = box.scrollHeight
  } catch(e) {
    const box = document.getElementById("log-box")
    if (box){
      box.innerHTML = ""
      const span = document.createElement("span")
      span.style.color = "var(--red)"
      span.textContent = "Failed to fetch logs: " + e.message
      box.appendChild(span)
    }
  }
}

/* ── Export current tab ──────────────────────────────────── */

const EXPORT_TABS = new Set(["franchises","directors","actors","classics","suggestions","wishlist"])

function exportCurrent(format = "csv") {
  if (!EXPORT_TABS.has(ACTIVE_TAB)) return
  const url = `/api/export?format=${format}&tab=${ACTIVE_TAB}`
  const a   = document.createElement("a")
  a.href    = url
  a.download = `cineplete-${ACTIVE_TAB}.csv`
  a.click()
  toast(`Exporting ${ACTIVE_TAB} as ${format.toUpperCase()}`, "info")
}

function updateExportBtn() {
  const btn = document.getElementById("exportBtn")
  if (!btn) return
  btn.style.display = EXPORT_TABS.has(ACTIVE_TAB) ? "" : "none"
}
