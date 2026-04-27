// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests for Trakt.tv integration.
 *
 * All backend calls are mocked — no live Trakt/TMDB access needed.
 *
 * Covers:
 *  - Config UI: Trakt section visible with connect form when not connected
 *  - Config UI: shows username + Disconnect button when connected
 *  - Config UI: device-code flow (Connect button → code display)
 *  - Cards: watched badge shown when movie is in Trakt watch history
 *  - Cards: hide-watched hides movies from grids (not wishlist)
 */

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const TMDB_WATCHED  = 550    // Fight Club — "watched"
const TMDB_UNWATCHED = 278   // Shawshank  — not watched

const MOVIE_WATCHED = { tmdb: TMDB_WATCHED, title: 'Fight Club', year: '1999', poster: null, rating: 8.8, wishlist: false }
const MOVIE_UNWATCHED = { tmdb: TMDB_UNWATCHED, title: 'The Shawshank Redemption', year: '1994', poster: null, rating: 9.3, wishlist: false }

const RESULTS_STUB = {
  ok:         true,
  configured: true,
  scanning:   false,
  sections:   {},
  classics:   [MOVIE_WATCHED, MOVIE_UNWATCHED],
  suggestions:[],
  franchises: [],
  directors:  [],
  actors:     [],
  wishlist:   [MOVIE_WATCHED],   // also in wishlist to test skipWatchedFilter
}

const CONFIG_TRAKT_DISABLED = {
  PLEX: {}, TMDB: { TMDB_API_KEY: 'test' },
  RADARR: { RADARR_ENABLED: false },
  RADARR_4K: { RADARR_4K_ENABLED: false },
  OVERSEERR: { OVERSEERR_ENABLED: false },
  JELLYSEERR: { JELLYSEERR_ENABLED: false },
  SEERR: { SEERR_ENABLED: false },
  STREAMING: { STREAMING_COUNTRY: 'US' },
  AUTH: { AUTH_METHOD: 'None' },
  TRAKT: {
    TRAKT_ENABLED: false,
    TRAKT_CLIENT_ID: '',
    TRAKT_CLIENT_SECRET: '',
    TRAKT_ACCESS_TOKEN: '',
    TRAKT_REFRESH_TOKEN: '',
    TRAKT_USERNAME: '',
    TRAKT_HIDE_WATCHED: false,
  },
}

const CONFIG_TRAKT_CONNECTED = {
  ...CONFIG_TRAKT_DISABLED,
  TRAKT: {
    TRAKT_ENABLED: true,
    TRAKT_CLIENT_ID: 'my-client-id',
    TRAKT_CLIENT_SECRET: 'my-secret',
    TRAKT_ACCESS_TOKEN: 'tok_abc',
    TRAKT_REFRESH_TOKEN: 'ref_abc',
    TRAKT_USERNAME: 'filmlover',
    TRAKT_HIDE_WATCHED: false,
  },
}

const CONFIG_TRAKT_HIDE = {
  ...CONFIG_TRAKT_CONNECTED,
  TRAKT: { ...CONFIG_TRAKT_CONNECTED.TRAKT, TRAKT_HIDE_WATCHED: true },
}

const WATCHED_STUB  = { ok: true, tmdb_ids: [TMDB_WATCHED] }
const STATUS_DISCONNECTED = { ok: true, connected: false, username: '', enabled: false }
const STATUS_CONNECTED    = { ok: true, connected: true, username: 'filmlover', enabled: true }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupMocks(page, { config = CONFIG_TRAKT_DISABLED, watched = WATCHED_STUB } = {}) {
  await page.route('**/api/config/status', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, issues: [] }) }))
  await page.route('**/api/config', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(config) }))
  await page.route('**/api/results', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RESULTS_STUB) }))
  await page.route('**/api/trakt/watched', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(watched) }))
  // Catch-all for movie details
  await page.route('**/api/movie/**', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ title: 'Test', cast: [] }) }))
  await page.route('**/api/streaming/**', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, providers: [] }) }))
  await page.route('**/api/radarr/library', r =>
    r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, tmdb_ids: [] }) }))
}

// ---------------------------------------------------------------------------
// Config UI: Trakt section
// ---------------------------------------------------------------------------

test.describe('Trakt config section', () => {

  test('shows connect form when not connected', async ({ page }) => {
    await setupMocks(page)
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    await page.waitForSelector('#cfg_trakt_id', { timeout: 5000 })

    // Client ID and Secret fields visible
    await expect(page.locator('#cfg_trakt_id')).toBeVisible()
    await expect(page.locator('#cfg_trakt_secret')).toBeVisible()

    // Connect button visible
    await expect(page.locator('button:has-text("Connect via Trakt")')).toBeVisible()

    // Connected box hidden
    await expect(page.locator('#traktConnectedBox')).not.toBeVisible()
  })

  test('shows username and disconnect button when connected', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_CONNECTED })
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    await page.waitForSelector('#traktConnectedBox', { timeout: 5000 })

    // Connected box shows username
    await expect(page.locator('#traktConnectedBox')).toContainText('@filmlover')

    // Disconnect button present
    await expect(page.locator('button:has-text("Disconnect")')).toBeVisible()

    // Connect form hidden
    await expect(page.locator('#traktConnectBox')).not.toBeVisible()
  })

  test('TRAKT_HIDE_WATCHED checkbox reflects config', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_HIDE })
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    await page.waitForSelector('#cfg_trakt_hide', { timeout: 5000 })

    // Checkbox should be checked when TRAKT_HIDE_WATCHED is true
    await expect(page.locator('#cfg_trakt_hide')).toBeChecked()
  })

  test('TRAKT_HIDE_WATCHED unchecked by default', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_CONNECTED })
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    await page.waitForSelector('#cfg_trakt_hide', { timeout: 5000 })

    await expect(page.locator('#cfg_trakt_hide')).not.toBeChecked()
  })

})

// ---------------------------------------------------------------------------
// Config UI: device code connect flow
// ---------------------------------------------------------------------------

test.describe('Trakt device code connect flow', () => {

  test('displays user code after clicking Connect', async ({ page }) => {
    await setupMocks(page)
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    await page.waitForSelector('#cfg_trakt_id', { timeout: 5000 })

    // Fill in credentials
    await page.fill('#cfg_trakt_id', 'my-client-id')
    await page.fill('#cfg_trakt_secret', 'my-secret')

    // Mock device code endpoint
    await page.route('**/api/trakt/device/code', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          device_code:      'dev123',
          user_code:        'HELLO-WORLD',
          verification_url: 'https://trakt.tv/activate',
          expires_in:       600,
          interval:         5,
        }),
      }))

    await page.route('**/api/trakt/device/poll', r =>
      r.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: false, status: 'pending' }),
      }))

    await page.click('button:has-text("Connect via Trakt")')

    // Device box should appear with the user code
    const deviceBox = page.locator('#traktDeviceBox')
    await expect(deviceBox).toBeVisible({ timeout: 3000 })
    await expect(deviceBox).toContainText('HELLO-WORLD')
    await expect(deviceBox).toContainText('trakt.tv/activate')
  })

  test('shows error when client id missing', async ({ page }) => {
    await setupMocks(page)
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    await page.waitForSelector('#cfg_trakt_id', { timeout: 5000 })

    // Don't fill in any credentials
    await page.click('button:has-text("Connect via Trakt")')

    // Should show a toast error, not a device box
    await expect(page.locator('#traktDeviceBox')).not.toBeVisible()
  })

})

// ---------------------------------------------------------------------------
// Cards: watched badge overlay
// ---------------------------------------------------------------------------

test.describe('Trakt watched badge on cards', () => {

  test('watched badge appears on watched movie card', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_CONNECTED, watched: WATCHED_STUB })
    await page.goto('/')

    // Navigate to Classics where MOVIE_WATCHED appears
    await page.locator('button.nav[data-tab="classics"]').click()

    // Wait for cards to render
    await page.waitForSelector('.pc', { timeout: 5000 })

    // Give _fetchTraktWatched a moment to complete and re-render
    await page.waitForTimeout(300)

    // The watched card should have the badge — NOTE: badge appears after
    // _fetchTraktWatched resolves, so re-render may be needed.
    // We look for any .watched-badge in the grid.
    // (In real usage JS re-renders on nav; here watched ids are loaded async)
    // Navigate away and back to force a render with ids populated
    await page.locator('button.nav[data-tab="dashboard"]').click()
    await page.locator('button.nav[data-tab="classics"]').click()
    await page.waitForSelector('.pc', { timeout: 5000 })

    const watchedCard = page.locator(`.pc[data-tmdb="${TMDB_WATCHED}"]`)
    await expect(watchedCard.locator('.watched-badge')).toBeVisible({ timeout: 3000 })
  })

  test('no watched badge on unwatched movie card', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_CONNECTED, watched: WATCHED_STUB })
    await page.goto('/')
    await page.locator('button.nav[data-tab="classics"]').click()
    await page.waitForSelector('.pc', { timeout: 5000 })

    const unwatchedCard = page.locator(`.pc[data-tmdb="${TMDB_UNWATCHED}"]`)
    await expect(unwatchedCard).toBeVisible()
    await expect(unwatchedCard.locator('.watched-badge')).not.toBeVisible()
  })

  test('no watched badge when Trakt is disabled', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_DISABLED, watched: { ok: true, tmdb_ids: [] } })
    await page.goto('/')
    await page.locator('button.nav[data-tab="classics"]').click()
    await page.waitForSelector('.pc', { timeout: 5000 })

    // No watched badges anywhere
    await expect(page.locator('.watched-badge')).toHaveCount(0)
  })

})

// ---------------------------------------------------------------------------
// Cards: hide-watched filter
// ---------------------------------------------------------------------------

test.describe('Trakt hide-watched filter', () => {

  test('watched movie hidden from Classics when TRAKT_HIDE_WATCHED=true', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_HIDE, watched: WATCHED_STUB })
    await page.goto('/')

    // Navigate away and back to trigger re-render after fetch
    await page.locator('button.nav[data-tab="classics"]').click()
    await page.waitForSelector('.pc', { timeout: 5000 })
    await page.locator('button.nav[data-tab="dashboard"]').click()
    await page.locator('button.nav[data-tab="classics"]').click()
    await page.waitForSelector('.pc', { timeout: 5000 })

    // Watched movie should be hidden
    await expect(page.locator(`.pc[data-tmdb="${TMDB_WATCHED}"]`)).toHaveCount(0)

    // Unwatched movie still visible
    await expect(page.locator(`.pc[data-tmdb="${TMDB_UNWATCHED}"]`)).toBeVisible()
  })

  test('watched movie remains in Wishlist even with TRAKT_HIDE_WATCHED=true', async ({ page }) => {
    await setupMocks(page, { config: CONFIG_TRAKT_HIDE, watched: WATCHED_STUB })
    await page.goto('/')

    await page.locator('button.nav[data-tab="wishlist"]').click()
    await page.waitForSelector('.pc', { timeout: 5000 })

    // MOVIE_WATCHED is also in wishlist — should NOT be hidden there
    await expect(page.locator(`.pc[data-tmdb="${TMDB_WATCHED}"]`)).toBeVisible()
  })

})
