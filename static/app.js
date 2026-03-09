let DATA = null;
let ACTIVE_TAB = "dashboard";

const statusEl = () => document.getElementById("status");

function yearBucket(y) {
  const year = parseInt(y || "0", 10);
  if (!year) return "";
  if (year >= 2020) return "2020s";
  if (year >= 2010) return "2010s";
  if (year >= 2000) return "2000s";
  if (year >= 1990) return "1990s";
  return "older";
}

function scorePill(label, value) {
  return `
    <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
      <div class="text-sm text-zinc-400">${label}</div>
      <div class="text-2xl font-semibold">${value}%</div>
    </div>
  `;
}

function pill(text) {
  return `<span class="text-xs px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-200">${text}</span>`;
}

function movieCard(m) {
  const poster = m.poster
    ? `<img src="${m.poster}" class="w-24 h-36 object-cover rounded bg-zinc-800" />`
    : `<div class="w-24 h-36 rounded bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">No poster</div>`;

  const wishLabel = m.wishlist ? "In wishlist" : "Wishlist";

  return `
    <div class="flex gap-3 bg-zinc-900 border border-zinc-800 rounded p-3">
      ${poster}
      <div class="flex-1">
        <div class="font-semibold">
          ${m.title || "Untitled"}
          ${m.year ? `<span class="text-zinc-400 font-normal">(${m.year})</span>` : ""}
        </div>

        <div class="text-xs text-zinc-400 mt-1 flex flex-wrap gap-2">
          ${m.tmdb ? pill(`tmdb:${m.tmdb}`) : ""}
          ${pill(`pop ${Math.round(m.popularity || 0)}`)}
          ${pill(`⭐ ${m.rating || 0}`)}
          ${pill(`votes ${m.votes || 0}`)}
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          ${m.tmdb ? `<button class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" onclick="ignoreMovie(${m.tmdb})">Ignore</button>` : ""}
          ${m.tmdb ? `<button class="px-2 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold" onclick="wishlistAdd(${m.tmdb})">${wishLabel}</button>` : ""}
          ${m.tmdb ? `<button class="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-black text-sm font-semibold" onclick="radarrAdd(${m.tmdb}, ${JSON.stringify(m.title || "")})">Add to Radarr</button>` : ""}
          ${m.tmdb ? `<a class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" target="_blank" href="https://www.themoviedb.org/movie/${m.tmdb}">TMDB</a>` : ""}
        </div>
      </div>
    </div>
  `;
}

function simpleRow(item) {
  // for No TMDB GUID list
  const title = item.title || "Untitled";
  const year = item.year ? `(${item.year})` : "";
  return `
    <div class="bg-zinc-900 border border-zinc-800 rounded p-3 flex items-center justify-between">
      <div class="font-semibold">${title} <span class="text-zinc-400 font-normal">${year}</span></div>
      <div class="text-xs text-zinc-400">Fix Match in Plex</div>
    </div>
  `;
}

function tmdbIdRow(item) {
  // for TMDB No Match list
  return `
    <div class="bg-zinc-900 border border-zinc-800 rounded p-3 flex items-center justify-between">
      <div class="font-semibold">tmdb:${item.tmdb}</div>
      <a class="text-sm px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" target="_blank"
         href="https://www.themoviedb.org/movie/${item.tmdb}">Open TMDB</a>
    </div>
  `;
}

function filterAndSortMovies(list) {
  const q = (document.getElementById("search").value || "").toLowerCase().trim();
  const yF = document.getElementById("yearFilter").value;
  const sort = document.getElementById("sort").value;

  let out = (list || []).filter(m => {
    const s = `${m.title || ""}`.toLowerCase();
    if (q && !s.includes(q)) return false;
    if (yF && yearBucket(m.year) !== yF) return false;
    return true;
  });

  const key = {
    popularity: (m) => (m.popularity || 0),
    rating: (m) => (m.rating || 0),
    votes: (m) => (m.votes || 0),
    year: (m) => parseInt(m.year || "0", 10),
    title: (m) => (m.title || "").toLowerCase()
  }[sort];

  out.sort((a, b) => {
    const av = key(a), bv = key(b);
    if (typeof av === "string") return av.localeCompare(bv);
    return (bv - av);
  });

  return out;
}

async function api(path, method="GET", body=null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  return await r.json();
}

async function loadResults() {
  statusEl().textContent = "Loading…";
  DATA = await api("/api/results");
  statusEl().textContent = `Loaded • ${DATA.generated_at}`;
  render();
}

async function rescan() {
  statusEl().textContent = "Scanning…";
  DATA = await api("/api/scan", "POST");
  statusEl().textContent = `Rescanned • ${DATA.generated_at}`;
  render();
}

async function ignoreMovie(tmdb) {
  await api("/api/ignore", "POST", { kind: "movie", value: tmdb });
  await rescan();
}

async function ignoreGroup(kind, value) {
  await api("/api/ignore", "POST", { kind, value });
  await rescan();
}

async function wishlistAdd(tmdb) {
  await api("/api/wishlist/add", "POST", { tmdb });
  await rescan();
}

async function wishlistRemove(tmdb) {
  await api("/api/wishlist/remove", "POST", { tmdb });
  await rescan();
}

async function radarrAdd(tmdb, title) {
  const res = await api("/api/radarr/add", "POST", { tmdb, title });
  if (!res.ok) alert(`Radarr: ${res.error || res.status || "failed"}`);
  else alert("Added to Radarr (no search/download).");
}

function renderDashboard() {
  const c = document.getElementById("content");
  const s = DATA.scores || {};
  const p = DATA.plex || {};

  c.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      ${scorePill("Franchise completion", s.franchise_completion_pct ?? 0)}
      ${scorePill("Directors score (proxy)", s.directors_proxy_pct ?? 0)}
      ${scorePill("Classics coverage (proxy)", s.classics_proxy_pct ?? 0)}
      ${scorePill("Global cinema score", s.global_cinema_score ?? 0)}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
        <div class="font-semibold mb-2">Plex stats</div>
        <div class="text-sm text-zinc-300 space-y-1">
          <div>Scanned items: <b>${p.scanned_items ?? 0}</b></div>
          <div>Indexed TMDB: <b>${p.indexed_tmdb ?? 0}</b></div>
          <div>Shorts skipped: <b>${p.skipped_short ?? 0}</b></div>
          <div>No TMDB GUID: <b>${p.no_tmdb_guid ?? 0}</b></div>
          <div>Directors kept: <b>${p.directors_kept ?? 0}</b></div>
          <div>Actors kept: <b>${p.actors_kept ?? 0}</b></div>
        </div>
      </div>

      <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
        <div class="font-semibold mb-2">Sagas completion (top 30)</div>
        <canvas id="sagaChart" height="120"></canvas>
      </div>

      <div class="bg-zinc-900 border border-zinc-800 rounded p-4 lg:col-span-2">
        <div class="font-semibold mb-2">Actor heatmap (top 40)</div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2" id="heat"></div>
      </div>
    </div>
  `;

  const saga = (DATA.charts && DATA.charts.franchise_completion) ? DATA.charts.franchise_completion : [];
  const labels = saga.map(x => x.name);
  const values = saga.map(x => Math.round((x.have / x.total) * 100));

  const ctx = document.getElementById("sagaChart");
  if (ctx) {
    new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label: "Completion %", data: values }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100 } } }
    });
  }

  const heat = document.getElementById("heat");
  const actors = (DATA.charts && DATA.charts.top_actors) ? DATA.charts.top_actors : [];
  if (heat) {
    heat.innerHTML = actors.map(a => `
      <div class="rounded px-2 py-2 border border-zinc-800 bg-zinc-900">
        <div class="text-xs text-zinc-200 truncate" title="${a.name}">${a.name}</div>
        <div class="text-xs text-zinc-400">${a.count}</div>
      </div>
    `).join("");
  }
}

function renderGroups(groups, kind) {
  const c = document.getElementById("content");
  const q = (document.getElementById("search").value || "").toLowerCase().trim();

  const filtered = (groups || []).filter(g => {
    if (!q) return true;
    return (g.name || "").toLowerCase().includes(q);
  });

  c.innerHTML = filtered.map(g => {
    const movies = filterAndSortMovies(g.missing || []);
    return `
      <div class="mb-6">
        <div class="flex items-center justify-between mb-2">
          <div class="text-lg font-semibold">
            ${g.name}
            ${g.have !== undefined ? `<span class="text-zinc-400 font-normal">(${g.have}/${g.total})</span>` : ""}
          </div>
          <button class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm"
                  onclick='ignoreGroup("${kind}", ${JSON.stringify(g.name)})'>Ignore ${kind}</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          ${movies.map(movieCard).join("") || `<div class="text-sm text-zinc-400">Nothing missing 🎉</div>`}
        </div>
      </div>
    `;
  }).join("");
}

function renderMovieList(list, title, isWishlist=false) {
  const c = document.getElementById("content");
  const movies = filterAndSortMovies(list || []);

  c.innerHTML = `
    <div class="text-xl font-semibold mb-4">${title} <span class="text-zinc-400 font-normal">(${movies.length})</span></div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      ${movies.map(m => {
        if (!isWishlist) return movieCard(m);
        // Wishlist: replace action with Remove
        const poster = m.poster
          ? `<img src="${m.poster}" class="w-24 h-36 object-cover rounded bg-zinc-800" />`
          : `<div class="w-24 h-36 rounded bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">No poster</div>`;
        return `
          <div class="flex gap-3 bg-zinc-900 border border-zinc-800 rounded p-3">
            ${poster}
            <div class="flex-1">
              <div class="font-semibold">
                ${m.title || "Untitled"} ${m.year ? `<span class="text-zinc-400 font-normal">(${m.year})</span>` : ""}
              </div>
              <div class="text-xs text-zinc-400 mt-1 flex flex-wrap gap-2">
                ${m.tmdb ? pill(`tmdb:${m.tmdb}`) : ""}
                ${pill(`pop ${Math.round(m.popularity || 0)}`)}
                ${pill(`⭐ ${m.rating || 0}`)}
                ${pill(`votes ${m.votes || 0}`)}
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button class="px-2 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold" onclick="wishlistRemove(${m.tmdb})">Remove</button>
                <button class="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-black text-sm font-semibold" onclick="radarrAdd(${m.tmdb}, ${JSON.stringify(m.title || "")})">Add to Radarr</button>
                <a class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" target="_blank" href="https://www.themoviedb.org/movie/${m.tmdb}">TMDB</a>
              </div>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderNoTmdbGuid() {
  const c = document.getElementById("content");
  const q = (document.getElementById("search").value || "").toLowerCase().trim();
  const yF = document.getElementById("yearFilter").value;
  const sort = document.getElementById("sort").value;

  let items = (DATA.no_tmdb_guid || []).filter(x => {
    const s = `${x.title || ""}`.toLowerCase();
    if (q && !s.includes(q)) return false;
    if (yF && yearBucket(x.year) !== yF) return false;
    return true;
  });

  items.sort((a, b) => {
    if (sort === "year") return (parseInt(b.year || "0", 10) - parseInt(a.year || "0", 10));
    return `${a.title || ""}`.toLowerCase().localeCompare(`${b.title || ""}`.toLowerCase());
  });

  c.innerHTML = `
    <div class="text-xl font-semibold mb-4">No TMDB GUID <span class="text-zinc-400 font-normal">(${items.length})</span></div>
    <div class="space-y-2">
      ${items.map(simpleRow).join("") || `<div class="text-sm text-zinc-400">None 🎉</div>`}
    </div>
    <div class="mt-4 text-sm text-zinc-400">
      In Plex: open the movie → <b>Fix Match</b> → choose <b>TheMovieDB</b>.
    </div>
  `;
}

function renderNoMatch() {
  const c = document.getElementById("content");
  const q = (document.getElementById("search").value || "").toLowerCase().trim();

  let items = (DATA.tmdb_not_found || []).filter(x => {
    const s = `tmdb:${x.tmdb}`.toLowerCase();
    if (q && !s.includes(q)) return false;
    return true;
  });

  c.innerHTML = `
    <div class="text-xl font-semibold mb-4">TMDB No Match <span class="text-zinc-400 font-normal">(${items.length})</span></div>
    <div class="space-y-2">
      ${items.map(tmdbIdRow).join("") || `<div class="text-sm text-zinc-400">None 🎉</div>`}
    </div>
    <div class="mt-4 text-sm text-zinc-400">
      Usually fixed by <b>Refresh Metadata</b> or <b>Fix Match</b> in Plex (bad/obsolete TMDB id).
    </div>
  `;
}

function render() {
  if (!DATA) return;

  if (ACTIVE_TAB === "dashboard") return renderDashboard();

  if (ACTIVE_TAB === "notmdb") return renderNoTmdbGuid();
  if (ACTIVE_TAB === "nomatch") return renderNoMatch();

  if (ACTIVE_TAB === "franchises") return renderGroups(DATA.franchises || [], "franchise");
  if (ACTIVE_TAB === "directors") return renderGroups(DATA.directors || [], "director");
  if (ACTIVE_TAB === "actors") return renderGroups(DATA.actors || [], "actor");

  if (ACTIVE_TAB === "classics") return renderMovieList(DATA.classics || [], "Classics (Top Rated)");
  if (ACTIVE_TAB === "suggestions") return renderMovieList(DATA.suggestions || [], "Suggestions TMDB");
  if (ACTIVE_TAB === "wishlist") return renderMovieList(DATA.wishlist || [], "Wishlist", true);
}

function setActiveTab(tab) {
  ACTIVE_TAB = tab;
  document.querySelectorAll(".nav").forEach(b => b.classList.remove("bg-zinc-800"));
  document.querySelector(`.nav[data-tab="${tab}"]`)?.classList.add("bg-zinc-800");
  render();
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".nav");
  if (!btn) return;
  setActiveTab(btn.dataset.tab);
});

document.getElementById("scanBtn").addEventListener("click", rescan);
document.getElementById("search").addEventListener("input", render);
document.getElementById("yearFilter").addEventListener("change", render);
document.getElementById("sort").addEventListener("change", render);

// boot
loadResults();let DATA = null;
let ACTIVE_TAB = "dashboard";
let CONFIG = null;
let CONFIGURED = false;

const statusEl = () => document.getElementById("status");
const topFilters = () => document.getElementById("topFilters");

function yearBucket(y) {
  const year = parseInt(y || "0", 10);
  if (!year) return "";
  if (year >= 2020) return "2020s";
  if (year >= 2010) return "2010s";
  if (year >= 2000) return "2000s";
  if (year >= 1990) return "1990s";
  return "older";
}

function scorePill(label, value) {
  return `
    <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
      <div class="text-sm text-zinc-400">${label}</div>
      <div class="text-2xl font-semibold">${value}%</div>
    </div>
  `;
}

function pill(text) {
  return `<span class="text-xs px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-zinc-200">${text}</span>`;
}

function movieCard(m) {
  const poster = m.poster
    ? `<img src="${m.poster}" class="w-24 h-36 object-cover rounded bg-zinc-800" />`
    : `<div class="w-24 h-36 rounded bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">No poster</div>`;

  const wishLabel = m.wishlist ? "In wishlist" : "Wishlist";

  return `
    <div class="flex gap-3 bg-zinc-900 border border-zinc-800 rounded p-3">
      ${poster}
      <div class="flex-1">
        <div class="font-semibold">
          ${m.title || "Untitled"}
          ${m.year ? `<span class="text-zinc-400 font-normal">(${m.year})</span>` : ""}
        </div>

        <div class="text-xs text-zinc-400 mt-1 flex flex-wrap gap-2">
          ${m.tmdb ? pill(`tmdb:${m.tmdb}`) : ""}
          ${pill(`pop ${Math.round(m.popularity || 0)}`)}
          ${pill(`⭐ ${m.rating || 0}`)}
          ${pill(`votes ${m.votes || 0}`)}
        </div>

        <div class="mt-3 flex flex-wrap gap-2">
          ${m.tmdb ? `<button class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" onclick="ignoreMovie(${m.tmdb})">Ignore</button>` : ""}
          ${m.tmdb ? `<button class="px-2 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold" onclick="wishlistAdd(${m.tmdb})">${wishLabel}</button>` : ""}
          ${m.tmdb ? `<button class="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-black text-sm font-semibold" onclick="radarrAdd(${m.tmdb}, ${JSON.stringify(m.title || "")})">Add to Radarr</button>` : ""}
          ${m.tmdb ? `<a class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" target="_blank" href="https://www.themoviedb.org/movie/${m.tmdb}">TMDB</a>` : ""}
        </div>
      </div>
    </div>
  `;
}

function simpleRow(item) {
  const title = item.title || "Untitled";
  const year = item.year ? `(${item.year})` : "";
  return `
    <div class="bg-zinc-900 border border-zinc-800 rounded p-3 flex items-center justify-between">
      <div class="font-semibold">${title} <span class="text-zinc-400 font-normal">${year}</span></div>
      <div class="text-xs text-zinc-400">Fix Match in Plex</div>
    </div>
  `;
}

function tmdbIdRow(item) {
  return `
    <div class="bg-zinc-900 border border-zinc-800 rounded p-3 flex items-center justify-between">
      <div class="font-semibold">tmdb:${item.tmdb}</div>
      <a class="text-sm px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" target="_blank"
         href="https://www.themoviedb.org/movie/${item.tmdb}">Open TMDB</a>
    </div>
  `;
}

function filterAndSortMovies(list) {
  const q = (document.getElementById("search").value || "").toLowerCase().trim();
  const yF = document.getElementById("yearFilter").value;
  const sort = document.getElementById("sort").value;

  let out = (list || []).filter(m => {
    const s = `${m.title || ""}`.toLowerCase();
    if (q && !s.includes(q)) return false;
    if (yF && yearBucket(m.year) !== yF) return false;
    return true;
  });

  const key = {
    popularity: (m) => (m.popularity || 0),
    rating: (m) => (m.rating || 0),
    votes: (m) => (m.votes || 0),
    year: (m) => parseInt(m.year || "0", 10),
    title: (m) => (m.title || "").toLowerCase()
  }[sort];

  out.sort((a, b) => {
    const av = key(a), bv = key(b);
    if (typeof av === "string") return av.localeCompare(bv);
    return (bv - av);
  });

  return out;
}

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const r = await fetch(path, opts);
  return await r.json();
}

async function loadConfig() {
  CONFIG = await api("/api/config");
}

async function loadStatus() {
  const s = await api("/api/config/status");
  CONFIGURED = !!s.configured;
}

async function loadResults() {
  statusEl().textContent = "Loading…";
  DATA = await api("/api/results");
  statusEl().textContent = DATA.generated_at ? `Loaded • ${DATA.generated_at}` : "Ready";
  render();
}

async function rescan() {
  if (!CONFIGURED) {
    alert("Complete setup first.");
    return;
  }

  statusEl().textContent = "Scanning…";
  DATA = await api("/api/scan", "POST");
  statusEl().textContent = `Rescanned • ${DATA.generated_at}`;
  render();
}

async function ignoreMovie(tmdb) {
  await api("/api/ignore", "POST", { kind: "movie", value: tmdb });
  await rescan();
}

async function ignoreGroup(kind, value) {
  await api("/api/ignore", "POST", { kind, value });
  await rescan();
}

async function wishlistAdd(tmdb) {
  await api("/api/wishlist/add", "POST", { tmdb });
  await rescan();
}

async function wishlistRemove(tmdb) {
  await api("/api/wishlist/remove", "POST", { tmdb });
  await rescan();
}

async function radarrAdd(tmdb, title) {
  const res = await api("/api/radarr/add", "POST", { tmdb, title });
  if (!res.ok) alert(`Radarr: ${res.error || "failed"}`);
  else alert("Added to Radarr (no search/download).");
}

function renderDashboard() {
  const c = document.getElementById("content");
  const s = DATA.scores || {};
  const p = DATA.plex || {};

  c.innerHTML = `
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
      ${scorePill("Franchise completion", s.franchise_completion_pct ?? 0)}
      ${scorePill("Directors score (proxy)", s.directors_proxy_pct ?? 0)}
      ${scorePill("Classics coverage (proxy)", s.classics_proxy_pct ?? 0)}
      ${scorePill("Global cinema score", s.global_cinema_score ?? 0)}
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
        <div class="font-semibold mb-2">Plex stats</div>
        <div class="text-sm text-zinc-300 space-y-1">
          <div>Scanned items: <b>${p.scanned_items ?? 0}</b></div>
          <div>Indexed TMDB: <b>${p.indexed_tmdb ?? 0}</b></div>
          <div>Shorts skipped: <b>${p.skipped_short ?? 0}</b></div>
          <div>No TMDB GUID: <b>${p.no_tmdb_guid ?? 0}</b></div>
          <div>Directors kept: <b>${p.directors_kept ?? 0}</b></div>
          <div>Actors kept: <b>${p.actors_kept ?? 0}</b></div>
        </div>
      </div>

      <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
        <div class="font-semibold mb-2">Sagas completion (top 30)</div>
        <canvas id="sagaChart" height="120"></canvas>
      </div>

      <div class="bg-zinc-900 border border-zinc-800 rounded p-4 lg:col-span-2">
        <div class="font-semibold mb-2">Actor heatmap (top 40)</div>
        <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2" id="heat"></div>
      </div>
    </div>
  `;

  const saga = (DATA.charts && DATA.charts.franchise_completion) ? DATA.charts.franchise_completion : [];
  const labels = saga.map(x => x.name);
  const values = saga.map(x => Math.round((x.have / x.total) * 100));

  const ctx = document.getElementById("sagaChart");
  if (ctx) {
    new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label: "Completion %", data: values }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100 } } }
    });
  }

  const heat = document.getElementById("heat");
  const actors = (DATA.charts && DATA.charts.top_actors) ? DATA.charts.top_actors : [];
  if (heat) {
    heat.innerHTML = actors.map(a => `
      <div class="rounded px-2 py-2 border border-zinc-800 bg-zinc-900">
        <div class="text-xs text-zinc-200 truncate" title="${a.name}">${a.name}</div>
        <div class="text-xs text-zinc-400">${a.count}</div>
      </div>
    `).join("");
  }
}

function renderGroups(groups, kind) {
  const c = document.getElementById("content");
  const q = (document.getElementById("search").value || "").toLowerCase().trim();

  const filtered = (groups || []).filter(g => {
    if (!q) return true;
    return (g.name || "").toLowerCase().includes(q);
  });

  c.innerHTML = filtered.map(g => {
    const movies = filterAndSortMovies(g.missing || []);
    return `
      <div class="mb-6">
        <div class="flex items-center justify-between mb-2">
          <div class="text-lg font-semibold">
            ${g.name}
            ${g.have !== undefined ? `<span class="text-zinc-400 font-normal">(${g.have}/${g.total})</span>` : ""}
          </div>
          <button class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm"
                  onclick='ignoreGroup("${kind}", ${JSON.stringify(g.name)})'>Ignore ${kind}</button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          ${movies.map(movieCard).join("") || `<div class="text-sm text-zinc-400">Nothing missing 🎉</div>`}
        </div>
      </div>
    `;
  }).join("");
}

function renderMovieList(list, title, isWishlist = false) {
  const c = document.getElementById("content");
  const movies = filterAndSortMovies(list || []);

  c.innerHTML = `
    <div class="text-xl font-semibold mb-4">${title} <span class="text-zinc-400 font-normal">(${movies.length})</span></div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      ${movies.map(m => {
        if (!isWishlist) return movieCard(m);

        const poster = m.poster
          ? `<img src="${m.poster}" class="w-24 h-36 object-cover rounded bg-zinc-800" />`
          : `<div class="w-24 h-36 rounded bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">No poster</div>`;

        return `
          <div class="flex gap-3 bg-zinc-900 border border-zinc-800 rounded p-3">
            ${poster}
            <div class="flex-1">
              <div class="font-semibold">
                ${m.title || "Untitled"} ${m.year ? `<span class="text-zinc-400 font-normal">(${m.year})</span>` : ""}
              </div>
              <div class="text-xs text-zinc-400 mt-1 flex flex-wrap gap-2">
                ${m.tmdb ? pill(`tmdb:${m.tmdb}`) : ""}
                ${pill(`pop ${Math.round(m.popularity || 0)}`)}
                ${pill(`⭐ ${m.rating || 0}`)}
                ${pill(`votes ${m.votes || 0}`)}
              </div>
              <div class="mt-3 flex flex-wrap gap-2">
                <button class="px-2 py-1 rounded bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold" onclick="wishlistRemove(${m.tmdb})">Remove</button>
                <button class="px-2 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-black text-sm font-semibold" onclick="radarrAdd(${m.tmdb}, ${JSON.stringify(m.title || "")})">Add to Radarr</button>
                <a class="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-sm" target="_blank" href="https://www.themoviedb.org/movie/${m.tmdb}">TMDB</a>
              </div>
            </div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}

function renderNoTmdbGuid() {
  const c = document.getElementById("content");
  const q = (document.getElementById("search").value || "").toLowerCase().trim();
  const yF = document.getElementById("yearFilter").value;
  const sort = document.getElementById("sort").value;

  let items = (DATA.no_tmdb_guid || []).filter(x => {
    const s = `${x.title || ""}`.toLowerCase();
    if (q && !s.includes(q)) return false;
    if (yF && yearBucket(x.year) !== yF) return false;
    return true;
  });

  items.sort((a, b) => {
    if (sort === "year") return (parseInt(b.year || "0", 10) - parseInt(a.year || "0", 10));
    return `${a.title || ""}`.toLowerCase().localeCompare(`${b.title || ""}`.toLowerCase());
  });

  c.innerHTML = `
    <div class="text-xl font-semibold mb-4">No TMDB GUID <span class="text-zinc-400 font-normal">(${items.length})</span></div>
    <div class="space-y-2">
      ${items.map(simpleRow).join("") || `<div class="text-sm text-zinc-400">None 🎉</div>`}
    </div>
    <div class="mt-4 text-sm text-zinc-400">
      In Plex: open the movie → <b>Fix Match</b> → choose <b>TheMovieDB</b>.
    </div>
  `;
}

function renderNoMatch() {
  const c = document.getElementById("content");
  const q = (document.getElementById("search").value || "").toLowerCase().trim();

  let items = (DATA.tmdb_not_found || []).filter(x => {
    const s = `tmdb:${x.tmdb}`.toLowerCase();
    if (q && !s.includes(q)) return false;
    return true;
  });

  c.innerHTML = `
    <div class="text-xl font-semibold mb-4">TMDB No Match <span class="text-zinc-400 font-normal">(${items.length})</span></div>
    <div class="space-y-2">
      ${items.map(tmdbIdRow).join("") || `<div class="text-sm text-zinc-400">None 🎉</div>`}
    </div>
    <div class="mt-4 text-sm text-zinc-400">
      Usually fixed by <b>Refresh Metadata</b> or <b>Fix Match</b> in Plex.
    </div>
  `;
}

function getConfigField(path) {
  const [section, key] = path.split(".");
  return CONFIG?.[section]?.[key];
}

function renderConfig() {
  const c = document.getElementById("content");

  const configField = (label, path, type = "text") => `
    <label class="block mb-4">
      <div class="text-sm text-zinc-300 mb-1">${label}</div>
      <input data-config="${path}" type="${type}" value="${getConfigField(path) ?? ""}"
             class="w-full bg-zinc-900 border border-zinc-800 rounded px-3 py-2" />
    </label>
  `;

  const boolField = (label, path) => `
    <label class="flex items-center gap-3 mb-4">
      <input data-config="${path}" type="checkbox" ${getConfigField(path) ? "checked" : ""} />
      <span class="text-sm text-zinc-300">${label}</span>
    </label>
  `;

  c.innerHTML = `
    <div class="max-w-4xl">
      <div class="text-2xl font-semibold mb-4">${CONFIGURED ? "Config" : "Setup Wizard"}</div>
      <div class="text-sm text-zinc-400 mb-6">
        ${CONFIGURED ? "Edit your saved configuration. Values persist across updates." : "Fill the required settings to initialize the application."}
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
          <div class="font-semibold mb-4">Server</div>
          ${configField("UI Port", "SERVER.UI_PORT", "number")}
          ${configField("Timezone", "SERVER.TZ")}
        </div>

        <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
          <div class="font-semibold mb-4">Plex</div>
          ${configField("Plex URL", "PLEX.PLEX_URL")}
          ${configField("Plex Token", "PLEX.PLEX_TOKEN")}
          ${configField("Library Name", "PLEX.LIBRARY_NAME")}
          ${configField("Plex Page Size", "PLEX.PLEX_PAGE_SIZE", "number")}
          ${configField("Short Movie Limit (min)", "PLEX.SHORT_MOVIE_LIMIT", "number")}
        </div>

        <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
          <div class="font-semibold mb-4">TMDB</div>
          ${configField("TMDB API Key", "TMDB.TMDB_API_KEY")}
          ${configField("TMDB Min Delay", "TMDB.TMDB_MIN_DELAY", "number")}
        </div>

        <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
          <div class="font-semibold mb-4">Classics / Suggestions</div>
          ${configField("Pages", "CLASSICS.CLASSICS_PAGES", "number")}
          ${configField("Min Votes", "CLASSICS.CLASSICS_MIN_VOTES", "number")}
          ${configField("Min Rating", "CLASSICS.CLASSICS_MIN_RATING", "number")}
          ${configField("Max Results", "CLASSICS.CLASSICS_MAX_RESULTS", "number")}
        </div>

        <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
          <div class="font-semibold mb-4">Actor Hits</div>
          ${configField("Min Votes", "ACTOR_HITS.ACTOR_MIN_VOTES", "number")}
          ${configField("Max Results per Actor", "ACTOR_HITS.ACTOR_MAX_RESULTS_PER_ACTOR", "number")}
        </div>

        <div class="bg-zinc-900 border border-zinc-800 rounded p-4">
          <div class="font-semibold mb-4">Radarr</div>
          ${boolField("Enable Radarr", "RADARR.RADARR_ENABLED")}
          ${configField("Radarr URL", "RADARR.RADARR_URL")}
          ${configField("Radarr API Key", "RADARR.RADARR_API_KEY")}
          ${configField("Root Folder Path", "RADARR.RADARR_ROOT_FOLDER_PATH")}
          ${configField("Quality Profile ID", "RADARR.RADARR_QUALITY_PROFILE_ID", "number")}
          ${boolField("Monitored", "RADARR.RADARR_MONITORED")}
        </div>
      </div>

      <div class="mt-6">
        <button onclick="saveConfig()" class="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-black font-semibold">
          Save Configuration
        </button>
      </div>
    </div>
  `;
}

async function saveConfig() {
  const next = structuredClone(CONFIG || {});

  document.querySelectorAll("[data-config]").forEach(el => {
    const [section, key] = el.dataset.config.split(".");
    next[section] = next[section] || {};

    if (el.type === "checkbox") {
      next[section][key] = el.checked;
    } else if (el.type === "number") {
      const val = el.value;
      next[section][key] = val === "" ? "" : Number(val);
    } else {
      next[section][key] = el.value;
    }
  });

  const res = await api("/api/config", "POST", next);
  if (!res.ok) {
    alert("Failed to save configuration");
    return;
  }

  await loadConfig();
  await loadStatus();

  if (CONFIGURED) {
    DATA = await api("/api/results");
    ACTIVE_TAB = "dashboard";
  }

  render();
  alert("Configuration saved");
}

function render() {
  if (!CONFIGURED) {
    topFilters().style.display = "none";
    ACTIVE_TAB = "config";
    return renderConfig();
  }

  topFilters().style.display = (ACTIVE_TAB === "config") ? "none" : "flex";

  if (ACTIVE_TAB === "config") return renderConfig();
  if (!DATA) return;

  if (ACTIVE_TAB === "dashboard") return renderDashboard();
  if (ACTIVE_TAB === "notmdb") return renderNoTmdbGuid();
  if (ACTIVE_TAB === "nomatch") return renderNoMatch();
  if (ACTIVE_TAB === "franchises") return renderGroups(DATA.franchises || [], "franchise");
  if (ACTIVE_TAB === "directors") return renderGroups(DATA.directors || [], "director");
  if (ACTIVE_TAB === "actors") return renderGroups(DATA.actors || [], "actor");
  if (ACTIVE_TAB === "classics") return renderMovieList(DATA.classics || [], "Classics (Top Rated)");
  if (ACTIVE_TAB === "suggestions") return renderMovieList(DATA.suggestions || [], "Suggestions TMDB");
  if (ACTIVE_TAB === "wishlist") return renderMovieList(DATA.wishlist || [], "Wishlist", true);
}

function setActiveTab(tab) {
  ACTIVE_TAB = tab;
  document.querySelectorAll(".nav").forEach(b => b.classList.remove("bg-zinc-800"));
  document.querySelector(`.nav[data-tab="${tab}"]`)?.classList.add("bg-zinc-800");
  render();
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest(".nav");
  if (!btn) return;
  setActiveTab(btn.dataset.tab);
});

document.getElementById("scanBtn").addEventListener("click", rescan);
document.getElementById("search").addEventListener("input", render);
document.getElementById("yearFilter").addEventListener("change", render);
document.getElementById("sort").addEventListener("change", render);

async function boot() {
  await loadConfig();
  await loadStatus();

  if (CONFIGURED) {
    await loadResults();
  } else {
    statusEl().textContent = "Setup required";
    render();
  }
}

boot();