/* ============================================================
   config.js — Config tab renderer, save, cache management
============================================================ */

function _ageStr(s){
  if (s < 3600)  return `${Math.floor(s/60)}m ago`
  if (s < 86400) return `${Math.floor(s/3600)}h ago`
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
  if (res.ok){ toast(`Cache backed up (${res.size_mb} MB)`,"success"); loadCacheInfo() }
  else toast("Backup failed: " + res.error,"error")
}

async function restoreCache(){
  if (!confirm("Restore cache from backup? Current cache will be overwritten.")) return
  const res = await api("/api/cache/restore","POST",{})
  if (res.ok){ toast(`Cache restored (${res.size_mb} MB)`,"success"); loadCacheInfo() }
  else toast("Restore failed: " + res.error,"error")
}

async function clearCache(){
  if (!confirm("Clear the TMDB cache? The next scan will re-fetch all data from TMDB.")) return
  const res = await api("/api/cache/clear","POST",{})
  if (res.ok){ toast("TMDB cache cleared","success"); loadCacheInfo() }
  else toast("Failed to clear cache: " + res.error,"error")
}

function toggleSecret(id){
  const input = document.getElementById(id)
  const eye   = document.getElementById(id+"-eye")
  if (!input) return
  if (input.type === "password"){
    input.type = "text"
    if (eye) eye.innerHTML = `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>`
  } else {
    input.type = "password"
    if (eye) eye.innerHTML = `<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>`
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
  const tg    = cfg.TELEGRAM    ||{}

  const field = (id, label, value, type="text") => {
    const isSecret = type === "secret"
    const inputType = isSecret ? "password" : type
    const toggle = isSecret ? `
      <button type="button" onclick="toggleSecret('${id}')"
        style="position:absolute;right:.6rem;top:50%;transform:translateY(-50%);
               background:none;border:none;cursor:pointer;color:var(--text3);
               display:flex;align-items:center;padding:2px"
        title="Show/hide">
        <svg id="${id}-eye" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
          <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
          <line x1="1" y1="1" x2="23" y2="23"/>
        </svg>
      </button>` : ""
    return `
  <div class="form-group">
    <label class="form-label" for="${id}">${label}</label>
    <div style="position:relative">
      <input class="form-input" id="${id}" type="${inputType}" value="${value??""}"
        style="${isSecret?"padding-right:2.2rem":""}"/>
      ${toggle}
    </div>
  </div>`
  }

  const check = (id, label, checked) => `
  <div class="form-group" style="display:flex;align-items:center;gap:.6rem">
    <input type="checkbox" id="${id}" ${checked?"checked":""}
      style="accent-color:var(--gold);width:14px;height:14px;cursor:pointer"/>
    <label for="${id}" class="form-label" style="margin:0;cursor:pointer">${label}</label>
  </div>`

  const sec   = t => `<div class="form-section-title">${t}</div>`
  const sub   = t => `<p style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:1rem 0 .75rem">${t}</p>`
  const hint  = t => `<p style="font-size:.68rem;color:var(--text3);margin-top:-.25rem;margin-bottom:.5rem">${t}</p>`

  c.innerHTML = `
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:start">

    <!-- LEFT COLUMN -->
    <div>
      <div class="form-section">
        ${sec("Plex")}
        ${field("cfg_plex_url",   "Plex URL",     plex.PLEX_URL    ||"")}
        ${field("cfg_plex_token", "Plex Token",   plex.PLEX_TOKEN  ||"", "secret")}
        ${field("cfg_library",    "Library Name", plex.LIBRARY_NAME||"")}
      </div>

      <div class="form-section">
        ${sec("TMDB")}
        ${field("cfg_tmdb_key","TMDB API Key", tmdb.TMDB_API_KEY||"", "secret")}
      </div>

      <details class="form-section">
        <summary style="display:flex;align-items:center;justify-content:space-between">
          <span class="form-section-title" style="margin-bottom:0">Advanced Settings</span>
          <svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text3)" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
        </summary>
        <div style="margin-top:1rem">
          ${sub("Classics")}
          ${field("cfg_classics_pages",  "Pages to fetch",    cls.CLASSICS_PAGES      ??4,    "number")}
          ${field("cfg_classics_votes",  "Minimum votes",     cls.CLASSICS_MIN_VOTES  ??5000, "number")}
          ${field("cfg_classics_rating", "Minimum rating",    cls.CLASSICS_MIN_RATING ??8.0,  "number")}
          ${field("cfg_classics_max",    "Max results",       cls.CLASSICS_MAX_RESULTS??120,  "number")}
          ${sub("Actors")}
          ${field("cfg_actor_votes", "Min votes per film",    act.ACTOR_MIN_VOTES            ??500, "number")}
          ${field("cfg_actor_max",   "Max results per actor", act.ACTOR_MAX_RESULTS_PER_ACTOR??10,  "number")}
          ${sub("TMDB")}
          ${field("cfg_tmdb_workers","Concurrent workers (1–10)", tmdb.TMDB_WORKERS??6,"number")}
          ${hint("Higher = faster first scan. Default 6, max 10.")}
          ${sub("Plex Scanner")}
          ${field("cfg_plex_page_size","Page size",               plex.PLEX_PAGE_SIZE   ??500, "number")}
          ${field("cfg_short_limit",  "Short movie limit (min)", plex.SHORT_MOVIE_LIMIT??60,  "number")}
        </div>
      </details>
    </div>

    <!-- RIGHT COLUMN -->
    <div>
      <div class="form-section">
        ${sec('Radarr <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_radarr_enabled", "Enabled", radarr.RADARR_ENABLED)}
        ${field("cfg_radarr_url",     "Radarr URL",         radarr.RADARR_URL              ||"")}
        ${field("cfg_radarr_key",     "Radarr API Key",     radarr.RADARR_API_KEY          ||"", "secret")}
        ${field("cfg_radarr_root",    "Root Folder Path",   radarr.RADARR_ROOT_FOLDER_PATH ||"")}
        ${field("cfg_radarr_quality", "Quality Profile ID", radarr.RADARR_QUALITY_PROFILE_ID??6,"number")}
        ${check("cfg_radarr_search",  "Search &amp; download on add", radarr.RADARR_SEARCH_ON_ADD)}
      </div>

      <div class="form-section">
        ${sec('Telegram <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_tg_enabled", "Enabled", tg.TELEGRAM_ENABLED)}
        ${field("cfg_tg_token",   "Bot Token",  tg.TELEGRAM_BOT_TOKEN||"", "secret")}
        ${field("cfg_tg_chat",    "Chat ID",    tg.TELEGRAM_CHAT_ID  ||"")}
        ${field("cfg_tg_interval","Min interval between notifications (min)", tg.TELEGRAM_MIN_INTERVAL??30,"number")}
        ${hint("Get your Bot Token from @BotFather and Chat ID from @userinfobot.")}
      </div>

      <div class="form-section">
        ${sec("Automation")}
        ${field("cfg_poll_interval","Library poll interval (min, 0 = disabled)", auto.LIBRARY_POLL_INTERVAL??30,"number")}
        ${hint("Auto-scans when your Plex library size changes.")}
      </div>

      <div class="form-section" id="cache-section">
        ${sec("TMDB Cache")}
        <div id="cache-info" style="font-size:.75rem;color:var(--text3);margin-bottom:.75rem">Loading…</div>
        <div style="display:flex;gap:.5rem;flex-wrap:wrap">
          <button class="btn-sm" style="font-size:.72rem;padding:5px 14px;border-color:rgba(34,197,94,.3);color:var(--green)" onclick="backupCache()">💾 Backup</button>
          <button class="btn-sm" style="font-size:.72rem;padding:5px 14px;border-color:rgba(59,130,246,.3);color:var(--blue)" onclick="restoreCache()">↩ Restore</button>
          <button class="btn-sm btn-ignore" style="font-size:.72rem;padding:5px 14px" onclick="clearCache()">🗑 Clear</button>
        </div>
      </div>

      <button class="btn-primary" onclick="saveConfig()">Save Configuration</button>
      <div id="cfgStatus" style="font-size:.75rem;color:var(--text3);margin-top:.6rem;text-align:center"></div>
    </div>

  </div>`

  loadCacheInfo()
}

async function saveConfig(){
  const v  = id => document.getElementById(id)?.value?.trim()||""
  const vi = id => parseInt(v(id))||0
  const vf = id => parseFloat(v(id))||0
  const vc = id => document.getElementById(id)?.checked||false

  const payload = {
    PLEX:{
      PLEX_URL:         v("cfg_plex_url"),
      PLEX_TOKEN:       v("cfg_plex_token"),
      LIBRARY_NAME:     v("cfg_library"),
      PLEX_PAGE_SIZE:   vi("cfg_plex_page_size"),
      SHORT_MOVIE_LIMIT:vi("cfg_short_limit"),
    },
    TMDB:{
      TMDB_API_KEY: v("cfg_tmdb_key"),
      TMDB_WORKERS: vi("cfg_tmdb_workers"),
    },
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
      RADARR_ENABLED:           vc("cfg_radarr_enabled"),
      RADARR_URL:               v("cfg_radarr_url"),
      RADARR_API_KEY:           v("cfg_radarr_key"),
      RADARR_ROOT_FOLDER_PATH:  v("cfg_radarr_root"),
      RADARR_QUALITY_PROFILE_ID:vi("cfg_radarr_quality"),
      RADARR_SEARCH_ON_ADD:     vc("cfg_radarr_search"),
    },
    TELEGRAM:{
      TELEGRAM_ENABLED:      vc("cfg_tg_enabled"),
      TELEGRAM_BOT_TOKEN:    v("cfg_tg_token"),
      TELEGRAM_CHAT_ID:      v("cfg_tg_chat"),
      TELEGRAM_MIN_INTERVAL: vi("cfg_tg_interval"),
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