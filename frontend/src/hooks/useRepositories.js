import { useEffect, useMemo, useState } from 'react'
import { api } from '../services/api'

const ACTIVE_REPO_KEY = 'codebase-navigator-active-repo'

export function useRepositories({
  setError,
  setResult,
  setQuery,
  setQueryState,
}) {
  // ============================================================
  // REPOSITORY STATE
  // ============================================================

  const [repositories, setRepositories] = useState([])
  const [activeRepositoryId, setActiveRepositoryId] =
    useState('')

  const [ingestState, setIngestState] =
    useState('idle')

  const [showRepoSelector, setShowRepoSelector] =
    useState(false)

  const [repoSelectionError, setRepoSelectionError] =
    useState('')

  const [historyLoading, setHistoryLoading] =
    useState(false)

  // ============================================================
  // DERIVED STATE
  // ============================================================

  const currentRepository = useMemo(() => {
    return repositories.find(
      (repo) => repo.id === activeRepositoryId
    )
  }, [
    repositories,
    activeRepositoryId,
  ])

  const repositoryName =
    currentRepository?.name ||
    'No repository connected'

  const canQuery =
    Boolean(activeRepositoryId) &&
    ingestState === 'ok'

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
  // ERROR HANDLING
  // ============================================================

  function clearRepositoryErrors() {
    setError('')
    setRepoSelectionError('')
  }

  // ============================================================
  // LOCAL REPOSITORY SELECTION
  // ============================================================

  function selectRepositoryLocally(repo) {
    if (!repo) {
      return
    }

    setActiveRepositoryId(repo.id)

    setIngestState(
      repo.indexed ? 'ok' : 'idle'
    )

    // Clear previous query state when repository changes.
    setResult(null)
    setQuery('')
    setQueryState('idle')

    clearRepositoryErrors()

    // Persist active repository.
    localStorage.setItem(
      ACTIVE_REPO_KEY,
      JSON.stringify({
        repository_id: repo.id,
        name: repo.name,
        collection_name:
          repo.collection_name,
        repository_path:
          repo.repository_path,
      })
    )
  }

  // ============================================================
  // SELECT REPOSITORY
  // ============================================================

  async function handleRepositorySelect(
    repo,
    sessionId
  ) {
    clearRepositoryErrors()

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

    // ----------------------------------------------------------
    // Restore conversation history
    // ----------------------------------------------------------

    try {
      setHistoryLoading(true)

      const history =
        await api.conversation(sessionId)

      if (
        history?.messages &&
        Array.isArray(history.messages)
      ) {
        console.log(
          'Conversation history loaded:',
          history.messages
        )
      }
    } catch (historyError) {
      // Conversation history is optional.
      // Repository selection should still succeed.
      console.warn(
        'Could not restore conversation history:',
        historyError
      )
    } finally {
      setHistoryLoading(false)
    }
  }

  // ============================================================
  // INDEX ACTIVE REPOSITORY
  // ============================================================

  async function handleIndexRepository() {
    if (!activeRepositoryId) {
      setError(
        'Select a repository before indexing.'
      )
      return
    }

    setError('')
    setRepoSelectionError('')
    setIngestState('loading')
    setResult(null)
    setQueryState('idle')

    try {
      // --------------------------------------------------------
      // Start indexing
      // --------------------------------------------------------

      const response =
        await api.indexRepository(
          activeRepositoryId
        )

      console.log(
        'Repository indexed:',
        response
      )

      // --------------------------------------------------------
      // Refresh repository list
      // --------------------------------------------------------

      const updatedRepositories =
        await api.repositories()

      setRepositories(
        updatedRepositories
      )

      // --------------------------------------------------------
      // Resolve updated active repository
      // --------------------------------------------------------

      const updatedRepository =
        updatedRepositories.find(
          (repo) =>
            repo.id === activeRepositoryId
        )

      if (
        updatedRepository &&
        updatedRepository.indexed
      ) {
        setIngestState('ok')

        // Persist latest repository metadata.
        localStorage.setItem(
          ACTIVE_REPO_KEY,
          JSON.stringify({
            repository_id:
              updatedRepository.id,

            name:
              updatedRepository.name,

            collection_name:
              updatedRepository.collection_name,

            repository_path:
              updatedRepository.repository_path,
          })
        )

        return
      }

      // --------------------------------------------------------
      // Indexing request succeeded but repository is not marked
      // as indexed.
      // --------------------------------------------------------

      setIngestState('error')

      setError(
        'Repository indexing completed, but the repository is still not marked as indexed.'
      )
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
    }
  }

  // ============================================================
  // DISCONNECT ACTIVE REPOSITORY
  // ============================================================

  function handleClearActiveRepo() {
    localStorage.removeItem(
      ACTIVE_REPO_KEY
    )

    setActiveRepositoryId('')
    setIngestState('idle')

    setResult(null)
    setQuery('')
    setQueryState('idle')

    clearRepositoryErrors()
  }

  // ============================================================
  // INITIALIZE REPOSITORIES
  // ============================================================

  useEffect(() => {
    let active = true

    async function initializeRepositories() {
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

        if (!active) {
          return
        }

        // ------------------------------------------------------
        // Repository API must succeed.
        // ------------------------------------------------------

        if (
          repositoryResponse.status !==
            'fulfilled' ||
          !Array.isArray(
            repositoryResponse.value
          )
        ) {
          setError(
            'Failed to load repositories from the backend.'
          )

          return
        }

        const availableRepositories =
          repositoryResponse.value

        setRepositories(
          availableRepositories
        )

        // ------------------------------------------------------
        // Restore previously selected repository.
        // ------------------------------------------------------

        const storedRepository =
          localStorage.getItem(
            ACTIVE_REPO_KEY
          )

        if (storedRepository) {
          try {
            const parsed =
              JSON.parse(
                storedRepository
              )

            const storedId =
              parsed?.repository_id

            const storedPath =
              parsed?.repository_path

            const storedCollectionName =
              parsed?.collection_name

            const matchedRepository =
              availableRepositories.find(
                (repo) =>
                  repo.id === storedId ||
                  repo.repository_path ===
                    storedPath ||
                  repo.collection_name ===
                    storedCollectionName
              )

            if (
              matchedRepository &&
              matchedRepository.indexed
            ) {
              setActiveRepositoryId(
                matchedRepository.id
              )

              setIngestState('ok')

              return
            }

            // Stored repository no longer exists
            // or is no longer indexed.
            localStorage.removeItem(
              ACTIVE_REPO_KEY
            )
          } catch (storageError) {
            console.warn(
              'Invalid stored repository state:',
              storageError
            )

            localStorage.removeItem(
              ACTIVE_REPO_KEY
            )
          }
        }

        // ------------------------------------------------------
        // Automatically select the only indexed repository.
        // ------------------------------------------------------

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

        // ------------------------------------------------------
        // If multiple indexed repositories exist,
        // let the user choose.
        // ------------------------------------------------------

        if (
          indexedRepositories.length > 1
        ) {
          setShowRepoSelector(true)
        }

        // ------------------------------------------------------
        // No indexed repositories.
        // ------------------------------------------------------

        if (
          indexedRepositories.length === 0
        ) {
          setIngestState('idle')
        }

        // Keep these variables intentionally evaluated.
        // The health/readiness requests are part of the
        // initialization contract.
        if (
          health.status === 'rejected' ||
          readiness.status === 'rejected'
        ) {
          console.warn(
            'Backend health/readiness check failed during repository initialization.'
          )
        }
      } catch (initializationError) {
        if (!active) {
          return
        }

        console.error(
          'Repository initialization error:',
          initializationError
        )

        setError(
          'Failed to initialize Codebase Navigator.'
        )
      }
    }

    initializeRepositories()

    return () => {
      active = false
    }
  }, [])

  // ============================================================
  // PUBLIC API OF HOOK
  // ============================================================

  return {
    // Repository collection
    repositories,
    setRepositories,

    // Active repository
    activeRepositoryId,
    setActiveRepositoryId,

    // Indexing
    ingestState,
    setIngestState,

    // Derived state
    currentRepository,
    repositoryName,
    canQuery,
    currentLabel,

    // Selector
    showRepoSelector,
    setShowRepoSelector,

    repoSelectionError,
    setRepoSelectionError,

    // Conversation
    historyLoading,

    // Actions
    handleRepositorySelect,
    handleIndexRepository,
    handleClearActiveRepo,
  }
}