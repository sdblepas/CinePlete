# CinePlete — Standard Test Document (STD)

**Version:** 4.0.3
**Last updated:** 2026-04-07
**Scope:** Full visual and functional QA of the CinePlete web UI
**Executed by:** Automated browser agent (Claude)
**Environment:** Provided by maintainer

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Pass |
| ❌ | Fail |
| ⚠️ | Pass with observation |
| ⏭️ | Skipped (prerequisite not met) |

---

## Prerequisites

Before running the STD, verify:
- CinePlete is running and accessible at the test URL
- At least one media server (Plex / Jellyfin / Emby) is reachable from the instance
- TMDB API key is configured
- At least one library has been scanned successfully

---

## 1 — Configuration

### TC01 — Add Plex library + Test Connection
**Steps:**
1. Navigate to Config tab
2. Click `+ Add Plex`
3. Enter a valid Plex URL, token, and library name
4. Click **Test Connection**

**Expected:** Green ✓ message confirming connection and library found
**Result:** ___

---

### TC02 — Add Jellyfin library + Test Connection
**Steps:**
1. Navigate to Config tab
2. Click `+ Add Jellyfin`
3. Enter a valid Jellyfin URL, API key, and library name
4. Click **Test Connection**

**Expected:** Green ✓ message confirming connection and library found
**Result:** ___

---

### TC03 — Add Emby library + Test Connection
**Steps:**
1. Navigate to Config tab
2. Click `+ Add Emby`
3. Enter a valid Emby URL, API key, and library name
4. Click **Test Connection**

**Expected:** Green ✓ message with EMBY badge (blue `#00A4DC`), library found
**Result:** ___

---

### TC04 — localhost warning on Test Connection
**Steps:**
1. Navigate to Config tab
2. Add any library type
3. Enter `http://localhost:8096` as the URL
4. Enter any API key
5. Click **Test Connection**

**Expected:** Red error message explaining localhost won't work inside Docker, suggesting LAN IP or `host.docker.internal`
**Result:** ___

---

### TC05 — Service badges visible in Config
**Steps:**
1. Navigate to Config tab
2. Scroll through all config sections

**Expected:** Coloured pill badges visible next to each section title:
- `RADARR` (purple)
- `RADARR 4K` (purple)
- `OVERSEERR` (amber)
- `JELLYSEERR` (blue)
- `TELEGRAM` (blue)
- `FLARESOLVERR` (orange)
- `WATCHTOWER` (Docker blue)
- `WEBHOOK` (indigo)

**Result:** ___

---

### TC06 — Config save persists after reload
**Steps:**
1. Navigate to Config tab
2. Change any visible setting (e.g. library label)
3. Click **Save**
4. Hard-reload the page (Ctrl+Shift+R)
5. Navigate back to Config tab

**Expected:** Changed value is still present
**Result:** ___

---

## 2 — Scan

### TC07 — Rescan triggers successfully
**Steps:**
1. Click **⟳ Rescan Library** in the sidebar

**Expected:** Progress card appears at bottom-left, scan state changes to "Scanning…"
**Result:** ___

---

### TC08 — Progress card updates through steps
**Steps:**
1. Trigger a rescan
2. Observe the progress card

**Expected:**
- Step counter increments (e.g. `2/8`, `3/8` …)
- Step label matches current operation
- Progress bar fills proportionally
- Card disappears automatically when scan completes

**Result:** ___

---

### TC09 — Progressive sections appear during scan
**Steps:**
1. Delete `tmdb_cache.json` to force a slow scan (or use a cold environment)
2. Trigger a rescan
3. Navigate between Franchises, Directors, Actors, Classics, Suggestions tabs during scan

**Expected:**
- Tabs not yet computed show shimmer skeleton + "waiting to start…" label
- Active computing tab shows spinner + section name
- Completed tabs show real data without needing a manual refresh
- Previously computed data (from last scan) visible while section recomputes

**Result:** ___

---

### TC10 — Scan complete toast and status update
**Steps:**
1. Trigger a rescan and wait for completion

**Expected:**
- "Scan complete" success toast appears
- Sidebar status updates to `Updated [timestamp]`
- Progress card disappears

**Result:** ___

---

## 3 — Dashboard

### TC11 — Score cards render
**Steps:**
1. Navigate to Dashboard tab after a completed scan

**Expected:** Four score cards visible:
- Franchise Completion %
- Directors Score %
- Classics Coverage %
- Global Cinema Score %

All show numeric values, not zero or NaN
**Result:** ___

---

### TC12 — Charts render
**Steps:**
1. Navigate to Dashboard tab

**Expected:** All six charts render without errors:
- Franchise Status doughnut
- Classics Coverage doughnut
- Metadata Health doughnut
- Top 10 Actors horizontal bar
- Directors by missing films grouped bar
- Library Stats panel

**Result:** ___

---

## 4 — Franchises

### TC13 — Missing franchise films listed
**Steps:**
1. Navigate to Franchises tab

**Expected:** List of incomplete sagas, each showing missing film cards with poster, title, year
**Result:** ___

---

### TC14 — Ignore franchise works
**Steps:**
1. Navigate to Franchises tab
2. Click the 🚫 ignore button on any franchise
3. Confirm the action

**Expected:**
- Franchise disappears from the list immediately
- Franchise chart on Dashboard excludes it
- Franchise appears in Ignored tab

**Result:** ___

---

### TC15 — Completed franchises visible
**Steps:**
1. Navigate to Franchises tab
2. Look for a "Complete ✓" section at the bottom

**Expected:** Collapsed `<details>` section showing franchises where all films are owned,
each displaying franchise name + ✓ N/N badge in green. Clicking the summary expands the grid.
**Result:** ___

---

## 5 — Directors

### TC16 — Directors listed with missing films
**Steps:**
1. Navigate to Directors tab

**Expected:** Directors listed, each showing missing film cards
**Result:** ___

---

### TC17 — Ignore director works
**Steps:**
1. Navigate to Directors tab
2. Click 🚫 on any director

**Expected:** Director disappears from list, appears in Ignored tab
**Result:** ___

---

## 6 — Actors

### TC18 — Actors listed with missing films
**Steps:**
1. Navigate to Actors tab

**Expected:** Actors listed with missing film cards
**Result:** ___

---

### TC19 — "In Your Library" section collapses and expands
**Steps:**
1. Navigate to Actors tab
2. Find an actor with an "In your library" disclosure triangle
3. Click to expand
4. Click to collapse

**Expected:**
- Collapsed by default, showing count
- Expands to show owned films at 45% opacity
- Collapses cleanly

**Result:** ___

---

## 7 — Classics

### TC20 — Classics listed
**Steps:**
1. Navigate to Classics tab

**Expected:** Grid of classic films missing from library, each with poster, title, year, rating
**Result:** ___

---

## 8 — Suggestions

### TC21 — Suggestions listed with ⚡ score badge
**Steps:**
1. Navigate to Suggestions tab

**Expected:** Film cards with ⚡ N badge showing recommendation score
**Result:** ___

---

### TC22 — Suggestion count stable after rescan
**Steps:**
1. Note the suggestion count before rescan
2. Trigger a rescan
3. Wait for scan to complete
4. Check suggestion count

**Expected:** Count remains consistent (within reason — may change slightly if library changed)
**Result:** ___

---

## 9 — Wishlist

### TC23 — Add film to wishlist
**Steps:**
1. Navigate to any tab with film cards (e.g. Franchises)
2. Click the ♥ wishlist button on a film card

**Expected:** Button state changes, toast confirms addition, film appears in Wishlist tab
**Result:** ___

---

### TC24 — Remove film from wishlist
**Steps:**
1. Navigate to Wishlist tab
2. Click the ♥ button on any film to remove it

**Expected:** Film removed immediately, Wishlist badge count decrements
**Result:** ___

---

## 10 — Radarr Integration

### TC25 — Add to Radarr
**Steps:**
1. Ensure Radarr is configured and enabled
2. Navigate to any film card
3. Click **→ Radarr**

**Expected:** Success toast, button state changes to "✓ In Radarr"
**Result:** ___

---

### TC26 — Radarr status badge on Wishlist
**Steps:**
1. Add a film to wishlist that is already in Radarr
2. Navigate to Wishlist tab

**Expected:** "✓ In Radarr" badge visible on the card
**Result:** ___

---

## 11 — Overseerr / Jellyseerr

### TC27 — Request button visible on film cards
**Steps:**
1. Ensure Overseerr or Jellyseerr is configured and enabled
2. Navigate to any tab with film cards

**Expected:** `→ OS` or `→ JS` button visible on eligible cards
**Result:** ___

---

### TC28 — Requested state persists after tab switch and rescan
**Steps:**
1. Click request on a film
2. Navigate to a different tab and back
3. Trigger a rescan
4. Return to the tab with the requested film

**Expected:** Film shows "✓ Requested" state throughout — not reset by navigation or rescan
**Result:** ___

---

## 12 — Letterboxd

### TC29 — Add Letterboxd URL
**Steps:**
1. Navigate to Letterboxd tab
2. Enter a valid public Letterboxd URL
3. Click **Add**

**Expected:** URL saved, films load automatically
**Result:** ___

---

### TC30 — Films load with ×N badge for multi-list overlap
**Steps:**
1. Add two Letterboxd URLs with overlapping films
2. Observe loaded grid

**Expected:** Films appearing in both lists show a ×2 (or higher) badge and sort to the top
**Result:** ___

---

### TC31 — Already-owned films filtered out
**Steps:**
1. Load a Letterboxd list that contains films already in your library

**Expected:** Owned films do not appear in the Letterboxd grid
**Result:** ___

---

## 13 — Authentication

### TC32 — Login page shows in Forms mode
**Steps:**
1. Set Auth Mode to `Always require login` in Config
2. Save config
3. Open a private/incognito browser window
4. Navigate to the CinePlete URL

**Expected:** Login form shown, dashboard not accessible without credentials
**Result:** ___

---

### TC33 — Local network free mode bypass
**Steps:**
1. Set Auth Mode to `Local network free, login from internet`
2. Access from a local IP (192.168.x.x / 10.x.x.x)

**Expected:** Dashboard accessible without login
**Result:** ___

---

## 14 — Accessibility

### TC34 — OpenDyslexic toggle activates
**Steps:**
1. Click the **Dyslexic** button in the topbar (Certified Dyslexic SVG icon)

**Expected:**
- Button gets gold outline ring
- All UI text switches to OpenDyslexic font
- Button label "Dyslexic" also in OpenDyslexic font

**Result:** ___

---

### TC35 — OpenDyslexic toggles off on second press
**Steps:**
1. Click Dyslexic button again

**Expected:** Font reverts to DM Mono / Syne, gold ring disappears
**Result:** ___

---

### TC36 — OpenDyslexic preference persists on reload
**Steps:**
1. Enable OpenDyslexic font
2. Hard-reload the page

**Expected:** Font is still OpenDyslexic after reload, button still shows active state
**Result:** ___

---

## 15 — Logs

### TC37 — Logs tab loads
**Steps:**
1. Navigate to Logs tab

**Expected:** Last 200 lines of log visible, newest at bottom
**Result:** ___

---

### TC38 — Log colour coding
**Steps:**
1. Navigate to Logs tab
2. Look for ERROR and WARNING lines

**Expected:** ERROR lines in red, WARNING lines in amber, INFO lines in default colour
**Result:** ___

---

## 16 — Ignored Items

### TC39 — Ignored items tab shows
**Steps:**
1. Ignore at least one movie (via 🚫 on any film card)
2. Navigate to Ignored tab

**Expected:** Ignored film visible with title, year, poster, and a restore button
**Result:** ___

---

### TC40 — Restore ignored item
**Steps:**
1. Navigate to Ignored tab
2. Click **Restore** on any item

**Expected:** Item disappears from Ignored tab, reappears in its original tab on next render
**Result:** ___

---

## 17 — Theme

### TC41 — Dark/light toggle
**Steps:**
1. Click the 🌙 / ☀️ button in the topbar

**Expected:** Theme switches between dark and light mode across all UI elements
**Result:** ___

---

### TC42 — Theme persists on reload
**Steps:**
1. Switch to light mode
2. Hard-reload the page

**Expected:** Light mode still active after reload
**Result:** ___

---

## 18 — Metadata Diagnostics

### TC43 — No TMDB GUID tab
**Steps:**
1. Navigate to Metadata → No TMDB tab (or equivalent)

**Expected:** List of films without TMDB metadata, showing Plex title
**Result:** ___

---

### TC44 — No Match tab
**Steps:**
1. Navigate to Metadata → No Match tab

**Expected:** List of films with invalid TMDB IDs, showing Plex title for identification
**Result:** ___

---

## 19 — Multi-library

### TC45 — Two libraries scan in parallel
**Steps:**
1. Add two library entries (e.g. Plex + Jellyfin) in Config, both enabled
2. Trigger a rescan
3. Observe scan logs or progress

**Expected:**
- Log shows both libraries being scanned
- Results merged (duplicates flagged)
- Duplicates tab shows shared films

**Result:** ___

---

## Summary Table

| TC | Area | Description | Result |
|----|------|-------------|--------|
| TC01 | Config | Add Plex + Test Connection | ___ |
| TC02 | Config | Add Jellyfin + Test Connection | ___ |
| TC03 | Config | Add Emby + Test Connection | ___ |
| TC04 | Config | localhost warning | ___ |
| TC05 | Config | Service badges visible | ___ |
| TC06 | Config | Save persists after reload | ___ |
| TC07 | Scan | Rescan triggers | ___ |
| TC08 | Scan | Progress card updates | ___ |
| TC09 | Scan | Progressive sections appear | ___ |
| TC10 | Scan | Complete toast + status | ___ |
| TC11 | Dashboard | Score cards | ___ |
| TC12 | Dashboard | Charts | ___ |
| TC13 | Franchises | Missing films listed | ___ |
| TC14 | Franchises | Ignore works | ___ |
| TC15 | Franchises | Completed visible | ___ |
| TC16 | Directors | Listed | ___ |
| TC17 | Directors | Ignore works | ___ |
| TC18 | Actors | Listed | ___ |
| TC19 | Actors | In Your Library collapse | ___ |
| TC20 | Classics | Listed | ___ |
| TC21 | Suggestions | ⚡ score badge | ___ |
| TC22 | Suggestions | Count stable after rescan | ___ |
| TC23 | Wishlist | Add film | ___ |
| TC24 | Wishlist | Remove film | ___ |
| TC25 | Radarr | Add to Radarr | ___ |
| TC26 | Radarr | Status badge on wishlist | ___ |
| TC27 | Overseerr/JS | Request button visible | ___ |
| TC28 | Overseerr/JS | State persists after rescan | ___ |
| TC29 | Letterboxd | Add URL | ___ |
| TC30 | Letterboxd | ×N badge for overlap | ___ |
| TC31 | Letterboxd | Owned filtered out | ___ |
| TC32 | Auth | Login page in Forms mode | ___ |
| TC33 | Auth | Local network bypass | ___ |
| TC34 | A11y | OpenDyslexic activates | ___ |
| TC35 | A11y | OpenDyslexic toggles off | ___ |
| TC36 | A11y | Preference persists on reload | ___ |
| TC37 | Logs | Logs tab loads | ___ |
| TC38 | Logs | Colour coding | ___ |
| TC39 | Ignored | Tab shows | ___ |
| TC40 | Ignored | Restore works | ___ |
| TC41 | Theme | Toggle works | ___ |
| TC42 | Theme | Persists on reload | ___ |
| TC43 | Metadata | No TMDB GUID tab | ___ |
| TC44 | Metadata | No Match tab | ___ |
| TC45 | Multi-lib | Two libraries parallel scan | ___ |

---

*45 test cases — TC15 known pending (completed franchises feature on backlog)*
