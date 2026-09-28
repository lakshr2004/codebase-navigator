import { useCallback, useEffect, useMemo, useState } from 'react'

import { api } from '../services/api'

const ACTIVE_REPO_KEY = 'codebase-navigator-active-repo'

export function useRepository() {
  const [repositories, setRepositories] = useState([])

  const [activeRepositoryId, setActiveRepositoryId] =
    useState('')

  const [repositoryName, setRepositoryName] =
    useState('No repository connected')

  const [ingestState, setIngestState] =
    useState('idle')

  const [backendState, setBackendState] =
    useState('loading')

  const [readyState, setReadyState] =
    useState('loading')

  const [error, setError] = useState('')

  const [repoSelectionError, setRepoSelectionError] =
    useState('')

  const [showRepoSelector, setShowRepoSelector] =
    useState(false)

  const currentRepository = useMemo(() => {
    return repositories.find(
      (repo) => repo.id === activeRepositoryId
    )
  }, [repositories, activeRepositoryId])

  const canQuery =
    Boolean(activeRepositoryId) &&
    ingestState === 'ok' &&
    Boolean(currentRepository?.indexed)

  const currentLabel = useMemo(() => {
    if (ingestState === 'loading') {
      return 'Indexing repository'
    }

    if (activeRepositoryId) {
      return currentRepository?.indexed
        ? 'Repository indexed'
        : 'Repository not indexed'
    }

    return 'Awaiting repository'
  }, [
    ingestState,
    activeRepositoryId,
    currentRepository,
  ])

  // ============================================================
  // LOCAL REPOSITORY SELECTION
  // ============================================================

  const selectRepositoryLocally = useCallback((repo) => {
    if (!repo) return

    setActiveRepositoryId(repo.id)
    setRepositoryName(repo.name)

    setIngestState(
      repo.indexed ? 'ok' : 'idle'
    )

    localStorage.setItem(
      ACTIVE_REPO_KEY,
      JSON.stringify({
        repository_id: repo.id,
      })
    )
  }, [])

  // ============================================================
  // INITIALIZE
  // ============================================================

  useEffect(() => {
    let active = true

    async function initializeRepositoryState() {
      try {
        const [
          health,
          readiness,
          repositoryResponse,
        ] = await Promise.allSettled([
          api.health(),
          api.readiness(),
          api.repositories(),
        ])

        if (!active) return

        // --------------------------------------------------------
        // Backend state
        // --------------------------------------------------------

        setBackendState(
          health.status === 'fulfilled'
            ? 'ok'
            : 'error'
        )

        // --------------------------------------------------------
        // Readiness state
        // --------------------------------------------------------

        setReadyState(
          readiness.status === 'fulfilled'
            ? 'ok'
            : 'error'
        )

        // --------------------------------------------------------
        // Repository state
        // --------------------------------------------------------

        if (
          repositoryResponse.status !== 'fulfilled' ||
          !Array.isArray(repositoryResponse.value)
        ) {
          setError(
            'Failed to load repositories.'
          )

          return
        }

        const availableRepositories =
          repositoryResponse.value

        setRepositories(
          availableRepositories
        )

        // --------------------------------------------------------
        // Restore previous repository
        // --------------------------------------------------------

        const storedRepository =
          localStorage.getItem(
            ACTIVE_REPO_KEY
          )

        if (storedRepository) {
          try {
            const parsed =
              JSON.parse(storedRepository)

            const storedId =
              parsed?.repository_id

            const matchedRepository =
              availableRepositories.find(
                (repo) =>
                  repo.id === storedId
              )

            if (
              matchedRepository &&
              matchedRepository.indexed
            ) {
              selectRepositoryLocally(
                matchedRepository
              )

              return
            }
          } catch {
            localStorage.removeItem(
              ACTIVE_REPO_KEY
            )
          }
        }

        // --------------------------------------------------------
        // Automatically select if exactly one is indexed
        // --------------------------------------------------------

        const indexedRepositories =
          availableRepositories.filter(
            (repo) => repo.indexed
          )

        if (
          indexedRepositories.length === 1
        ) {
          selectRepositoryLocally(
            indexedRepositories[0]
          )

          return
        }

        // --------------------------------------------------------
        // Multiple indexed repositories
        // --------------------------------------------------------

        if (
          indexedRepositories.length > 1
        ) {
          setShowRepoSelector(true)
        }
      } catch (initializationError) {
        if (!active) return

        console.error(
          'Repository initialization error:',
          initializationError
        )

        setBackendState('error')
        setReadyState('error')

        setError(
          'Failed to initialize Codebase Navigator.'
        )
      }
    }

    initializeRepositoryState()

    return () => {
      active = false
    }
  }, [selectRepositoryLocally])

  // ============================================================
  // SELECT REPOSITORY
  // ============================================================

  const selectRepository = useCallback(
    async (repo) => {
      setRepoSelectionError('')
      setError('')

      if (!repo) {
        setRepoSelectionError(
          'Invalid repository selection.'
        )

        return
      }

      if (!repo.indexed) {
        setRepoSelectionError(
          `${repo.name} is not indexed yet.`
        )

        return
      }

      selectRepositoryLocally(repo)

      setShowRepoSelector(false)
    },
    [selectRepositoryLocally]
  )

  // ============================================================
  // INDEX REPOSITORY
  // ============================================================

  const indexRepository = useCallback(
    async () => {
      if (!activeRepositoryId) {
        setError(
          'Select a repository before indexing.'
        )

        return false
      }

      setError('')
      setIngestState('loading')

      try {
        const response =
          await api.indexRepository(
            activeRepositoryId
          )

        console.log(
          'Repository indexed:',
          response
        )

        // ------------------------------------------------------
        // Refresh repository state
        // ------------------------------------------------------

        const updatedRepositories =
          await api.repositories()

        setRepositories(
          updatedRepositories
        )

        const updatedRepository =
          updatedRepositories.find(
            (repo) =>
              repo.id === activeRepositoryId
          )

        if (
          updatedRepository &&
          updatedRepository.indexed
        ) {
          setRepositoryName(
            updatedRepository.name
          )

          setIngestState('ok')

          localStorage.setItem(
            ACTIVE_REPO_KEY,
            JSON.stringify({
              repository_id:
                updatedRepository.id,
            })
          )

          return true
        }

        setIngestState('error')

        setError(
          'Repository indexing completed, but the repository is still not marked as indexed.'
        )

        return false
      } catch (requestError) {
        console.error(
          'Repository indexing error:',
          requestError
        )

        setIngestState('error')

        setError(
          requestError?.message ||
            'Failed to index repository.'
        )

        return false
      }
    },
    [activeRepositoryId]
  )

  // ============================================================
  // CLEAR ACTIVE REPOSITORY
  // ============================================================

  const clearActiveRepository = useCallback(() => {
    localStorage.removeItem(
      ACTIVE_REPO_KEY
    )

    setActiveRepositoryId('')
    setRepositoryName(
      'No repository connected'
    )

    setIngestState('idle')
    setError('')
    setRepoSelectionError('')
  }, [])

  // ============================================================
  // OPEN / CLOSE SELECTOR
  // ============================================================

  const openRepositorySelector = useCallback(() => {
    setRepoSelectionError('')
    setShowRepoSelector(true)
  }, [])

  const closeRepositorySelector = useCallback(() => {
    setRepoSelectionError('')
    setShowRepoSelector(false)
  }, [])

  // ============================================================
  // CLEAR ERROR
  // ============================================================

  const clearError = useCallback(() => {
    setError('')
  }, [])

  // ============================================================
  // RETURN
  // ============================================================

  return {
    // Repository data
    repositories,
    activeRepositoryId,
    repositoryName,
    currentRepository,

    // Repository state
    ingestState,
    backendState,
    readyState,
    currentLabel,
    canQuery,

    // Errors
    error,
    repoSelectionError,

    // Selector
    showRepoSelector,

    // Actions
    selectRepository,
    indexRepository,
    clearActiveRepository,

    openRepositorySelector,
    closeRepositorySelector,

    clearError,
  }
}