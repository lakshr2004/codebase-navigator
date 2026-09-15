import { test, expect } from '@playwright/test'

test('application loads the developer workspace', async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto('/')
  await expect(page.locator('.brand-lockup strong')).toHaveText('CODEBASE')
  await expect(page.getByRole('heading', { name: /Read the codebase/ })).toBeVisible()
  expect(errors).toEqual([])
})

test('repository validation keeps the workspace usable', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Index repository/ }).click()
  await expect(page.getByRole('alert')).toContainText('Enter a public GitHub repository URL')
  await expect(page.getByRole('heading', { name: 'Ask the repository' })).toBeVisible()
})