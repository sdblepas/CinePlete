/* ============================================================
   scan.js — data loading, scan polling, progress UI, skeleton
============================================================ */

let _pollTimer = null

async function loadConfig(){
  CONFIG = await api("/api/config")
}

let SETUP_ISSUES = []

async function loadStatus(){
  const s = await api("/api/config/status")
  CONFIGURED   = !!s.configured
  SETUP_ISSUES = s.issues || []
}

async function loadResults(){
  setStatus("Loading…")
  const data = await api("/api/results")
  if (data.scanning){
    setStatus("Scan in progress…")
    DATA = data
    updateBadges()
    render()          // renders available sections; pending ones show skeletons
    startPolling()
    return
  }
  DATA = data
  setStatus(`Updated ${fmtDate(DATA.generated_at)}`)
  updateBadges()
  render()
}

function updateBadges(){
  if (!DATA) return
  const b = (id, n) => {
    const el = document.getElementById(id)
    if (!el) return
    if (n > 0){ el.textContent = n > 99 ? "99+" : n; el.style.display = "" }
    else el.style.display = "none"
  }
  b("badge-notmdb",     (DATA.no_tmdb_guid   || []).length)
  b("badge-nomatch",    (DATA.tmdb_not_found || []).length)
  b("badge-wishlist",   (DATA.wishlist       || []).length)
  b("badge-duplicates", (DATA.duplicates     || []).length)
}

async function rescan(){
  if (!CONFIGURED){
    const msg = SETUP_ISSUES.length
      ? "Setup incomplete: " + SETUP_ISSUES[0]
      : "Complete setup first."
    toast(msg, "error")
    return
  }
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
  if (s.running){
    // Always fetch and re-render while scan is running so completed
    // sections appear as soon as they are written — do not gate on
    // data.scanning which can be false between partial writes
    const data = await api("/api/results")
    if (data) {
      DATA = data
      updateBadges()
      render()
    }
    return
  }
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
  if (ACTIVE_TAB === "logs") renderLogs()
  else render()
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