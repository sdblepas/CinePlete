/* ============================================================
   config.js — Config tab renderer, save, cache management
============================================================ */

// Returns the HTML for a quality profile select + Fetch button
function qualityProfileField(id, currentId, instance) {
  return `
  <div class="form-group">
    <label class="form-label">Quality Profile</label>
    <div style="display:flex;gap:.5rem;align-items:center">
      <select id="${id}"
        style="flex:1;background:var(--bg3);border:1px solid var(--border2);
               border-radius:8px;color:var(--text);font-family:'DM Mono',monospace;
               font-size:.82rem;padding:.45rem .6rem;outline:none">
        <option value="${currentId||0}">${currentId ? `⚠ ID ${currentId} — click Fetch to verify` : "— click Fetch to load profiles —"}</option>
      </select>
      <button type="button" class="btn-sm" style="white-space:nowrap;font-size:.72rem;padding:5px 12px"
        onclick="fetchRadarrProfiles('${instance}','${id}')">⟳ Fetch</button>
    </div>
  </div>`
}

async function fetchRadarrProfiles(instance, selectId) {
  const btn = event.target
  btn.disabled = true; btn.textContent = "…"
  try {
    const res = await api(`/api/radarr/profiles?instance=${instance}`)
    if (!res.ok) {
      toast(`Could not fetch profiles: ${res.error}`, "error")
      return
    }
    const sel = document.getElementById(selectId)
    if (!sel) return
    const current = parseInt(sel.value) || 0
    sel.innerHTML = res.profiles.map(p =>
      `<option value="${p.id}" ${p.id === current ? "selected" : ""}>${p.name} (${p.id})</option>`
    ).join("")
    toast("Quality profiles loaded", "success")
  } catch(e) {
    toast("Failed to fetch profiles", "error")
  } finally {
    btn.disabled = false; btn.textContent = "⟳ Fetch"
  }
}

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

async function testJellyfinConnection(){
  const url     = document.getElementById("cfg_jf_url")?.value?.trim()
  const token   = document.getElementById("cfg_jf_key")?.value?.trim()
  const library = document.getElementById("cfg_jf_library")?.value?.trim()
  const result  = document.getElementById("jf-test-result")

  if (!url || !token) { toast("Enter Jellyfin URL and API key first", "error"); return }
  if (result) result.textContent = "Testing…"

  const res = await api("/api/jellyfin/test", "POST", { url, token, library })
  if (result) {
    result.textContent = res.ok ? `✓ ${res.message}` : `✗ ${res.error}`
    result.style.color = res.ok ? "var(--green)" : "var(--red)"
  }
}

function toggleMediaServer(){
  const val = document.getElementById("cfg_media_server")?.value
  document.getElementById("plex-fields").style.display     = val === "plex"     ? "block" : "none"
  document.getElementById("jellyfin-fields").style.display = val === "jellyfin" ? "block" : "none"
}

function renderConfig(){
  const c     = document.getElementById("content")
  const cfg   = CONFIG||{}
  const plex  = cfg.PLEX        ||{}
  const tmdb  = cfg.TMDB        ||{}
  const radarr= cfg.RADARR      ||{}
  const r4k   = cfg.RADARR_4K   ||{}
  const cls   = cfg.CLASSICS    ||{}
  const act   = cfg.ACTOR_HITS  ||{}
  const auto  = cfg.AUTOMATION  ||{}
  const tg    = cfg.TELEGRAM    ||{}
  const jf    = cfg.JELLYFIN    ||{}
  const srv   = cfg.SERVER      ||{}
  const ovs   = cfg.OVERSEERR   ||{}
  const jss   = cfg.JELLYSEERR  ||{}
  const wh    = cfg.WEBHOOK     ||{}
  const wtch  = cfg.WATCHTOWER  ||{}
  const auth  = cfg.AUTH        ||{}

  const mediaServer = (srv.MEDIA_SERVER || "plex").toLowerCase()

  const field = (id, label, value, type="text") => {
    const isSecret  = type === "secret"
    const inputType = isSecret ? "password" : type
    const toggle    = isSecret ? `
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

  const sec  = t => `<div class="form-section-title">${t}</div>`
  const sub  = t => `<p style="font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:var(--text3);margin:1rem 0 .75rem">${t}</p>`
  const hint = t => `<p style="font-size:.68rem;color:var(--text3);margin-top:-.25rem;margin-bottom:.5rem">${t}</p>`

  c.innerHTML = `
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:start">

    <!-- LEFT COLUMN -->
    <div>
      <div class="form-section">
        ${sec('Authentication <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        <div class="form-group">
          <label class="form-label">Auth Mode</label>
          <select id="cfg_auth_method"
            style="width:100%;background:var(--bg3);border:1px solid var(--border2);
                   border-radius:8px;color:var(--text);font-family:'DM Mono',monospace;
                   font-size:.82rem;padding:.45rem .6rem;outline:none">
            <option value="None"                     ${(auth.AUTH_METHOD||"None")==="None"?"selected":""}>None — open access</option>
            <option value="DisabledForLocalAddresses" ${auth.AUTH_METHOD==="DisabledForLocalAddresses"?"selected":""}>Local network free, login from internet</option>
            <option value="Forms"                     ${auth.AUTH_METHOD==="Forms"?"selected":""}>Always require login</option>
          </select>
        </div>
        ${field("cfg_auth_username", "Username", auth.AUTH_USERNAME||"")}
        ${field("cfg_auth_password", "New Password", "", "secret")}
        ${auth.AUTH_HAS_PASSWORD
          ? hint("Password is set. Leave blank to keep current password.")
          : hint("No password set yet. Enter one to enable login.")}
      </div>

      <div class="form-section">
        ${sec("Media Server")}
        <div class="form-group">
          <label class="form-label">Server Type</label>
          <select id="cfg_media_server" onchange="toggleMediaServer()"
            style="width:100%;background:var(--bg3);border:1px solid var(--border2);
                   border-radius:8px;color:var(--text);font-family:'DM Mono',monospace;
                   font-size:.82rem;padding:.55rem .85rem;outline:none">
            <option value="plex"     ${mediaServer==="plex"     ?"selected":""}>Plex</option>
            <option value="jellyfin" ${mediaServer==="jellyfin" ?"selected":""}>Jellyfin</option>
          </select>
        </div>
        <div id="plex-fields" style="display:${mediaServer==="plex"?"block":"none"}">
          ${field("cfg_plex_url",   "Plex URL",     plex.PLEX_URL    ||"")}
          ${field("cfg_plex_token", "Plex Token",   plex.PLEX_TOKEN  ||"", "secret")}
          ${field("cfg_library",    "Library Name", plex.LIBRARY_NAME||"")}
        </div>
        <div id="jellyfin-fields" style="display:${mediaServer==="jellyfin"?"block":"none"}">
          ${field("cfg_jf_url",     "Jellyfin URL",  jf.JELLYFIN_URL          ||"")}
          ${field("cfg_jf_key",     "API Key",        jf.JELLYFIN_API_KEY      ||"", "secret")}
          ${field("cfg_jf_library", "Library Name",   jf.JELLYFIN_LIBRARY_NAME ||"Movies")}
          <div style="display:flex;align-items:center;gap:.75rem;margin-top:.25rem">
            <button class="btn-sm" style="font-size:.72rem;padding:5px 14px" onclick="testJellyfinConnection()">Test Connection</button>
            <span id="jf-test-result" style="font-size:.72rem"></span>
          </div>
        </div>

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
          ${sub("Scanner")}
          ${field("cfg_plex_page_size","Page size",               plex.PLEX_PAGE_SIZE   ??500, "number")}
          ${field("cfg_short_limit",  "Short movie limit (min)", plex.SHORT_MOVIE_LIMIT??60,  "number")}
        </div>
      </details>

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
        ${hint("Auto-scans when your media server library size changes.")}
        <div class="form-group">
          <label class="form-label">Scheduled rescan</label>
          <select id="cfg_auto_scan_schedule"
            style="width:100%;background:var(--bg3);border:1px solid var(--border2);
                   border-radius:8px;color:var(--text);font-family:'DM Mono',monospace;
                   font-size:.82rem;padding:.45rem .6rem;outline:none">
            <option value="off"    ${(auto.AUTO_SCAN_SCHEDULE||"off")==="off"    ?"selected":""}>Off</option>
            <option value="daily"  ${auto.AUTO_SCAN_SCHEDULE==="daily"  ?"selected":""}>Daily at 02:00</option>
            <option value="weekly" ${auto.AUTO_SCAN_SCHEDULE==="weekly" ?"selected":""}>Weekly on Sunday at 02:00</option>
          </select>
        </div>
        ${hint("Full rescan on a fixed schedule, regardless of library changes.")}
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

    </div>

    <!-- RIGHT COLUMN — Integrations -->
    <div>
      <div class="form-section">
        ${sec('Radarr <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_radarr_enabled", "Enabled", radarr.RADARR_ENABLED)}
        ${field("cfg_radarr_url",  "Radarr URL",     radarr.RADARR_URL     ||"")}
        ${field("cfg_radarr_key",  "Radarr API Key", radarr.RADARR_API_KEY ||"", "secret")}
        ${field("cfg_radarr_root", "Root Folder Path", radarr.RADARR_ROOT_FOLDER_PATH ||"")}
        ${qualityProfileField("cfg_radarr_quality", radarr.RADARR_QUALITY_PROFILE_ID??0, "primary")}
        ${check("cfg_radarr_search", "Search &amp; download on add", radarr.RADARR_SEARCH_ON_ADD)}
      </div>

      <div class="form-section">
        ${sec('Radarr 4K <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_r4k_enabled", "Enabled", r4k.RADARR_4K_ENABLED)}
        ${field("cfg_r4k_url",  "Radarr 4K URL",      r4k.RADARR_4K_URL     ||"")}
        ${field("cfg_r4k_key",  "Radarr 4K API Key",  r4k.RADARR_4K_API_KEY ||"", "secret")}
        ${field("cfg_r4k_root", "Root Folder Path",   r4k.RADARR_4K_ROOT_FOLDER_PATH ||"")}
        ${qualityProfileField("cfg_r4k_quality", r4k.RADARR_4K_QUALITY_PROFILE_ID??0, "4k")}
        ${check("cfg_r4k_search", "Search &amp; download on add", r4k.RADARR_4K_SEARCH_ON_ADD)}
        ${hint("Shows a separate '+ 4K' button on every movie card.")}
      </div>

      <div class="form-section">
        ${sec('Overseerr <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_ovs_enabled", "Enabled", ovs.OVERSEERR_ENABLED)}
        ${field("cfg_ovs_url",   "Overseerr URL",  ovs.OVERSEERR_URL    ||"")}
        ${field("cfg_ovs_key",   "API Key",         ovs.OVERSEERR_API_KEY||"", "secret")}
        ${hint("Point to your Overseerr instance. API key found in Overseerr → Settings → General.")}
      </div>

      <div class="form-section">
        ${sec('Jellyseerr <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_jss_enabled", "Enabled", jss.JELLYSEERR_ENABLED)}
        ${field("cfg_jss_url",   "Jellyseerr URL",  jss.JELLYSEERR_URL    ||"")}
        ${field("cfg_jss_key",   "API Key",          jss.JELLYSEERR_API_KEY||"", "secret")}
        ${hint("Same API format as Overseerr. API key found in Jellyseerr → Settings → General.")}
      </div>

      <div class="form-section">
        ${sec('Webhook <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_wh_enabled", "Enabled", wh.WEBHOOK_ENABLED)}
        ${field("cfg_wh_secret",  "Secret (optional)", wh.WEBHOOK_SECRET||"", "secret")}
        ${hint("POST to <code style='color:var(--gold)'>/api/webhook?secret=…</code> from Plex/Jellyfin to trigger a rescan. Leave secret blank to allow unauthenticated calls.")}
      </div>

      <div class="form-section">
        ${sec('Watchtower <span style="font-size:.75rem;font-weight:400;color:var(--text3)">(optional)</span>')}
        ${check("cfg_wtch_enabled", "Auto-update enabled", wtch.WATCHTOWER_ENABLED)}
        ${field("cfg_wtch_url",   "Watchtower URL",  wtch.WATCHTOWER_URL        ||"")}
        ${field("cfg_wtch_token", "API Token",        wtch.WATCHTOWER_API_TOKEN  ||"", "secret")}
        ${hint("Pulls the latest CinePlete image automatically. Enable the Watchtower HTTP API with <code style='color:var(--gold)'>WATCHTOWER_HTTP_API_UPDATE=true</code> and set a matching token.")}
        <button class="btn-sm" style="margin-top:.5rem;font-size:.72rem;padding:5px 14px;border-color:rgba(59,130,246,.3);color:var(--blue)"
          onclick="triggerWatchtowerUpdate()">⬆ Update Now</button>
        <span id="wtchStatus" style="font-size:.72rem;color:var(--text3);margin-left:.5rem"></span>
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
    SERVER:{
      MEDIA_SERVER: v("cfg_media_server"),
    },
    // For the inactive server, the fields are hidden (display:none) so their
    // DOM inputs don't exist — fall back to last saved CONFIG values
    PLEX:{
      PLEX_URL:         document.getElementById("cfg_plex_url")    ? v("cfg_plex_url")    : (CONFIG?.PLEX?.PLEX_URL    ||""),
      PLEX_TOKEN:       document.getElementById("cfg_plex_token")  ? v("cfg_plex_token")  : (CONFIG?.PLEX?.PLEX_TOKEN  ||""),
      LIBRARY_NAME:     document.getElementById("cfg_library")     ? v("cfg_library")     : (CONFIG?.PLEX?.LIBRARY_NAME||""),
      PLEX_PAGE_SIZE:   vi("cfg_plex_page_size") ?? CONFIG?.PLEX?.PLEX_PAGE_SIZE    ?? 500,
      SHORT_MOVIE_LIMIT:vi("cfg_short_limit")    ?? CONFIG?.PLEX?.SHORT_MOVIE_LIMIT ?? 60,
    },
    JELLYFIN:{
      JELLYFIN_URL:          document.getElementById("cfg_jf_url")     ? v("cfg_jf_url")     : (CONFIG?.JELLYFIN?.JELLYFIN_URL          ||""),
      JELLYFIN_API_KEY:      document.getElementById("cfg_jf_key")     ? v("cfg_jf_key")     : (CONFIG?.JELLYFIN?.JELLYFIN_API_KEY      ||""),
      JELLYFIN_LIBRARY_NAME: document.getElementById("cfg_jf_library") ? v("cfg_jf_library") : (CONFIG?.JELLYFIN?.JELLYFIN_LIBRARY_NAME ||"Movies"),
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
    RADARR_4K:{
      RADARR_4K_ENABLED:           vc("cfg_r4k_enabled"),
      RADARR_4K_URL:               v("cfg_r4k_url"),
      RADARR_4K_API_KEY:           v("cfg_r4k_key"),
      RADARR_4K_ROOT_FOLDER_PATH:  v("cfg_r4k_root"),
      RADARR_4K_QUALITY_PROFILE_ID:vi("cfg_r4k_quality"),
      RADARR_4K_SEARCH_ON_ADD:     vc("cfg_r4k_search"),
    },
    OVERSEERR:{
      OVERSEERR_ENABLED: vc("cfg_ovs_enabled"),
      OVERSEERR_URL:     v("cfg_ovs_url"),
      OVERSEERR_API_KEY: v("cfg_ovs_key"),
    },
    JELLYSEERR:{
      JELLYSEERR_ENABLED: vc("cfg_jss_enabled"),
      JELLYSEERR_URL:     v("cfg_jss_url"),
      JELLYSEERR_API_KEY: v("cfg_jss_key"),
    },
    WEBHOOK:{
      WEBHOOK_ENABLED: vc("cfg_wh_enabled"),
      WEBHOOK_SECRET:  v("cfg_wh_secret"),
    },
    WATCHTOWER:{
      WATCHTOWER_ENABLED:   vc("cfg_wtch_enabled"),
      WATCHTOWER_URL:       v("cfg_wtch_url"),
      WATCHTOWER_API_TOKEN: v("cfg_wtch_token"),
    },
    TELEGRAM:{
      TELEGRAM_ENABLED:      vc("cfg_tg_enabled"),
      TELEGRAM_BOT_TOKEN:    v("cfg_tg_token"),
      TELEGRAM_CHAT_ID:      v("cfg_tg_chat"),
      TELEGRAM_MIN_INTERVAL: vi("cfg_tg_interval"),
    },
    AUTOMATION:{
      LIBRARY_POLL_INTERVAL: vi("cfg_poll_interval"),
      AUTO_SCAN_SCHEDULE:    v("cfg_auto_scan_schedule"),
    },
    AUTH:{
      AUTH_METHOD:   v("cfg_auth_method"),
      AUTH_USERNAME: v("cfg_auth_username"),
      AUTH_PASSWORD: v("cfg_auth_password"),  // virtual — backend hashes and stores
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
async function triggerWatchtowerUpdate() {
  const el = document.getElementById("wtchStatus")
  if (el) { el.textContent = "Triggering…"; el.style.color = "var(--text3)" }
  try {
    const r = await api("/api/watchtower/update", "POST")
    if (r.ok) {
      if (el) { el.textContent = "✓ Update triggered"; el.style.color = "var(--green)" }
      toast("Watchtower update triggered — new image will pull shortly", "success")
    } else {
      if (el) { el.textContent = `✗ ${r.error||r.status}`; el.style.color = "var(--red)" }
      toast(`Watchtower error: ${r.error||r.status}`, "error")
    }
  } catch(e) {
    if (el) { el.textContent = "✗ Request failed"; el.style.color = "var(--red)" }
    toast("Watchtower request failed", "error")
  }
}
