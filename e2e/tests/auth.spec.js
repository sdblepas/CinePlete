// @ts-check
const { test, expect } = require('@playwright/test')

// NOTE: The app runs with AUTH_METHOD="None" in the e2e environment,
// so all pages are accessible without login. These tests verify:
//   1. Auth API endpoints return correct shape
//   2. /login page renders correctly
//   3. Auth section appears in Config UI
//   4. Logout button is hidden when auth mode is None

test.describe('Auth — API endpoints', () => {

  test('/api/auth/status returns correct shape', async ({ request }) => {
    const res = await request.get('/api/auth/status')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('method')
    expect(body).toHaveProperty('authenticated')
    expect(body).toHaveProperty('has_user')
  })

  test('/api/auth/status method is None in e2e env', async ({ request }) => {
    const res  = await request.get('/api/auth/status')
    const body = await res.json()
    expect(body.method).toBe('None')
    expect(body.authenticated).toBe(true)
  })

  test('/api/config does not expose password hash or secret key', async ({ request }) => {
    const res  = await request.get('/api/config')
    const body = await res.json()
    expect(body.AUTH).toBeDefined()
    expect(body.AUTH.AUTH_PASSWORD_HASH).toBeUndefined()
    expect(body.AUTH.AUTH_PASSWORD_SALT).toBeUndefined()
    expect(body.AUTH.AUTH_SECRET_KEY).toBeUndefined()
    expect(body.AUTH).toHaveProperty('AUTH_HAS_PASSWORD')
    expect(body.AUTH).toHaveProperty('AUTH_METHOD')
  })

  test('POST /api/auth/logout returns ok', async ({ request }) => {
    const res  = await request.post('/api/auth/logout')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.ok).toBe(true)
  })

  test('POST /api/auth/login with no user configured returns error', async ({ request }) => {
    const res = await request.post('/api/auth/login', {
      data: { username: 'admin', password: 'wrong', remember_me: false },
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.ok).toBe(false)
    expect(body.error).toBeTruthy()
  })

})

test.describe('Auth — login page', () => {

  test('/login returns 200', async ({ request }) => {
    const res = await request.get('/login')
    expect(res.status()).toBe(200)
  })

  test('login page has username and password fields', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#username')).toBeVisible()
    await expect(page.locator('#password')).toBeVisible()
  })

  test('login page has remember me checkbox', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#remember')).toBeVisible()
  })

  test('login page has sign in button', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('#loginBtn')).toBeVisible()
    await expect(page.locator('#loginBtn')).toContainText(/sign in/i)
  })

  test('login page shows error on empty submit', async ({ page }) => {
    await page.goto('/login')
    await page.click('#loginBtn')
    await expect(page.locator('#error')).toBeVisible()
  })

  test('login page title is correct', async ({ page }) => {
    await page.goto('/login')
    await expect(page).toHaveTitle(/Cineplete/i)
  })

})

test.describe('Auth — config UI', () => {

  test('Authentication section is visible in config tab', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-tab="config"]')
    await expect(page.locator('#cfg_auth_method')).toBeVisible()
  })

  test('auth method select has three options', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-tab="config"]')
    const options = page.locator('#cfg_auth_method option')
    await expect(options).toHaveCount(3)
  })

  test('auth method defaults to None', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-tab="config"]')
    const value = await page.locator('#cfg_auth_method').inputValue()
    expect(value).toBe('None')
  })

  test('username field is visible in auth section', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-tab="config"]')
    await expect(page.locator('#cfg_auth_username')).toBeVisible()
  })

  test('password field is of type password (secret)', async ({ page }) => {
    await page.goto('/')
    await page.click('[data-tab="config"]')
    const type = await page.locator('#cfg_auth_password').getAttribute('type')
    expect(type).toBe('password')
  })

})

test.describe('Auth — logout button', () => {

  test('logout button is hidden when auth mode is None', async ({ page }) => {
    await page.goto('/')
    // Boot fetches /api/auth/status — with method=None, button stays hidden
    await page.waitForTimeout(500)
    const btn = page.locator('#logoutBtn')
    await expect(btn).toBeHidden()
  })

})
