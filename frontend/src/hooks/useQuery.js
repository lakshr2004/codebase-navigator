import { useState } from 'react'
import { api } from '../services/api'

export function useQuery({
  activeRepositoryId,
  currentRepository,
  sessionId,
  setError,
}) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('exact')
  const [result, setResult] = useState(null)
  const [queryState, setQueryState] = useState('idle')

  async function handleQuery(event) {
    event.preventDefault()

    if (!activeRepositoryId) {
      setError('Select a repository before searching it.')
      return
    }

    if (!query.trim()) {
      setError('Enter a search or question first.')
      return
    }

    if (!currentRepository?.indexed) {
      setError('The selected repository is not indexed yet.')
      return
    }

    setError('')
    setQueryState('loading')

    try {
      const payload = await api.ask(
        query.trim(),
        activeRepositoryId,
        sessionId,
        mode
      )

      setResult(payload)
      setQueryState('ok')
    } catch (requestError) {
      console.error('Query error:', requestError)

      setQueryState('error')

      setError(
        requestError?.message ||
          'Failed to process query.'
      )
    }
  }

  async function handleClearConversation() {
    try {
      await api.clearConversation(sessionId)

      setResult(null)
      setQuery('')
      setQueryState('idle')
      setError('')
    } catch (requestError) {
      console.error(
        'Conversation clear error:',
        requestError
      )

      setError(
        requestError?.message ||
          'Failed to clear conversation.'
      )
    }
  }

  return {
    query,
    setQuery,

    mode,
    setMode,

    result,
    setResult,

    queryState,
    setQueryState,

    handleQuery,
    handleClearConversation,
  }
}