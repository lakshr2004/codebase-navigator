import { test, expect } from '@playwright/test'

const ACTIVE_REPO_KEY = 'codebase-navigator-active-repo'

const repositories = [
  {
    id: 'monetrik',
    name: 'monetrik',
    collection_name: 'codebase_chunks_monetrik',
    repository_path: 'data/repos/monetrik',
    indexed: true,
  },
  {
    id: 'ticketpechalo',
    name: 'TicketPeChalo.in',
    collection_name: 'codebase_chunks_ticketpechalo_in',
    repository_path: 'data/repos/TicketPeChalo.in',
    indexed: true,
  },
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript((repoList) => {
    const response = (path, payload) => ({
      ok: true,
      status: 200,
      headers: { get: (name) => (name === 'content-type' ? 'application/json' : '') },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    })

    window.fetch = async (input) => {
      const url = String(input)

      if (url.endsWith('/health')) {
        return response(url, { status: 'healthy' })
      }

      if (url.endsWith('/ready')) {
        return response(url, { status: 'ready' })
      }

      if (url.endsWith('/repositories')) {
        return response(url, repoList)
      }

      if (url.includes('/repositories/')) {
        return response(url, { message: 'Repository indexed successfully' })
      }

      return response(url, {})
    }
  }, repositories)
})

test('repository selection persists the backend repository path', async ({ page }) => {
  await page.goto('/')

  await expect(page.locator('.repository-choice')).toHaveCount(2)

  await page.evaluate(() => {
    const button = [...document.querySelectorAll('.repository-choice')].find((element) =>
      element.textContent.includes('monetrik')
    )
    if (button) button.click()
  })

  const stored = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), ACTIVE_REPO_KEY)

  expect(stored).toMatchObject({
    repository_id: 'monetrik',
    name: 'monetrik',
    collection_name: 'codebase_chunks_monetrik',
    repository_path: 'data/repos/monetrik',
  })
})

test('repository switching refreshes the selected repository metadata', async ({ page }) => {
  await page.goto('/')

  await page.evaluate(() => {
    const button = [...document.querySelectorAll('.repository-choice')].find((element) =>
      element.textContent.includes('monetrik')
    )
    if (button) button.click()
  })

  let stored = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), ACTIVE_REPO_KEY)
  expect(stored.repository_path).toBe('data/repos/monetrik')

  await page.evaluate(() => {
    const button = [...document.querySelectorAll('.repository-choice')].find((element) =>
      element.textContent.includes('TicketPeChalo')
    )
    if (button) button.click()
  })

  stored = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), ACTIVE_REPO_KEY)
  expect(stored.repository_path).toBe('data/repos/TicketPeChalo.in')
  expect(stored.collection_name).toBe('codebase_chunks_ticketpechalo_in')

  await page.evaluate(() => {
    const button = [...document.querySelectorAll('.repository-choice')].find((element) =>
      element.textContent.includes('monetrik')
    )
    if (button) button.click()
  })

  stored = await page.evaluate((key) => JSON.parse(localStorage.getItem(key)), ACTIVE_REPO_KEY)
  expect(stored.repository_path).toBe('data/repos/monetrik')
  expect(stored.collection_name).toBe('codebase_chunks_monetrik')
})
