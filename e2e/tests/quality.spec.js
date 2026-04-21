// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests for the Quality Upgrades tab.
 *
 * All backend calls are mocked — no live Radarr instance required.
 * Tests cover: tab navigation, grid rendering, quality resolution badge,
 * empty state, and the "→ 4K" button interaction.
 */

const UPGRADE_MOVIES = [
  {
    tmdb:            603,
    title:           'The Matrix',
    year:            '1999',
    poster:          null,
    rating:          8.7,
    current_quality: 'Bluray-1080p',
    resolution:      1080,
    wishlist:        false,
  },
  {
    tmdb:            680,
    title:           'Pulp Fiction',
    year:            '1994',
    poster:          null,
    rating:          8.9,
    current_quality: 'WEBDL-720p',
    resolution:      720,
    wishlist:        false,
  },
]

const UPGRADES_RESPONSE     = { ok: true,  movies: UPGRADE_MOVIES, count: 2 }
const UPGRADES_EMPTY        = { ok: true,  movies: [],             count: 0 }
const UPGRADES_RADARR_ERROR = { ok: false, error: 'Radarr not enabled', movies: [], count: 0 }

const CONFIG_STUB_4K = {
  PLEX: {}, TMDB: { TMDB_API_KEY: 'test' },
  RADARR:    { RADARR_ENABLED: true },
  RADARR_4K: { RADARR_4K_ENABLED: true },
  OVERSEERR:  { OVERSEERR_ENABLED: false },
  JELLYSEERR: { JELLYSEERR_ENABLED: false },
  STREAMING:  { STREAMING_COUNTRY: 'US' },
  AUTH:       { AUTH_METHOD: 'None' },
}

const CONFIG_STUB_NO_4K = {
  ...CONFIG_STUB_4K,
  RADARR_4K: { RADARR_4K_ENABLED: false },
}

const RESULTS_STUB = {
  ok: true, configured: true, scanning: false, sections: {},
  wishlist: [], franchises: [], directors: [], actors: [], classics: [], suggestions: [],
}

const RADARR_ADD_OK    = { ok: true }
const RADARR_ADD_FAIL  = { ok: false, error: 'Movie already exists' }
const REFRESH_OK       = { ok: true }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupBase(page, upgradesPayload = UPGRADES_RESPONSE, configPayload = CONFIG_STUB_4K) {
  await page.route('**/api/config/status',     r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, issues: [] }) }))
  await page.route('**/api/results',           r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RESULTS_STUB) }))
  await page.route('**/api/config',            r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(configPayload) }))
  await page.route('**/api/quality/upgrades',  r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(upgradesPayload) }))
  await page.route('**/api/quality/refresh',   r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(REFRESH_OK) }))
  await page.route('**/api/streaming/**',      r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, providers: [], link: '' }) }))
  await page.route('**/api/movie/**',          r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tmdb: 603, title: 'The Matrix', cast: [], genres: [] }) }))
}

async function goToUpgrades(page) {
  const btn = page.locator('button.nav[data-tab="upgrades"]')
  await expect(btn).toBeVisible()
  await btn.click()
  await page.waitForSelector('.grid-posters', { timeout: 6000 })
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

test.describe('Quality Upgrades tab — navigation', () => {

  test('Upgrades tab button is visible in the sidebar', async ({ page }) => {
    await setupBase(page)
    await page.goto('/')
    await expect(page.locator('button.nav[data-tab="upgrades"]')).toBeVisible()
  })

  test('clicking Upgrades tab changes page title', async ({ page }) => {
    await setupBase(page)
    await page.goto('/')
    await page.locator('button.nav[data-tab="upgrades"]').click()
    await expect(page.locator('#page-title')).toHaveText('Quality Upgrades', { timeout: 4000 })
  })

})

// ---------------------------------------------------------------------------
// Grid rendering
// ---------------------------------------------------------------------------

test.describe('Quality Upgrades tab — grid', () => {

  test('renders a card for each upgrade candidate', async ({ page }) => {
    await setupBase(page)
    await page.goto('/')
    await goToUpgrades(page)

    const cards = page.locator('.grid-posters .pc')
    await expect(cards).toHaveCount(2)
  })

  test('resolution badge is visible on each card', async ({ page }) => {
    await setupBase(page)
    await page.goto('/')
    await goToUpgrades(page)

    // Each card should show its resolution (e.g. "1080p" or "720p")
    const firstCard = page.locator('.grid-posters .pc').first()
    await expect(firstCard).toContainText('p')  // "1080p" or "720p"
  })

  test('header shows correct candidate count', async ({ page }) => {
    await setupBase(page)
    await page.goto('/')
    await goToUpgrades(page)

    // Description text mentions the movie count
    await expect(page.locator('#content')).toContainText('2 movies')
  })

})

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

test.describe('Quality Upgrades tab — empty state', () => {

  test('shows empty state when no upgrade candidates exist', async ({ page }) => {
    await setupBase(page, UPGRADES_EMPTY)
    await page.goto('/')
    await page.locator('button.nav[data-tab="upgrades"]').click()
    await page.waitForTimeout(500)

    await expect(page.locator('#content')).toContainText('already in Radarr 4K')
  })

  test('shows error message when Radarr is not enabled', async ({ page }) => {
    await setupBase(page, UPGRADES_RADARR_ERROR)
    await page.goto('/')
    await page.locator('button.nav[data-tab="upgrades"]').click()
    await page.waitForTimeout(500)

    await expect(page.locator('#content')).toContainText('Radarr not enabled')
  })

})

// ---------------------------------------------------------------------------
// 4K button — Radarr 4K enabled
// ---------------------------------------------------------------------------

test.describe('Quality Upgrades tab — → 4K button', () => {

  test('4K button visible when Radarr 4K is enabled', async ({ page }) => {
    await setupBase(page, UPGRADES_RESPONSE, CONFIG_STUB_4K)
    await page.goto('/')
    await goToUpgrades(page)

    // Hover first card to reveal overlay
    const firstCard = page.locator('.grid-posters .pc').first()
    await firstCard.hover()
    const btn = firstCard.locator('button', { hasText: '→ 4K' })
    await expect(btn).toBeVisible()
  })

  test('clicking → 4K calls Radarr 4K API and updates button', async ({ page }) => {
    await setupBase(page, UPGRADES_RESPONSE, CONFIG_STUB_4K)
    // Mock Radarr 4K: single profile so no picker shown
    await page.route('**/api/radarr/profiles**',   r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, profiles: [{ id: 6, name: 'Ultra-HD' }] }) }))
    await page.route('**/api/radarr/rootfolders**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, folders: [{ path: '/movies4k', freeSpace: 0 }] }) }))
    await page.route('**/api/radarr/add**',        r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RADARR_ADD_OK) }))

    await page.goto('/')
    await goToUpgrades(page)

    const firstCard = page.locator('.grid-posters .pc').first()
    await firstCard.hover()
    await firstCard.locator('button', { hasText: '→ 4K' }).click()

    // After success the button text changes to ✓ Queued — re-query by new text
    const successBtn = firstCard.locator('button', { hasText: '✓ Queued' })
    await expect(successBtn).toBeVisible({ timeout: 3000 })
    await expect(successBtn).toBeDisabled()
  })

  test('4K button shows "Enable Radarr 4K" text when Radarr 4K is disabled', async ({ page }) => {
    await setupBase(page, UPGRADES_RESPONSE, CONFIG_STUB_NO_4K)
    await page.goto('/')
    await goToUpgrades(page)

    const firstCard = page.locator('.grid-posters .pc').first()
    await firstCard.hover()
    await expect(firstCard).toContainText('Enable Radarr 4K')
  })

})

// ---------------------------------------------------------------------------
// Refresh button
// ---------------------------------------------------------------------------

test.describe('Quality Upgrades tab — refresh', () => {

  test('refresh button is present in the header', async ({ page }) => {
    await setupBase(page)
    await page.goto('/')
    await goToUpgrades(page)

    const refreshBtn = page.locator('#content button', { hasText: '⟳ Refresh' })
    await expect(refreshBtn).toBeVisible()
  })

  test('clicking refresh re-fetches upgrade data', async ({ page }) => {
    let callCount = 0
    await page.route('**/api/config/status', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, issues: [] }) }))
    await page.route('**/api/results', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RESULTS_STUB) }))
    await page.route('**/api/config',  r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CONFIG_STUB_4K) }))
    await page.route('**/api/quality/upgrades', r => {
      callCount++
      return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(UPGRADES_RESPONSE) })
    })
    await page.route('**/api/quality/refresh', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(REFRESH_OK) }))
    await page.route('**/api/streaming/**', r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, providers: [], link: '' }) }))

    await page.goto('/')
    await goToUpgrades(page)

    const refreshBtn = page.locator('#content button', { hasText: '⟳ Refresh' })
    await refreshBtn.click()

    // After refresh the tab re-fetches upgrades
    await page.waitForSelector('.grid-posters', { timeout: 4000 })
    expect(callCount).toBeGreaterThanOrEqual(2)
  })

})
