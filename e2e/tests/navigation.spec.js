// @ts-check
const { test, expect } = require('@playwright/test')

// Tabs whose page title updates WITHOUT needing scan data or configuration.
// All others call renderSkeleton() (no data) or are forced to config (!CONFIGURED).
const TITLE_TABS = [
  { tab: 'dashboard',  title: 'Dashboard' },
  { tab: 'config',     title: 'Configuration' }, // PAGE_TITLES.config = "Configuration"
]

// All nav tabs — we test button presence and .active class for these,
// but NOT page title (title requires scan data or config to be set up).
const ALL_TABS = [
  'dashboard', 'notmdb', 'nomatch', 'duplicates',
  'franchises', 'directors', 'actors', 'classics',
  'suggestions', 'wishlist', 'config', 'logs',
]

test.describe('Sidebar navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('all nav buttons are present', async ({ page }) => {
    for (const tab of ALL_TABS) {
      await expect(
        page.locator(`button.nav[data-tab="${tab}"]`),
        `nav button for tab "${tab}" should exist`
      ).toBeVisible()
    }
  })

  test('clicking a nav button makes it .active', async ({ page }) => {
    // Use config tab — it always works regardless of data or configuration state
    await page.locator('button.nav[data-tab="config"]').click()
    await expect(page.locator('button.nav[data-tab="config"]')).toHaveClass(/active/)
  })

  test('previous active nav loses .active class on switch', async ({ page }) => {
    // Dashboard is active by default; switch to config
    await page.locator('button.nav[data-tab="config"]').click()
    await expect(page.locator('button.nav[data-tab="dashboard"]')).not.toHaveClass(/active/)
  })

  // Only test page title for tabs that update it without needing data/config
  for (const { tab, title } of TITLE_TABS) {
    test(`clicking "${tab}" updates page title to "${title}"`, async ({ page }) => {
      await page.locator(`button.nav[data-tab="${tab}"]`).click()
      await expect(page.locator('#page-title')).toHaveText(title)
    })
  }

  // For data-gated tabs: verify button is clickable and becomes .active
  // (page title stays "Dashboard" via renderSkeleton when no scan data exists)
  const DATA_GATED = ['notmdb', 'nomatch', 'duplicates', 'franchises',
                      'directors', 'actors', 'classics', 'suggestions', 'wishlist']
  for (const tab of DATA_GATED) {
    test(`"${tab}" nav button is clickable and becomes active`, async ({ page }) => {
      await page.locator(`button.nav[data-tab="${tab}"]`).click()
      await expect(page.locator(`button.nav[data-tab="${tab}"]`)).toHaveClass(/active/)
    })
  }
})
