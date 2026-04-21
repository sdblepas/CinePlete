// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests for streaming availability (JustWatch via TMDB).
 *
 * All backend calls are mocked so tests run without live TMDB / JustWatch access.
 * Verifies the "Where to watch" section appears in the movie modal when providers
 * are available, and is absent when there are none.
 */

const TMDB_ID = 603

const STREAMING_WITH_PROVIDERS = {
  ok: true,
  country: 'US',
  link: 'https://www.justwatch.com/us/movie/the-matrix',
  providers: [
    {
      name: 'Netflix',
      logo: 'https://image.tmdb.org/t/p/original/netflix.jpg',
      type: 'flatrate',
      id:   8,
    },
    {
      name: 'Amazon Prime',
      logo: 'https://image.tmdb.org/t/p/original/prime.jpg',
      type: 'flatrate',
      id:   9,
    },
    {
      name: 'Apple TV',
      logo: 'https://image.tmdb.org/t/p/original/apple.jpg',
      type: 'rent',
      id:   2,
    },
  ],
}

const STREAMING_NO_PROVIDERS = {
  ok: true,
  country: 'US',
  link: '',
  providers: [],
}

const SAMPLE_MOVIE_DETAIL = {
  tmdb:        TMDB_ID,
  title:       'The Matrix',
  year:        '1999',
  overview:    'A computer hacker learns about the true nature of reality.',
  tagline:     'Welcome to the Real World',
  genres:      [{ id: 28, name: 'Action' }],
  poster:      null,
  backdrop:    null,
  rating:      8.7,
  votes:       25000,
  runtime:     136,
  trailer_key: null,
  tmdb_url:    `https://www.themoviedb.org/movie/${TMDB_ID}`,
  cast:        [],
}

const RESULTS_STUB = {
  ok:          true,
  configured:  true,
  scanning:    false,
  sections:    {},
  wishlist:    [{
    tmdb:    TMDB_ID,
    title:   'The Matrix',
    year:    '1999',
    poster:  null,
    rating:  8.7,
    wishlist: true,
  }],
  franchises:  [],
  directors:   [],
  actors:      [],
  classics:    [],
  suggestions: [],
}

const CONFIG_STUB = {
  PLEX: {}, TMDB: { TMDB_API_KEY: 'test' },
  RADARR: { RADARR_ENABLED: false },
  RADARR_4K: { RADARR_4K_ENABLED: false },
  OVERSEERR: { OVERSEERR_ENABLED: false },
  JELLYSEERR: { JELLYSEERR_ENABLED: false },
  STREAMING: { STREAMING_COUNTRY: 'US' },
  AUTH: { AUTH_METHOD: 'None' },
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function setupMocks(page, streamingPayload = STREAMING_WITH_PROVIDERS) {
  await page.route('**/api/config/status',     r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, issues: [] }) }))
  await page.route('**/api/results',           r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RESULTS_STUB) }))
  await page.route('**/api/config',            r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CONFIG_STUB) }))
  await page.route(`**/api/movie/${TMDB_ID}`,  r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SAMPLE_MOVIE_DETAIL) }))
  await page.route(`**/api/streaming/${TMDB_ID}`, r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(streamingPayload) }))
}

async function openMatrixModal(page) {
  await page.locator('button.nav[data-tab="wishlist"]').click()
  // Click the first poster card in the wishlist grid
  await page.locator('.pc[data-tmdb="603"]').first().click()
  // Wait for the modal to open
  await page.waitForSelector('#movieModal.open', { timeout: 5000 })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('Streaming availability in movie modal', () => {

  test('streaming section appears with providers when available', async ({ page }) => {
    await setupMocks(page)
    await page.goto('/')
    await openMatrixModal(page)

    // The streaming section is lazy-loaded — wait for it to appear
    const section = page.locator('#streamingSection')
    await expect(section).not.toBeEmpty({ timeout: 5000 })

    // Should contain "Where to watch" label
    await expect(section).toContainText('Where to watch')
  })

  test('shows provider logos for flatrate services', async ({ page }) => {
    await setupMocks(page)
    await page.goto('/')
    await openMatrixModal(page)

    const section = page.locator('#streamingSection')
    await expect(section).not.toBeEmpty({ timeout: 5000 })

    // Provider logos should be present
    const imgs = section.locator('img')
    await expect(imgs).toHaveCount(3) // Netflix, Amazon Prime, Apple TV
  })

  test('JustWatch link present when link provided', async ({ page }) => {
    await setupMocks(page)
    await page.goto('/')
    await openMatrixModal(page)

    const section = page.locator('#streamingSection')
    await expect(section).not.toBeEmpty({ timeout: 5000 })

    const link = section.locator('a[href*="justwatch.com"]')
    await expect(link).toBeVisible()
    await expect(link).toHaveAttribute('target', '_blank')
  })

  test('streaming section is empty when no providers available', async ({ page }) => {
    await setupMocks(page, STREAMING_NO_PROVIDERS)
    await page.goto('/')
    await openMatrixModal(page)

    // Give the lazy load time to complete
    await page.waitForTimeout(500)
    const section = page.locator('#streamingSection')
    // Should remain empty (no "Where to watch" row injected)
    await expect(section).toBeEmpty()
  })

  test('modal still opens correctly when streaming API fails', async ({ page }) => {
    await page.route('**/api/config/status',     r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, issues: [] }) }))
    await page.route('**/api/results',           r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(RESULTS_STUB) }))
    await page.route('**/api/config',            r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(CONFIG_STUB) }))
    await page.route(`**/api/movie/${TMDB_ID}`,  r => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SAMPLE_MOVIE_DETAIL) }))
    // Streaming API returns an error
    await page.route(`**/api/streaming/${TMDB_ID}`, r => r.fulfill({ status: 500, body: '{"ok":false,"error":"TMDB error"}' }))

    await page.goto('/')
    await openMatrixModal(page)

    // Modal should be open and show movie title
    await expect(page.locator('#movieModalTitle')).toContainText('The Matrix')
    // Streaming section should be empty (no crash)
    const section = page.locator('#streamingSection')
    await expect(section).toBeEmpty()
  })

})
