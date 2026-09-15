import { test, expect } from '@playwright/test'

test('frontend reaches the FastAPI health endpoint', async ({ page }) => {
  await page.goto('/')
  await expect.poll(async () => {
    return page.locator('.status-pill').first().textContent()
  }).toContain('API online')
})