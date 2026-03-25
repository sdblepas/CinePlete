// @ts-check
const { test, expect } = require('@playwright/test')

test.describe('App smoke tests', () => {
  test('homepage returns 200 and has correct title', async ({ page }) => {
    const response = await page.goto('/')
    expect(response.status()).toBe(200)
    await expect(page).toHaveTitle(/Cineplete/i)
  })

  test('sidebar logo is visible', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#sidebar-logo')).toBeVisible()
    await expect(page.locator('.logo-text')).toContainText('Cineplete')
  })

  test('scan button is visible and enabled', async ({ page }) => {
    await page.goto('/')
    const btn = page.locator('#scanBtn')
    await expect(btn).toBeVisible()
    await expect(btn).toBeEnabled()
  })

  test('page title defaults to Dashboard', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('#page-title')).toHaveText('Dashboard')
  })

  test('API version endpoint responds', async ({ request }) => {
    const res = await request.get('/api/version')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('version')
  })

  test('API scan status endpoint responds', async ({ request }) => {
    const res = await request.get('/api/scan/status')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('running')
  })

  test('API config endpoint responds', async ({ request }) => {
    const res = await request.get('/api/config')
    expect(res.status()).toBe(200)
    const body = await res.json()
    // Should at minimum return PLEX and TMDB sections
    expect(body).toHaveProperty('PLEX')
    expect(body).toHaveProperty('TMDB')
  })
})
