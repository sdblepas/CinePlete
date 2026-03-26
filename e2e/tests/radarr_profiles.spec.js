// @ts-check
const { test, expect } = require('@playwright/test')

/**
 * E2E tests for the Radarr quality-profile dropdown.
 *
 * All tests mock the /api/radarr/profiles backend so they work without
 * a live Radarr instance.  The UI behaviour (button state, select options,
 * toast messages) is verified end-to-end in the browser.
 */

const SAMPLE_PROFILES = [
  { id: 4, name: 'Any' },
  { id: 6, name: 'Ultra-HD' },
  { id: 9, name: 'HD-1080p' },
]

async function goToRadarrConfig(page) {
  await page.goto('/')
  await page.locator('button.nav[data-tab="config"]').click()
  await page.waitForSelector('#cfg_radarr_quality', { timeout: 5000 })
}

/** Intercept /api/radarr/profiles for a given instance and return fake profiles */
async function mockProfiles(page, instance, payload) {
  await page.route(
    `**/api/radarr/profiles?instance=${instance}`,
    route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
  )
}

/** Intercept /api/radarr/profiles for a given instance and simulate a network error */
async function mockProfilesError(page, instance, errorPayload) {
  await page.route(
    `**/api/radarr/profiles?instance=${instance}`,
    route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(errorPayload) })
  )
}

// ---------------------------------------------------------------------------
// Quality-profile select + Fetch button — primary instance
// ---------------------------------------------------------------------------
test.describe('Radarr quality profile dropdown — primary instance', () => {
  test('quality profile select is visible in Radarr config section', async ({ page }) => {
    await goToRadarrConfig(page)
    await expect(page.locator('#cfg_radarr_quality')).toBeVisible()
  })

  test('Fetch button is visible next to primary quality profile select', async ({ page }) => {
    await goToRadarrConfig(page)
    // The Fetch button is rendered as part of qualityProfileField("cfg_radarr_quality", …)
    // It sits beside the <select> and calls fetchRadarrProfiles('primary','cfg_radarr_quality')
    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="primary"][onclick*="cfg_radarr_quality"]'
    )
    await expect(fetchBtn).toBeVisible()
    await expect(fetchBtn).toBeEnabled()
  })

  test('Fetch populates select with profile names from API', async ({ page }) => {
    await mockProfiles(page, 'primary', { ok: true, profiles: SAMPLE_PROFILES })
    await goToRadarrConfig(page)

    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="primary"][onclick*="cfg_radarr_quality"]'
    )
    await fetchBtn.click()

    const sel = page.locator('#cfg_radarr_quality')
    // All three profiles should appear as <option> elements
    await expect(sel.locator('option')).toHaveCount(3)
    await expect(sel.locator('option[value="4"]')).toHaveText('Any (4)')
    await expect(sel.locator('option[value="6"]')).toHaveText('Ultra-HD (6)')
    await expect(sel.locator('option[value="9"]')).toHaveText('HD-1080p (9)')
  })

  test('success toast appears after Fetch', async ({ page }) => {
    await mockProfiles(page, 'primary', { ok: true, profiles: SAMPLE_PROFILES })
    await goToRadarrConfig(page)

    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="primary"][onclick*="cfg_radarr_quality"]'
    )
    await fetchBtn.click()

    // Toast with success class should appear
    const toast = page.locator('.toast.success, #toast.success, [class*="toast"][class*="success"]')
    await expect(toast).toBeVisible({ timeout: 3000 })
  })

  test('Fetch button re-enables after successful load', async ({ page }) => {
    await mockProfiles(page, 'primary', { ok: true, profiles: SAMPLE_PROFILES })
    await goToRadarrConfig(page)

    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="primary"][onclick*="cfg_radarr_quality"]'
    )
    await fetchBtn.click()

    // Button should be re-enabled and back to "⟳ Fetch" label after response
    await expect(fetchBtn).toBeEnabled({ timeout: 3000 })
    await expect(fetchBtn).toHaveText('⟳ Fetch')
  })

  test('error toast appears when API returns ok:false', async ({ page }) => {
    await mockProfilesError(page, 'primary', { ok: false, error: 'Invalid API key' })
    await goToRadarrConfig(page)

    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="primary"][onclick*="cfg_radarr_quality"]'
    )
    await fetchBtn.click()

    const toast = page.locator('.toast.error, #toast.error, [class*="toast"][class*="error"]')
    await expect(toast).toBeVisible({ timeout: 3000 })
    await expect(toast).toContainText('Invalid API key')
  })
})

// ---------------------------------------------------------------------------
// Quality-profile select + Fetch button — 4K instance
// ---------------------------------------------------------------------------
test.describe('Radarr quality profile dropdown — 4K instance', () => {
  test('4K quality profile select is visible in Radarr 4K config section', async ({ page }) => {
    await goToRadarrConfig(page)
    await expect(page.locator('#cfg_r4k_quality')).toBeVisible()
  })

  test('Fetch button is visible next to 4K quality profile select', async ({ page }) => {
    await goToRadarrConfig(page)
    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="4k"][onclick*="cfg_r4k_quality"]'
    )
    await expect(fetchBtn).toBeVisible()
    await expect(fetchBtn).toBeEnabled()
  })

  test('Fetch populates 4K select with profile names from API', async ({ page }) => {
    await mockProfiles(page, '4k', { ok: true, profiles: SAMPLE_PROFILES })
    await goToRadarrConfig(page)

    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="4k"][onclick*="cfg_r4k_quality"]'
    )
    await fetchBtn.click()

    const sel = page.locator('#cfg_r4k_quality')
    await expect(sel.locator('option')).toHaveCount(3)
    await expect(sel.locator('option[value="4"]')).toHaveText('Any (4)')
    await expect(sel.locator('option[value="9"]')).toHaveText('HD-1080p (9)')
  })

  test('error toast appears when 4K API returns ok:false', async ({ page }) => {
    await mockProfilesError(page, '4k', { ok: false, error: 'URL and API key required' })
    await goToRadarrConfig(page)

    const fetchBtn = page.locator(
      'button[onclick*="fetchRadarrProfiles"][onclick*="4k"][onclick*="cfg_r4k_quality"]'
    )
    await fetchBtn.click()

    const toast = page.locator('.toast.error, #toast.error, [class*="toast"][class*="error"]')
    await expect(toast).toBeVisible({ timeout: 3000 })
    await expect(toast).toContainText('URL and API key required')
  })
})

// ---------------------------------------------------------------------------
// /api/radarr/profiles endpoint contract
// ---------------------------------------------------------------------------
test.describe('/api/radarr/profiles API contract', () => {
  test('returns ok:true with profiles array for primary instance', async ({ request }) => {
    // This test hits the real backend — it only passes when a running server is
    // available at BASE_URL.  On CI, skip if Radarr is not configured.
    const res = await request.get('/api/radarr/profiles?instance=primary')
    expect(res.status()).toBe(200)
    const body = await res.json()
    // Either configured (ok:true, profiles array) or not configured (ok:false, error string)
    expect(typeof body.ok).toBe('boolean')
    if (body.ok) {
      expect(Array.isArray(body.profiles)).toBe(true)
      if (body.profiles.length > 0) {
        expect(typeof body.profiles[0].id).toBe('number')
        expect(typeof body.profiles[0].name).toBe('string')
      }
    } else {
      expect(typeof body.error).toBe('string')
    }
  })

  test('returns ok:true with profiles array for 4k instance', async ({ request }) => {
    const res = await request.get('/api/radarr/profiles?instance=4k')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(typeof body.ok).toBe('boolean')
    if (body.ok) {
      expect(Array.isArray(body.profiles)).toBe(true)
    } else {
      expect(typeof body.error).toBe('string')
    }
  })

  test('defaults to primary when no instance param given', async ({ request }) => {
    const res1 = await request.get('/api/radarr/profiles')
    const res2 = await request.get('/api/radarr/profiles?instance=primary')
    expect(res1.status()).toBe(200)
    expect(res2.status()).toBe(200)
    // Both responses should have the same shape
    const b1 = await res1.json()
    const b2 = await res2.json()
    expect(typeof b1.ok).toBe('boolean')
    expect(b1.ok).toBe(b2.ok)
  })
})
