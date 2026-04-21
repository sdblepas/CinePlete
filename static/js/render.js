/* ============================================================
   render.js — tab renderers, pagination, charts, export
   Depends on: api.js, cards.js, mutations.js, filters.js
============================================================ */

/* ── Section status helpers (progressive scan) ───────────── */

function _sectionStatus(name) {
  return DATA?.sections?.[name] ?? "done"
}

function _renderSectionPending(label) {
  return `<div class="section-pending">
    <div class="skeleton-grid">
      ${Array(6).fill('<div class="skeleton-card"></div>').join("")}
    </div>
    <p class="section-pending-label">⏳ ${label} — waiting to start…</p>
  </div>`
}

function _renderSectionComputing(msg) {
  return `<div class="section-pending computing">
    <div class="skeleton-grid">
      ${Array(6).fill('<div class="skeleton-card"></div>').join("")}
    </div>
    <p class="section-pending-label">
      <span class="section-spinner">⟳</span> ${msg}
    </p>
  </div>`
}

/* ── Chart registry ──────────────────────────────────────── */

const _charts = {}
function destroyChart(id){ if(_charts[id]){_charts[id].destroy();delete _charts[id]} }
function mkChart(id,cfg){ destroyChart(id); _charts[id]=new Chart(document.getElementById(id),cfg); return _charts[id] }

let _dashRO = null   // ResizeObserver for dashboard charts

function _teardownDashRO(){
  if (_dashRO){ _dashRO.disconnect(); _dashRO = null }
}

/* ── Pagination state ────────────────────────────────────── */

const PAGE_SIZE = 24
const _tabPage  = {}   // tab → current page count (starts at 1)

function _getPage(tab) { return _tabPage[tab] || 1 }
function _resetPage(tab) {
  // Clear the top-level tab page AND any group-level keys (e.g. "franchises-Marvel's Avengers")
  Object.keys(_tabPage).forEach(k => { if (k === tab || k.startsWith(tab + "-")) delete _tabPage[k] })
}
function _loadMore(tab) { _tabPage[tab] = (_tabPage[tab] || 1) + 1; render() }

function _paginate(list, tab) {
  const page    = _getPage(tab)
  const shown   = page * PAGE_SIZE
  const slice   = list.slice(0, shown)
  const rem     = list.length - shown
  const safeTab = tab.replace(/\\/g, "\\\\").replace(/'/g, "\\'")
  const btn     = rem > 0
    ? `<div style="text-align:center;padding:1.5rem 0">
        <button onclick="_loadMore('${safeTab}')"
          style="background:var(--bg3);border:1px solid var(--border2);color:var(--text2);
                 border-radius:8px;padding:.5rem 1.5rem;cursor:pointer;font-family:'DM Mono',monospace;
                 font-size:.75rem">Load ${Math.min(rem,PAGE_SIZE)} more (${rem} remaining)</button>
      </div>`
    : ""
  return { slice, btn }
}

/* ── Dashboard ───────────────────────────────────────────── */

function renderDashboard(){
  _teardownDashRO()
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
  const classicsPct   = s.classics_proxy_pct||0
  const _cTotal       = classicsMiss === 0
    ? (classicsPct >= 100 ? null : 0)   // null = "all done", 0 = not configured
    : Math.round(classicsMiss/(1-classicsPct/100))||classicsMiss
  const classicsTotal = _cTotal ?? 0
  const classicsHave  = _cTotal === null ? null : Math.max(0, classicsTotal - classicsMiss)

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
    .map(([id,n])=>({id, name:GENRE_MAP[id], count:n}))

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
    ${kpi(Math.round(s.classics_proxy_pct??0)+"%","Classics","#a855f7","classics",classicsHave===null?"All done! 🎉":`${classicsHave}/${classicsTotal} in library`)}
    ${kpi(Math.round(s.global_cinema_score??0)+"%","Global Score","#22c55e","","composite")}
    ${kpi(totalMissing,"Total Missing","var(--text)","franchises","unique films")}
    ${kpi((DATA.wishlist||[]).length,"Wishlist","var(--gold)","wishlist","saved for later")}
  </div>

  <!-- Doughnuts row -->
  <div class="db-row" style="margin-bottom:.75rem">
    <div class="card card-compact">
      <div class="card-title">Franchise Status</div>
      <div class="chart-duo">
        <div class="chart-donut-wrap"><canvas id="cFranchise"></canvas></div>
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
        <div class="chart-donut-wrap"><canvas id="cClassics"></canvas></div>
        <div class="legend-stack">
          ${leg("#a855f7","In Library",classicsHave??classicsTotal,"classics")}
          ${leg("#27272a","Missing",classicsMiss,"classics")}
        </div>
      </div>
    </div>
    <div class="card card-compact">
      <div class="card-title">Metadata Health</div>
      <div class="chart-duo">
        <div class="chart-donut-wrap"><canvas id="cMeta"></canvas></div>
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
          const jsName = f.name.replace(/\\/g,"\\\\").replace(/'/g,"\\'")
          return `<div class="fbr" onclick="navigateToGroupTab('franchises','${jsName}')" style="cursor:pointer">
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
        responsive:true, maintainAspectRatio:false,
        plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>`${ctx.label}: ${ctx.parsed}`}}},
        onClick:(e,els)=>{ if(els.length&&onClick) onClick(els[0].index) }
      }
    })

    mkChart("cFranchise",doughnut(
      ["Complete","Missing 1","Missing 2+"],[fComplete,fOne,fMore],
      ["#22c55e","#F5C518","#ef4444"],i=>{ if(i>0) setActiveTab("franchises") }
    ))
    mkChart("cClassics",doughnut(
      ["In Library","Missing"],
      classicsHave===null ? [1,0] : [classicsHave,classicsMiss],
      ["#a855f7","#27272a"],i=>{ if(i===1) setActiveTab("classics") }
    ))
    mkChart("cMeta",doughnut(
      ["Valid TMDB","No GUID","No Match"],[okMovies,noGuid,noMatch],
      ["#22c55e","#F5C518","#ef4444"],i=>{ if(i===1) setActiveTab("notmdb"); else if(i===2) setActiveTab("nomatch") }
    ))

    // Missing by decade — clicking navigates to Suggestions filtered by that decade
    const decadeToYear={"2020s":"2020s","2010s":"2010s","2000s":"2000s","1990s":"1990s","1980s":"older","1970s":"older","Pre-1970":"older"}
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
        plugins:{legend:{display:false}},
        onClick:(e,els)=>{
          if(!els.length) return
          const decade = dLabels[els[0].index]
          navigateToSuggestions({ year: decadeToYear[decade]||"" })
        }
      }
    })

    // Genre gap — clicking navigates to Suggestions filtered by that genre
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
        plugins:{legend:{display:false}},
        onClick:(e,els)=>{
          if(!els.length) return
          const gid = topGenres[els[0].index]?.id
          if(gid) navigateToSuggestions({ genreId: String(gid) })
        }
      }
    })

    // Top actors — clicking a bar deep-links to Actors tab filtered to that actor
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
        plugins:{legend:{display:false}},
        onClick:(e,els)=>{
          if(!els.length) return
          const name = topActors[els[0].index]?.name
          if(name) navigateToGroupTab("actors", name)
        }
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

    // Resize all dashboard charts when the content area changes size
    // (covers fullscreen toggle, sidebar collapse, window resize)
    _teardownDashRO()
    _dashRO = new ResizeObserver(() => {
      Object.values(_charts).forEach(ch => { try { ch.resize() } catch(_){} })
    })
    const contentEl = document.getElementById("content")
    if (contentEl) _dashRO.observe(contentEl)
  })
}

/* ── Grouped list (franchises / directors / actors) ─────── */

function renderGroupedList({ groups, nameKey, nameIcon, ignoreHandler, emptyMsg, showHave = false }){
  const c           = document.getElementById("content")
  const groupFilter = getGroupFilter()
  const sort        = getSort()
  const genreFilter = getGenreFilter()

  // When sort=title, sort the group headers themselves A-Z
  const orderedGroups = sort === "title"
    ? [...groups].sort((a, b) => (a[nameKey]||"").localeCompare(b[nameKey]||""))
    : groups

  let html = ""

  orderedGroups.forEach(g => {
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

    const ratingMin = getRatingFilter()
    if (ratingMin > 0) {
      sorted = sorted.filter(m => (m.rating||0) >= ratingMin)
    }

    if (!sorted.length) return

    const groupTab = `${ACTIVE_TAB}-${name}`
    const { slice, btn: moreBtn } = _paginate(sorted, groupTab)

    const haveList    = (showHave && g.have_list) ? g.have_list : []
    const haveSection = haveList.length
      ? `<details class="have-section">
           <summary style="cursor:pointer;font-size:.73rem;color:var(--text3);margin:.5rem 0 .4rem;user-select:none">
             ▸ In your library (${haveList.length})
           </summary>
           <div class="grid-posters" style="opacity:.45;pointer-events:none">
             ${haveList.map(m => posterCard(m)).join("")}
           </div>
         </details>`
      : ""

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
      <div class="grid-posters">${slice.map(m=>posterCard(m)).join("")}</div>
      ${moreBtn}
      ${haveSection}
    </div>`
  })

  c.innerHTML = html || emptyStateHTML(emptyMsg)
}

/* ── Franchises ──────────────────────────────────────────── */

function renderFranchises(){
  const st = _sectionStatus("franchises")
  const c  = document.getElementById("content")
  if (st === "pending")   { c.innerHTML = _renderSectionPending("Franchises");           return }
  if (st === "computing") { c.innerHTML = _renderSectionComputing("Analyzing franchises…"); return }

  const all        = DATA.franchises || []
  const incomplete = all.filter(f => (f.missing||[]).length > 0)
  const complete   = all.filter(f => (f.missing||[]).length === 0)

  renderGroupedList({
    groups: incomplete, nameKey:"name", nameIcon:"🎬",
    ignoreHandler:"ignoreFranchise", emptyMsg:"No missing franchise movies 🎉"
  })

  if (complete.length === 0) return

  const sorted = [...complete].sort((a,b) => (a.name||"").localeCompare(b.name||""))
  const pills  = sorted.map(f => `
    <div style="display:flex;align-items:center;gap:.5rem;padding:.4rem .7rem;
                background:var(--bg2);border:1px solid var(--border2);border-radius:8px">
      <span style="font-size:.8rem;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
        🎬 ${escHtml(f.name)}
      </span>
      <span style="margin-left:auto;font-size:.72rem;color:#22c55e;font-weight:700;white-space:nowrap;flex-shrink:0">
        ✓ ${f.have}/${f.total}
      </span>
    </div>`).join("")

  c.innerHTML += `
    <details class="completed-franchises-section" style="margin-top:2.5rem">
      <summary style="cursor:pointer;user-select:none;list-style:none;display:flex;
                      align-items:center;gap:.5rem;padding:.4rem 0;margin-bottom:.1rem">
        <span class="cfs-chevron" style="font-size:.7rem;color:var(--text3);
                                         transition:transform .2s;display:inline-block">▶</span>
        <span style="font-size:.8rem;font-weight:700;color:#22c55e;letter-spacing:.03em">
          Complete ✓
        </span>
        <span style="font-size:.78rem;color:var(--text3)">(${complete.length})</span>
      </summary>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));
                  gap:.45rem;margin-top:.6rem">
        ${pills}
      </div>
    </details>`

  // Rotate chevron when open
  c.querySelector(".completed-franchises-section")?.addEventListener("toggle", function(){
    const ch = this.querySelector(".cfs-chevron")
    if (ch) ch.style.transform = this.open ? "rotate(90deg)" : ""
  })
}

/* ── Directors ───────────────────────────────────────────── */

function renderDirectors(){
  const st = _sectionStatus("directors")
  const c  = document.getElementById("content")
  if (st === "pending")   { c.innerHTML = _renderSectionPending("Directors");            return }
  if (st === "computing") { c.innerHTML = _renderSectionComputing("Analyzing directors…"); return }
  renderGroupedList({
    groups: DATA.directors||[], nameKey:"name", nameIcon:"🎬",
    ignoreHandler:"ignoreDirector", emptyMsg:"No missing director films found"
  })
}

/* ── Actors ──────────────────────────────────────────────── */

function renderActors(){
  const st = _sectionStatus("actors")
  const c  = document.getElementById("content")
  if (st === "pending")   { c.innerHTML = _renderSectionPending("Actors");            return }
  if (st === "computing") { c.innerHTML = _renderSectionComputing("Analyzing actors…"); return }
  renderGroupedList({
    groups: DATA.actors||[], nameKey:"name", nameIcon:"🎭",
    ignoreHandler:"ignoreActor", emptyMsg:"No actor suggestions found",
    showHave: true,
  })
}

/* ── Classics ────────────────────────────────────────────── */

/* ── Shared grid helpers ─────────────────────────────────── */

// Holds the current tab's filtered movie list so _addAllBtn onclick can reference it
let _tabAllMovies = []

/* Genre pills — shows genres present in `movies`, clicking filters/unfilters */
function _genrePills(movies) {
  if (!movies.length) return ""
  const counts = {}
  for (const m of movies)
    for (const gid of (m.genre_ids || []))
      counts[gid] = (counts[gid] || 0) + 1
  if (!Object.keys(counts).length) return ""
  const active = getGenreFilter()
  const pills = Object.entries(counts)
    .filter(([id]) => GENRE_MAP[id])
    .sort((a, b) => b[1] - a[1])
    .map(([id, cnt]) => {
      const on = String(id) === String(active)
      return `<button onclick="onGenreFilterChange(${on ? "''" : id})"
        style="padding:3px 10px;border-radius:20px;
               border:1px solid ${on ? "var(--gold)" : "var(--border2)"};
               background:${on ? "rgba(255,197,61,.12)" : "var(--bg3)"};
               color:${on ? "var(--gold)" : "var(--text3)"};
               font-size:.68rem;cursor:pointer;white-space:nowrap;
               font-family:'DM Mono',monospace;line-height:1.6"
        >${GENRE_MAP[id]}<span style="opacity:.55;margin-left:.3rem">${cnt}</span></button>`
    }).join("")
  return `<div style="display:flex;flex-wrap:wrap;gap:.35rem;margin-bottom:.9rem">${pills}</div>`
}

/* "Add all X to Radarr" button — only rendered when Radarr is enabled */
function _addAllBtn(movies) {
  if (!CONFIG?.RADARR?.RADARR_ENABLED || !movies.length) return ""
  return `<div style="display:flex;justify-content:flex-end;margin-bottom:.6rem">
    <button onclick="addAllToRadarr(_tabAllMovies)"
      style="padding:5px 14px;border-radius:7px;
             border:1px solid rgba(123,47,190,.4);
             background:rgba(123,47,190,.12);color:#a78bfa;
             cursor:pointer;font-size:.72rem;font-family:'DM Mono',monospace">
      ⬇ Add all ${movies.length} to Radarr
    </button>
  </div>`
}

function renderClassics(){
  const st = _sectionStatus("classics")
  const c  = document.getElementById("content")
  if (st === "pending")   { c.innerHTML = _renderSectionPending("Classics");           return }
  if (st === "computing") { c.innerHTML = _renderSectionComputing("Building classics…"); return }
  let list   = applyFilters(DATA.classics||[])
  if (!list.length){ c.innerHTML=emptyStateHTML("No missing classics 🎉"); return }
  _tabAllMovies = list
  const { slice, btn } = _paginate(list, "classics")
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:.6rem">${list.length} classic films missing from your library</p>
    ${_genrePills(list)}
    ${_addAllBtn(list)}
    <div class="grid-posters">${slice.map(m=>posterCard(m)).join("")}</div>${btn}`
}

/* ── Suggestions ─────────────────────────────────────────── */

function renderSuggestions(){
  const st = _sectionStatus("suggestions")
  const c  = document.getElementById("content")
  if (st === "pending")   { c.innerHTML = _renderSectionPending("Suggestions");              return }
  if (st === "computing") { c.innerHTML = _renderSectionComputing("Building suggestions…");  return }
  const owned = new Set(DATA.owned_tmdb_ids||[])
  const raw   = (DATA.suggestions||[]).filter(m => !owned.has(m.tmdb))
  const list  = applyFilters(raw)
  if (!list.length){ c.innerHTML=emptyStateHTML("No suggestions available"); return }
  _tabAllMovies = list
  const { slice, btn } = _paginate(list, "suggestions")
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:.6rem">${list.length} films recommended by your library</p>
    ${_genrePills(list)}
    ${_addAllBtn(list)}
    <div class="grid-posters">${slice.map(m => suggestionCard(m)).join("")}</div>${btn}`
}

/* ── Wishlist ────────────────────────────────────────────── */

async function renderWishlist(){
  const c    = document.getElementById("content")
  const list = applyFilters(DATA.wishlist||[])

  if (!list.length){
    c.innerHTML = emptyStateHTML("Wishlist is empty")
    return
  }

  // Fetch Radarr sync status (non-blocking — falls back gracefully)
  let radarrStatuses = {}
  if (CONFIG?.RADARR?.RADARR_ENABLED) {
    try {
      const res = await api("/api/radarr/status")
      if (res.ok) radarrStatuses = res.statuses || {}
    } catch (_) {}
  }

  _tabAllMovies = list
  const { slice, btn } = _paginate(list, "wishlist")
  c.innerHTML = `
    ${_genrePills(list)}
    <div class="grid-posters">${slice.map(m => {
      const s = radarrStatuses[m.tmdb]
      const badge = s === "available"
        ? `<span style="background:var(--radarr,#7B2FBE);color:#fff;font-size:.58rem;padding:1px 5px;border-radius:3px;vertical-align:middle">✓ In Radarr</span>`
        : s === "monitored"
        ? `<span style="background:var(--gold);color:#000;font-size:.58rem;padding:1px 5px;border-radius:3px;vertical-align:middle">⬇ Searching</span>`
        : ""
      return posterCard(m, badge)
    }).join("")}</div>${btn}`
}

/* ── In Theaters tab ─────────────────────────────────────── */

let _theaterCache    = null
let _theaterFetching = false

async function renderTheaters() {
  const c = document.getElementById("content")

  // Show skeleton on first load
  if (!_theaterCache && !_theaterFetching) {
    _theaterFetching = true
    c.innerHTML = _renderSectionComputing("Fetching from TMDB…")
    try {
      const res = await api("/api/theaters")
      if (!res.ok) {
        c.innerHTML = emptyStateHTML(res.error || "Failed to load theater data")
        _theaterFetching = false
        return
      }
      _theaterCache = res
    } catch(e) {
      c.innerHTML = emptyStateHTML("Failed to load theater data")
      _theaterFetching = false
      return
    }
    _theaterFetching = false
  }

  if (!_theaterCache) { c.innerHTML = _renderSectionComputing("Loading…"); return }

  const all  = _theaterCache.movies || []
  const list = applyFilters(all)

  if (!all.length) {
    c.innerHTML = emptyStateHTML("No upcoming films found — check your TMDB API key")
    return
  }
  if (!list.length) {
    c.innerHTML = emptyStateHTML("No films match the current filters")
    return
  }

  _tabAllMovies = list
  const { slice, btn } = _paginate(list, "theaters")
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:.6rem">
      ${list.length} films now playing or coming soon · not in your library
      <button onclick="_theaterCache=null;renderTheaters()"
        style="margin-left:.75rem;background:none;border:none;color:var(--text3);
               cursor:pointer;font-size:.78rem;vertical-align:middle" title="Refresh">↻</button>
    </p>
    ${_genrePills(list)}
    ${_addAllBtn(list)}
    <div class="grid-posters">${slice.map(m => {
      const rel = m.release_date
        ? `<span style="background:var(--bg3);color:var(--text3);font-size:.56rem;
                        padding:1px 5px;border-radius:3px">📅 ${m.release_date}</span>`
        : ""
      return posterCard(m, rel)
    }).join("")}</div>${btn}`
}

/* ── Letterboxd tab ──────────────────────────────────────── */

let _lbPollTimer   = null   // setInterval handle while refresh is in flight
let _lbLastFetched = null   // last known fetched_at ISO string

function _lbUrlManager(savedUrls, moviesRes) {
  const urlList = savedUrls.length
    ? savedUrls.map(u => {
        const safe   = escHtml(u)
        const safeJs = u.replace(/\\/g,"\\\\").replace(/'/g,"\\'")
        return `<div style="display:flex;align-items:center;gap:.5rem;padding:.35rem 0;border-bottom:1px solid var(--border)">
          <span style="flex:1;font-size:.75rem;color:var(--text2);overflow:hidden;text-overflow:ellipsis;
                       white-space:nowrap" title="${safe}">${safe}</span>
          <button onclick="removeLbUrl('${safeJs}',this)"
            style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:.85rem;
                   padding:2px 6px;flex-shrink:0" title="Remove">✕</button>
        </div>`
      }).join("")
    : `<p style="color:var(--text3);font-size:.75rem;padding:.4rem 0">No lists added yet</p>`

  const count = moviesRes?.movies?.length || 0
  const owned = moviesRes?.owned_count   || 0
  const stats = count
    ? `<span style="color:var(--text3);font-size:.72rem">${count} movies${owned ? ` · ${owned} already owned hidden` : ""}</span>`
    : ""

  const isRefreshing = _lbPollTimer !== null || moviesRes?.refreshing
  let freshness = ""
  if (isRefreshing) {
    freshness = `<span style="color:var(--text3);font-size:.7rem;font-style:italic">↻ Refreshing…</span>`
  } else if (moviesRes?.fetched_at) {
    const mins = Math.round((Date.now() - new Date(moviesRes.fetched_at)) / 60000)
    const label = mins < 1 ? "just now" : `${mins}m ago`
    freshness = `<span style="color:var(--text3);font-size:.7rem">Updated ${label}</span>`
  }

  return `
    <div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;
                padding:1rem 1.2rem;margin-bottom:1.5rem">
      <div style="font-size:.68rem;letter-spacing:.1em;text-transform:uppercase;
                  color:var(--text3);margin-bottom:.75rem;display:flex;align-items:center;gap:.5rem">
        Letterboxd Lists
        ${stats}
        ${freshness}
        <button onclick="triggerLbRefresh()"
          style="margin-left:auto;background:none;border:none;color:var(--text3);cursor:pointer;
                 font-size:.85rem;padding:2px 6px;flex-shrink:0;line-height:1" title="Refresh">↻</button>
      </div>
      <div style="margin-bottom:.75rem">${urlList}</div>
      <div style="display:flex;flex-direction:column;gap:.35rem">
        <div style="display:flex;gap:.5rem;align-items:center">
          <input id="lbUrlInput" type="url"
            placeholder="e.g. letterboxd.com/you/watchlist/ or /list/my-list/"
            style="flex:1;min-width:0;padding:6px 10px;border-radius:7px;border:1px solid var(--border2);
                   background:var(--bg3);color:var(--text);font-size:.78rem;font-family:'DM Mono',monospace"
            onkeydown="if(event.key==='Enter')addLbUrl(this)"/>
          <button onclick="addLbUrl(document.getElementById('lbUrlInput'))"
            style="white-space:nowrap;padding:6px 14px;border-radius:7px;border:1px solid var(--border2);
                   background:var(--bg3);color:var(--text2);cursor:pointer;font-size:.75rem;
                   font-family:'DM Mono',monospace;flex-shrink:0">
            + Add
          </button>
        </div>
        <p style="color:var(--text3);font-size:.7rem;margin:0">
          Supports watchlists, named lists, diary feeds and profile RSS.
          E.g. <code style="color:var(--gold);font-size:.68rem">letterboxd.com/you/watchlist/</code> ·
          <code style="color:var(--gold);font-size:.68rem">letterboxd.com/you/list/best-of-2024/</code> ·
          <code style="color:var(--gold);font-size:.68rem">letterboxd.com/you/rss/</code>.
          Profile RSS feeds from curators are auto-expanded into their individual lists.
          All lists must be public.
        </p>
      </div>
    </div>`
}

async function renderLetterboxd() {
  const c = document.getElementById("content")

  // Both calls read local files — fast, no spinner needed
  let urlsRes, moviesRes
  try {
    [urlsRes, moviesRes] = await Promise.all([
      api("/api/letterboxd/urls"),
      api("/api/letterboxd/movies"),
    ])
  } catch(e) {
    c.innerHTML = emptyStateHTML("Failed to load Letterboxd data")
    return
  }

  // Track fetched_at so the poll can detect when new data arrives
  if (moviesRes.fetched_at) _lbLastFetched = moviesRes.fetched_at

  // Auto-trigger first-time fetch when URLs exist but no cache yet
  if (moviesRes.needs_refresh) triggerLbRefresh()

  // Keep poll running if a refresh is still in progress
  if (moviesRes.refreshing && !_lbPollTimer) _startLbPoll()

  const savedUrls = urlsRes.urls || []

  // If server returned an error (e.g. TMDB not configured), show it
  if (!moviesRes.ok) {
    c.innerHTML = _lbUrlManager(savedUrls) + emptyStateHTML(moviesRes.error || "Failed to load movies")
    return
  }

  const movies = moviesRes.movies || []

  // ── URL manager ─────────────────────────────────────────
  const urlManager = _lbUrlManager(savedUrls, moviesRes)

  if (!movies.length) {
    const hint = moviesRes.unique > 0
      ? `Found ${moviesRes.unique} movie IDs in RSS but TMDB enrichment returned nothing — check your TMDB API key`
      : savedUrls.length
        ? "No movies found — make sure the list is public and is a watchlist or named list (not a profile page)"
        : "Add a Letterboxd list above to get started"
    c.innerHTML = urlManager + emptyStateHTML(hint)
    return
  }

  const maxScore = movies[0]?.score || 1
  const filtered = applyFilters(movies)
  _tabAllMovies  = filtered
  const { slice, btn } = _paginate(filtered, "letterboxd")
  c.innerHTML = urlManager +
    (maxScore > 1
      ? `<p style="color:var(--text3);font-size:.75rem;margin-bottom:.6rem">
           Gold badge = appears in multiple lists · sorted by frequency then rating</p>`
      : "") +
    _genrePills(filtered) +
    _addAllBtn(filtered) +
    `<div class="grid-posters">${slice.map(m => lbPosterCard(m)).join("")}</div>${btn}`
}

/* ── Quality Upgrades tab ────────────────────────────────── */

let _upgradeCache     = null
let _upgradeFetching  = false

async function renderQualityUpgrades() {
  const c = document.getElementById("content")

  if (!_upgradeCache && !_upgradeFetching) {
    _upgradeFetching = true
    c.innerHTML = _renderSectionComputing("Checking Radarr library…")
    try {
      const res = await api("/api/quality/upgrades")
      if (!res.ok) {
        c.innerHTML = emptyStateHTML(res.error || "Failed to load quality data")
        _upgradeFetching = false
        return
      }
      _upgradeCache = res
    } catch(e) {
      c.innerHTML = emptyStateHTML("Failed to load quality data")
      _upgradeFetching = false
      return
    }
    _upgradeFetching = false
  }

  if (!_upgradeCache) return

  const movies = _upgradeCache.movies || []
  if (!movies.length) {
    c.innerHTML = `
      <div style="display:flex;justify-content:flex-end;margin-bottom:.75rem">
        <button onclick="_upgradeCache=null;renderQualityUpgrades()"
          style="background:none;border:1px solid var(--border2);color:var(--text3);
                 border-radius:6px;padding:.3rem .75rem;font-size:.75rem;cursor:pointer">⟳ Refresh</button>
      </div>` +
      emptyStateHTML("All your movies are already in Radarr 4K, or none qualify for upgrade")
    return
  }

  const list = applyFilters(movies)
  _tabAllMovies = list
  const { slice, btn } = _paginate(list, "upgrades")

  const header = `
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.75rem;flex-wrap:wrap;gap:.5rem">
      <p style="color:var(--text3);font-size:.75rem;margin:0">
        ${movies.length} movie${movies.length!==1?"s":""} at 720p or lower in your Radarr library — not yet in Radarr 4K
      </p>
      <button onclick="_upgradeCache=null;renderQualityUpgrades()"
        style="background:none;border:1px solid var(--border2);color:var(--text3);
               border-radius:6px;padding:.3rem .75rem;font-size:.75rem;cursor:pointer">⟳ Refresh</button>
    </div>`

  c.innerHTML = header +
    _genrePills(list) +
    `<div class="grid-posters">${slice.map(m => {
      const qBadge = `<span style="background:var(--bg3);color:var(--text3);font-size:.56rem;
                                   padding:1px 5px;border-radius:3px">📀 ${escHtml(m.current_quality||"")}</span>`
      return upgradeCard(m, qBadge)
    }).join("")}</div>${btn}`
}

function _startLbPoll() {
  if (_lbPollTimer) return   // already polling
  const started = Date.now()
  _lbPollTimer = setInterval(async () => {
    // Give up after 3 minutes
    if (Date.now() - started > 180_000) {
      clearInterval(_lbPollTimer)
      _lbPollTimer = null
      return
    }
    try {
      const res = await api("/api/letterboxd/movies")
      if (res.fetched_at && res.fetched_at !== _lbLastFetched) {
        clearInterval(_lbPollTimer)
        _lbPollTimer = null
        if (ACTIVE_TAB === "letterboxd") await renderLetterboxd()
      }
    } catch(_) { /* ignore transient poll errors */ }
  }, 5000)
}

/* ── Ignored ─────────────────────────────────────────────── */

async function renderIgnored(){
  const c = document.getElementById("content")
  c.innerHTML = `<p style="color:var(--text3);font-size:.78rem">Loading…</p>`

  const res = await api("/api/ignored")
  if (!res.ok) { c.innerHTML = emptyStateHTML("Could not load ignored list"); return }

  const movies = res.movies || []
  if (!movies.length) {
    c.innerHTML = emptyStateHTML("No ignored movies — click 🚫 on any card to hide it permanently")
    return
  }

  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">
      ${movies.length} ignored movie${movies.length!==1?"s":""} — these will never appear in Missing, Classics or Suggestions.
    </p>
    <div class="grid-posters">
      ${movies.map(m => {
        const safeName = (m.title||"").replace(/'/g,"\\'").replace(/"/g,"&quot;")
        const imgHtml  = m.poster
          ? `<img class="pc-img" src="${m.poster}" loading="lazy" alt=""/>`
          : `<div class="pc-no-img"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3"><rect x="2" y="2" width="20" height="20" rx="3"/><path d="M7 2v20M17 2v20M2 12h20"/></svg><span>No Image</span></div>`
        return `
          <div class="pc" id="ignored-${m.tmdb}">
            ${imgHtml}
            <div class="pc-info">
              <div class="pc-title" title="${escHtml(m.title||"")}">${escHtml(m.title||"Untitled")}</div>
              <div class="pc-meta">${m.year?`<span>${m.year}</span>`:""}</div>
            </div>
            <div class="pc-overlay">
              <div class="pc-overlay-title">${escHtml(m.title||"Untitled")}</div>
              <div class="pc-overlay-actions">
                <button class="btn-sm" onclick="unignoreMovie(${m.tmdb},'${safeName}',this)"
                  style="color:var(--green)">↩ Restore</button>
              </div>
            </div>
          </div>`
      }).join("")}
    </div>`
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
    <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem;flex-wrap:wrap">
      <p style="color:var(--text3);font-size:.78rem;margin:0">${list.length} movies with invalid TMDB metadata — failed lookups are retried automatically on next scan.</p>
      <button onclick="rescan()"
        style="flex-shrink:0;font-size:.72rem;padding:4px 12px;border-radius:6px;border:1px solid var(--border2);
               background:var(--bg3);color:var(--text2);cursor:pointer;font-family:'DM Mono',monospace">
        ↻ Retry now
      </button>
    </div>
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

/* ── Duplicates ──────────────────────────────────────────── */

function renderDuplicates(){
  const c    = document.getElementById("content")
  const list = DATA.duplicates || []
  if (!list.length){
    c.innerHTML = emptyStateHTML("No multi-version entries detected 🎉")
    return
  }
  c.innerHTML = `
    <p style="color:var(--text3);font-size:.78rem;margin-bottom:1rem">
      ${list.length} TMDB ID${list.length > 1 ? "s" : ""} appear more than once in your library.<br>
      This is usually <strong style="color:var(--text2)">intentional</strong> — e.g. Theatrical + Director's Cut share the same TMDB ID.
      Review and remove any unintentional copies from your media server.
    </p>
    <div style="display:flex;flex-direction:column;gap:.4rem">
      ${list.map(d=>{
        const titles     = d.titles || []
        const hasEdition = titles.some(t => t.edition)
        const allSame    = new Set(titles.map(t => t.title)).size === 1
        const isDupe     = !hasEdition && allSame
        const tagCls     = isDupe ? "tag-red" : "tag-gold"
        const tagLbl     = isDupe ? "DUPE" : "MULTI"
        const titleHtml  = titles.map(t => {
          const lbl = escHtml(t.title) + (t.edition ? ` <span style="color:var(--text3);font-size:.75em">[${escHtml(t.edition)}]</span>` : "")
          return lbl
        }).join(`<span style="color:var(--text3);margin:0 .3rem">·</span>`)
        return `
        <div class="meta-item">
          <span class="tag ${tagCls}" style="flex-shrink:0" title="${allSame ? "Same title — likely a true duplicate" : "Different titles — likely different editions"}">${tagLbl}</span>
          <span class="meta-item-title">${titleHtml}</span>
          <span class="meta-item-year">
            ${tag(`tmdb:${d.tmdb}`)}
            <a href="https://www.themoviedb.org/movie/${d.tmdb}" target="_blank" rel="noopener"
               style="color:var(--text3);font-size:.65rem;text-decoration:none;margin-left:.3rem">↗</a>
          </span>
        </div>`
      }).join("")}
    </div>
    <p style="color:var(--text3);font-size:.68rem;margin-top:1rem">
      <span style="color:var(--red)">DUPE</span> = identical titles (likely unintentional) &nbsp;·&nbsp;
      <span style="color:var(--gold)">MULTI</span> = different titles (likely different editions — OK to keep)
    </p>`
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

async function copyLetterboxdToClipboard() {
  if (!EXPORT_TABS.has(ACTIVE_TAB)) return
  try {
    const res  = await fetch(`/api/export?format=letterboxd&tab=${ACTIVE_TAB}`)
    const text = await res.text()
    await navigator.clipboard.writeText(text)
    toast("Letterboxd list copied to clipboard!", "success")
  } catch(e) {
    toast("Could not copy to clipboard", "error")
  }
}

function updateExportBtn() {
  const btn  = document.getElementById("exportBtn")
  const cbtn = document.getElementById("clipboardBtn")
  if (btn)  btn.style.display  = EXPORT_TABS.has(ACTIVE_TAB) ? "inline-block" : "none"
  if (cbtn) cbtn.style.display = EXPORT_TABS.has(ACTIVE_TAB) ? "inline-block" : "none"
}
