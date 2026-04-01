/* ============================================================
   api.js — HTTP client, toast notifications, status helpers
============================================================ */

async function api(path, method = "GET", body = null){
  try {
    const opts = { method, headers:{} }
    if (body){ opts.headers["Content-Type"]="application/json"; opts.body=JSON.stringify(body) }
    const r = await fetch(path, opts)

    // Handle non-200 responses
    if (!r.ok) {
      // Try to parse error JSON, fallback to status text
      try {
        const err = await r.json()
        return { ok: false, error: err.error || err.detail || err.message || `HTTP ${r.status}`, status: r.status }
      } catch {
        return { ok: false, error: `HTTP ${r.status}: ${r.statusText}`, status: r.status }
      }
    }

    // HTTP 200 - parse response and preserve backend's ok field if present
    const data = await r.json()
    // If backend explicitly sets ok: false (business logic error), preserve it
    // Otherwise assume success and set ok: true
    return {
      ...data,
      status: r.status,
      ok: data.ok !== undefined ? data.ok : true
    }
  } catch (e) {
    // Network error or other fetch failure
    console.error("API request failed:", e)
    return { ok: false, error: e.message || "Network error", status: 0 }
  }
}

function toast(msg, type = "info"){
  const colors = { info: "#9090a0", success: "#22c55e", error: "#ef4444", gold: "#F5C518" }
  const el = document.createElement("div")
  el.className = `toast ${type}`
  el.innerHTML = `
    <div class="toast-dot" style="background:${colors[type]||colors.info}"></div>
    <span>${msg}</span>`
  document.getElementById("toastContainer").appendChild(el)
  setTimeout(() => {
    el.classList.add("fade-out")
    el.addEventListener("animationend", () => el.remove())
  }, 3000)
}

function setStatus(txt){ document.getElementById("status").textContent = txt }

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

function escHtml(str){
  return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
}