/* ============================================================
   api.js — HTTP client, toast notifications, status helpers
============================================================ */

async function api(path, method = "GET", body = null){
  const opts = { method, headers:{} }
  if (body){ opts.headers["Content-Type"]="application/json"; opts.body=JSON.stringify(body) }
  const r = await fetch(path, opts)
  return r.json()
}

function toast(msg, type = "info"){
  const colors = { info: "#9090a0", success: "#22c55e", error: "#ef4444", gold: "#F5C518" }
  const el = document.createElement("div")
  el.className = `toast ${type}`
  el.innerHTML = `
    <div class="toast-dot" style="background:${colors[type]||colors.info}"></div>
    <span></span>`
  el.querySelector("span").textContent = msg
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