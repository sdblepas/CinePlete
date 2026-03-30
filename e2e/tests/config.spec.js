// @ts-check
const { test, expect } = require('@playwright/test')

test.describe('Settings page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.locator('button.nav[data-tab="config"]').click()
    // Wait for the config form to render
    await page.waitForSelector('#cfg_tmdb_key', { timeout: 5000 })
  })

  test('page title shows Configuration', async ({ page }) => {
    // PAGE_TITLES.config = "Configuration" in app.js
    await expect(page.locator('#page-title')).toHaveText('Configuration')
  })

  test('TMDB API Key field is present and masked', async ({ page }) => {
    const field = page.locator('#cfg_tmdb_key')
    await expect(field).toBeVisible()
    await expect(field).toHaveAttribute('type', 'password')
  })

  test('Libraries section is present with Add Plex and Add Jellyfin buttons', async ({ page }) => {
    await expect(page.locator('#libraries-section')).toBeVisible()
    await expect(page.locator('button', { hasText: '+ Add Plex' })).toBeVisible()
    await expect(page.locator('button', { hasText: '+ Add Jellyfin' })).toBeVisible()
  })

  test('Save Configuration button is present and enabled', async ({ page }) => {
    const saveBtn = page.locator('button', { hasText: /save configuration/i })
    await expect(saveBtn).toBeVisible()
    await expect(saveBtn).toBeEnabled()
  })

  test('Add Plex entry renders URL and library name fields', async ({ page }) => {
    await page.locator('button', { hasText: '+ Add Plex' }).click()
    await expect(page.locator('[id^="lib_"][id$="_url"]').first()).toBeVisible()
    await expect(page.locator('[id^="lib_"][id$="_library"]').first()).toBeVisible()
  })

  test('Add Jellyfin entry renders URL and library name fields', async ({ page }) => {
    await page.locator('button', { hasText: '+ Add Jellyfin' }).click()
    await expect(page.locator('[id^="lib_"][id$="_url"]').first()).toBeVisible()
    await expect(page.locator('[id^="lib_"][id$="_library"]').first()).toBeVisible()
  })

  test('config roundtrip: save then reload preserves values', async ({ page, request }) => {
    // Read current config
    const before = await request.get('/api/config')
    const cfg = await before.json()

    // POST a save with a known test value
    const res = await request.post('/api/config', {
      data: {
        ...cfg,
        TMDB: { ...cfg.TMDB, TMDB_API_KEY: 'test-key-e2e' },
      },
    })
    expect(res.status()).toBe(200)

    // Reload and verify
    const after = await request.get('/api/config')
    const updated = await after.json()
    expect(updated.TMDB.TMDB_API_KEY).toBe('test-key-e2e')

    // Restore original value
    await request.post('/api/config', { data: cfg })
  })
})

test.describe('Movie modal', () => {
  test('modal is hidden on load', async ({ page }) => {
    await page.goto('/')
    const modal = page.locator('#movieModal')
    // Modal exists in DOM but should not be visible (no 'open' class)
    await expect(modal).not.toHaveClass(/open/)
  })

  test('modal opens and closes via DOM manipulation', async ({ page }) => {
    await page.goto('/')
    // Add the open class directly — avoids triggering real TMDB API calls
    await page.evaluate(() => {
      document.getElementById('movieModal')?.classList.add('open')
    })
    await expect(page.locator('#movieModal')).toHaveClass(/open/)

    // Close via the ✕ button
    await page.locator('#movieModalClose').click()
    await expect(page.locator('#movieModal')).not.toHaveClass(/open/)
  })
})
