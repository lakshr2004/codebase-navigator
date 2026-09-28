import { useCallback, useState } from 'react'

import { api } from '../services/api'

export function useQuery(repositoryId) {
  const [query, setQuery] = useState('')

  const [mode, setMode] = useState('exact')

  const [result, setResult] = useState(null)

  const [queryState, setQueryState] =
    useState('idle')

  const [error, setError] = useState('')

  const [historyLoading, setHistoryLoading] =
    useState(false)

  const [sessionId] = useState(
    () => `navigator-${crypto.randomUUID()}`
  )

  // ============================================================
  // ASK QUERY
  // ============================================================

  const askQuery = useCallback(
    async () => {
      const trimmedQuery = query.trim()

      if (!repositoryId) {
        setError(
          'Select a repository before searching it.'
        )

        return false
      }

      if (!trimmedQuery) {
        setError(
          'Enter a search or question first.'
        )

        return false
      }

      setError('')
      setQueryState('loading')

      try {
        const payload = await api.ask(
          trimmedQuery,
          repositoryId,
          sessionId
        )

        setResult(payload)
        setQueryState('ok')

        return true
      } catch (requestError) {
        console.error(
          'Query error:',
          requestError
        )

        setQueryState('error')

        setError(
          requestError?.message ||
            'Failed to process query.'
        )

        return false
      }
    },
    [
      query,
      repositoryId,
      sessionId,
    ]
  )

  // ============================================================
  // SUBMIT QUERY
  // ============================================================

  const handleQuery = useCallback(
    async (event) => {
      event?.preventDefault()

      return askQuery()
    },
    [askQuery]
  )

  // ============================================================
  // CLEAR RESULT
  // ============================================================

  const clearResult = useCallback(() => {
    setResult(null)
    setQueryState('idle')
  }, [])

  // ============================================================
  // CLEAR QUERY
  // ============================================================

  const clearQuery = useCallback(() => {
    setQuery('')
    setQueryState('idle')
  }, [])

  // ============================================================
  // CLEAR CONVERSATION
  // ============================================================

  const clearConversation = useCallback(
    async () => {
      try {
        setHistoryLoading(true)

        await api.clearConversation(
          sessionId
        )

        setResult(null)
        setQuery('')
        setQueryState('idle')
        setError('')

        return true
      } catch (requestError) {
        console.error(
          'Conversation clear error:',
          requestError
        )

        setError(
          requestError?.message ||
            'Failed to clear conversation.'
        )

        return false
      } finally {
        setHistoryLoading(false)
      }
    },
    [sessionId]
  )

  // ============================================================
  // LOAD CONVERSATION
  // ============================================================

  const loadConversation = useCallback(
    async () => {
      try {
        setHistoryLoading(true)

        const history =
          await api.conversation(
            sessionId
          )

        if (
          history?.messages &&
          Array.isArray(history.messages)
        ) {
          return history.messages
        }

        return []
      } catch (requestError) {
        console.error(
          'Conversation history error:',
          requestError
        )

        // Conversation history is optional.
        // Do not block the application.
        return []
      } finally {
        setHistoryLoading(false)
      }
    },
    [sessionId]
  )

  // ============================================================
  // SET QUERY
  // ============================================================

  const updateQuery = useCallback(
    (value) => {
      setQuery(value)
    },
    []
  )

  // ============================================================
  // SET MODE
  // ============================================================

  const updateMode = useCallback(
    (nextMode) => {
      setMode(nextMode)
    },
    []
  )

  // ============================================================
  // SET ERROR
  // ============================================================

  const clearError = useCallback(() => {
    setError('')
  }, [])

  // ============================================================
  // RETURN
  // ============================================================

  return {
    query,
    setQuery: updateQuery,

    mode,
    setMode: updateMode,

    result,

    queryState,
    error,

    historyLoading,
    sessionId,

    askQuery,
    handleQuery,

    clearResult,
    clearQuery,
    clearConversation,
    loadConversation,

    clearError,
  }
}