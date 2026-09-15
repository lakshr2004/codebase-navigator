const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

async function request(path, options = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    })

    const contentType = response.headers.get('content-type') || ''
    const payload = contentType.includes('application/json')
      ? await response.json()
      : await response.text()

    if (!response.ok) {
      const message = typeof payload === 'object' && payload?.detail
        ? payload.detail
        : 'The backend returned an unexpected error.'
      throw new Error(message)
    }

    return payload
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('The request timed out. Check the backend and try again.')
    }
    if (error instanceof TypeError) {
      throw new Error('The backend is unavailable. Start FastAPI and try again.')
    }
    throw error
  } finally {
    clearTimeout(timeout)
  }
}

export const api = {
  health: () => request('/health'),
  readiness: () => request('/ready'),
  repositories: () => request('/repositories'),
  loadRepository: (repoUrl) => request('/repositories/load', {
    method: 'POST',
    body: JSON.stringify({ repo_url: repoUrl }),
  }),
  ask: (query, repositoryPath, sessionId) => request('/ask', {
    method: 'POST',
    body: JSON.stringify({
      query,
      repository_path: repositoryPath,
      session_id: sessionId,
    }),
  }),
}

export { API_BASE_URL }
