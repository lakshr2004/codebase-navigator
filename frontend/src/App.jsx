import { useEffect, useMemo, useState } from 'react'

import StatusPill from './components/ui/StatusPill'
import ErrorBanner from './components/ui/ErrorBanner'

import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronRight,
  Database,
  FileCode2,
  GitBranch,
  LoaderCircle,
  MessageSquareText,
  Search,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react'

import { api } from './services/api'

const SESSION_ID = `navigator-${crypto.randomUUID()}`
const ACTIVE_REPO_KEY = 'codebase-navigator-active-repo'

const examples = [
  'Where is loginUser defined?',
  'Find all usages of getRecords',
  'How does authentication work in this project?',
]

function SourceCard({ source, index }) {
  return (
    <article className="source-card">
      <div className="source-index">
        {String(index + 1).padStart(2, '0')}
      </div>

      <div className="source-body">
        <div className="source-meta">
          <span className="source-file">
            <FileCode2 size={15} />
            {source.file}
          </span>

          {source.language && (
            <span>{source.language}</span>
          )}

          {source.start_line && (
            <span>
              Ln {source.start_line}
              {source.end_line
                ? `-${source.end_line}`
                : ''}
            </span>
          )}
        </div>

        <div className="source-rule" />

        <p>
          Referenced by the backend response for this query.
        </p>
      </div>

      <ArrowUpRight
        className="source-arrow"
        size={17}
      />
    </article>
  )
}

export default function App() {
  const [repositories, setRepositories] = useState([])

  const [activeRepositoryId, setActiveRepositoryId] =
    useState('')

  const [repositoryName, setRepositoryName] =
    useState('No repository connected')

  const [ingestState, setIngestState] =
    useState('idle')

  const [query, setQuery] = useState('')

  const [mode, setMode] = useState('exact')

  const [result, setResult] = useState(null)

  const [queryState, setQueryState] =
    useState('idle')

  const [error, setError] = useState('')

  const [backendState, setBackendState] =
    useState('loading')

  const [readyState, setReadyState] =
    useState('loading')

  const [showRepoSelector, setShowRepoSelector] =
    useState(false)

  const [repoSelectionError, setRepoSelectionError] =
    useState('')

  const [historyLoading, setHistoryLoading] =
    useState(false)

  const canQuery =
    Boolean(activeRepositoryId) &&
    ingestState === 'ok'

  const currentRepository = useMemo(() => {
    return repositories.find(
      (repo) => repo.id === activeRepositoryId
    )
  }, [repositories, activeRepositoryId])

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
  // INITIALIZE APP
  // ============================================================

  useEffect(() => {
    let active = true

    async function initializeApp() {
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

        setBackendState(
          health.status === 'fulfilled'
            ? 'ok'
            : 'error'
        )

        setReadyState(
          readiness.status === 'fulfilled'
            ? 'ok'
            : 'error'
        )

        if (
          repositoryResponse.status ===
            'fulfilled' &&
          Array.isArray(repositoryResponse.value)
        ) {
          const availableRepositories =
            repositoryResponse.value

          setRepositories(
            availableRepositories
          )

          // ----------------------------------------------------
          // Restore previous repository
          // ----------------------------------------------------

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

              const matchedRepository =
                availableRepositories.find(
                  (repo) =>
                    repo.id === storedId
                )

              if (
                matchedRepository &&
                matchedRepository.indexed
              ) {
                setActiveRepositoryId(
                  matchedRepository.id
                )

                setRepositoryName(
                  matchedRepository.name
                )

                setIngestState('ok')

                return
              }
            } catch {
              localStorage.removeItem(
                ACTIVE_REPO_KEY
              )
            }
          }

          // ----------------------------------------------------
          // If exactly one indexed repository exists,
          // select it automatically.
          // ----------------------------------------------------

          const indexedRepositories =
            availableRepositories.filter(
              (repo) => repo.indexed
            )

          if (
            indexedRepositories.length === 1
          ) {
            const repo =
              indexedRepositories[0]

            selectRepositoryLocally(repo)
          }

          // ----------------------------------------------------
          // If multiple repositories exist,
          // keep selector open for user choice.
          // ----------------------------------------------------

          if (
            indexedRepositories.length > 1
          ) {
            setShowRepoSelector(true)
          }
        }
      } catch (initializationError) {
        if (!active) return

        console.error(
          'Initialization error:',
          initializationError
        )

        setBackendState('error')
        setReadyState('error')

        setError(
          'Failed to initialize Codebase Navigator.'
        )
      }
    }

    initializeApp()

    return () => {
      active = false
    }
  }, [])

  // ============================================================
  // LOCAL REPOSITORY SELECTION
  // ============================================================

  function selectRepositoryLocally(repo) {
    if (!repo) return

    setActiveRepositoryId(repo.id)
    setRepositoryName(repo.name)

    setIngestState(
      repo.indexed ? 'ok' : 'idle'
    )

    setResult(null)
    setQuery('')
    setQueryState('idle')
    setError('')
    setRepoSelectionError('')

    localStorage.setItem(
      ACTIVE_REPO_KEY,
      JSON.stringify({
        repository_id: repo.id,
      })
    )
  }

  // ============================================================
  // SELECT REPOSITORY
  // ============================================================

  async function handleRepositorySelect(repo) {
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

    // Try to restore conversation history
    try {
      setHistoryLoading(true)

      const history =
        await api.getConversation(
          SESSION_ID
        )

      if (
        history?.messages &&
        Array.isArray(history.messages)
      ) {
        console.log(
          'Conversation history loaded:',
          history.messages
        )
      }
    } catch {
      // History is optional.
      // Do not block repository selection.
    } finally {
      setHistoryLoading(false)
    }
  }

  // ============================================================
  // INDEX SELECTED REPOSITORY
  // ============================================================

  async function handleIndexRepository() {
    if (!activeRepositoryId) {
      setError(
        'Select a repository before indexing.'
      )
      return
    }

    setError('')
    setIngestState('loading')
    setResult(null)

    try {
      const response =
        await api.indexRepository(
          activeRepositoryId
        )

      console.log(
        'Repository indexed:',
        response
      )

      // Refresh repository state
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
      } else {
        setIngestState('error')

        setError(
          'Repository indexing completed, but the repository is still not marked as indexed.'
        )
      }
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
    setRepositoryName(
      'No repository connected'
    )

    setIngestState('idle')
    setResult(null)
    setQuery('')
    setQueryState('idle')
    setError('')
  }

  // ============================================================
  // ASK QUERY
  // ============================================================

  async function handleQuery(event) {
    event.preventDefault()

    if (!activeRepositoryId) {
      setError(
        'Select a repository before searching it.'
      )
      return
    }

    if (!query.trim()) {
      setError(
        'Enter a search or question first.'
      )
      return
    }

    if (!currentRepository?.indexed) {
      setError(
        'The selected repository is not indexed yet.'
      )
      return
    }

    setError('')
    setQueryState('loading')

    try {
      const payload = await api.ask(
  query.trim(),
  activeRepositoryId,
  SESSION_ID,
  mode
)

      setResult(payload)
      setQueryState('ok')
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
    }
  }

  // ============================================================
  // CLEAR CONVERSATION
  // ============================================================

  async function handleClearConversation() {
    try {
      await api.clearConversation(
        SESSION_ID
      )

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

  return (
    <div className="app-shell font-display">

      {/* ======================================================
          TOPBAR
      ====================================================== */}

      <header className="topbar">

        <div className="brand-lockup">

          <div className="brand-mark">
            <Terminal size={19} />
          </div>

          <div>
            <strong>CODEBASE</strong>
            <span>NAVIGATOR</span>
          </div>

        </div>

        <div className="topbar-right">

          <StatusPill
            state={backendState}
            label={
              backendState === 'ok'
                ? 'API online'
                : backendState === 'loading'
                  ? 'API checking'
                  : 'API offline'
            }
          />

          <span className="build-label">
            LOCAL WORKSPACE / 0.1
          </span>

        </div>

      </header>

      <main className="workspace">

        {/* ====================================================
            INTRO
        ==================================================== */}

        <section className="intro-grid">

          <div className="intro-copy">

            <div className="eyebrow">
              <span className="eyebrow-line" />
              REPOSITORY INTELLIGENCE
            </div>

            <h1>
              Read the codebase
              <br />
              <em>between the lines.</em>
            </h1>

            <p>
              Explore your indexed repositories,
              search exact identifiers, and ask
              grounded architectural questions
              without leaving your workspace.
            </p>

          </div>

          <div className="signal-panel">

            <div className="signal-grid" />

            <Sparkles
              className="signal-icon"
              size={27}
            />

            <span>
              DETERMINISTIC SEARCH
              <br />
              + GROUNDED RAG
            </span>

          </div>

        </section>

        {/* ====================================================
            ERROR
        ==================================================== */}

        <ErrorBanner
          message={error}
          onDismiss={() => setError('')}
        />

        {/* ====================================================
            CONTROL GRID
        ==================================================== */}

        <section className="control-grid">

          {/* ==================================================
              REPOSITORY PANEL
          ================================================== */}

          <div className="panel ingest-panel">

            <div className="panel-heading">

              <div>

                <span className="section-kicker">
                  01 / REPOSITORY
                </span>

                <h2>
                  Choose a repository
                </h2>

              </div>

              <GitBranch size={20} />

            </div>

            <p className="panel-note">
              Codebase Navigator currently
              supports the two configured local
              repositories below.
            </p>

            <div className="repository-choice-grid">

              {repositories.length === 0 && (
                <div className="empty-repository-choice">
                  <LoaderCircle
                    className="spin"
                    size={18}
                  />

                  <span>
                    Loading repositories...
                  </span>
                </div>
              )}

              {repositories.map((repo) => {

                const isActive =
                  repo.id ===
                  activeRepositoryId

                return (
                  <button
                    key={repo.id}
                    type="button"
                    className={`repository-choice ${
                      isActive
                        ? 'active'
                        : ''
                    }`}
                    onClick={() =>
                      handleRepositorySelect(
                        repo
                      )
                    }
                    disabled={!repo.indexed}
                  >

                    <div className="repository-choice-icon">
                      <Database size={17} />
                    </div>

                    <div className="repository-choice-content">

                      <strong>
                        {repo.name}
                      </strong>

                      <span>
                        {repo.indexed
                          ? 'Indexed and ready'
                          : 'Not indexed'}
                      </span>

                    </div>

                    {isActive &&
                      repo.indexed && (
                        <Check size={17} />
                      )}

                  </button>
                )
              })}

            </div>

            <div className="input-row repository-action-row">

              <button
                type="button"
                className="primary-button"
                disabled={
                  !activeRepositoryId ||
                  ingestState ===
                    'loading'
                }
                onClick={
                  handleIndexRepository
                }
              >

                {ingestState ===
                'loading' ? (
                  <LoaderCircle
                    className="spin"
                    size={17}
                  />
                ) : (
                  <ArrowUpRight size={17} />
                )}

                {ingestState ===
                'loading'
                  ? 'Indexing'
                  : 'Re-index repository'}

              </button>

            </div>

            <div className="panel-foot">

              <StatusPill
                state={
                  ingestState === 'ok'
                    ? 'ok'
                    : ingestState ===
                        'loading'
                      ? 'loading'
                      : 'idle'
                }
                label={currentLabel}
              />

              <span className="foot-detail">
                {currentRepository
                  ? currentRepository.repository_path
                  : 'No repository selected'}
              </span>

            </div>

          </div>

          {/* ==================================================
              CURRENT CONTEXT
          ================================================== */}

          <aside className="panel repo-panel">

            <div className="panel-heading">

              <div>

                <span className="section-kicker">
                  CURRENT CONTEXT
                </span>

                <h2>
                  {repositoryName}
                </h2>

              </div>

              {activeRepositoryId && (
                <button
                  className="icon-button"
                  onClick={
                    handleClearActiveRepo
                  }
                  aria-label="Disconnect repository"
                  type="button"
                >
                  <X size={16} />
                </button>
              )}

            </div>

            <div className="repo-status">

              <div className="repo-status-icon">
                {currentRepository?.indexed ? (
                  <Check size={18} />
                ) : (
                  <Database size={18} />
                )}
              </div>

              <div>

                <strong>
                  {currentRepository?.indexed
                    ? 'Ready to explore'
                    : activeRepositoryId
                      ? 'Repository unavailable'
                      : 'Select a repository'}
                </strong>

                <span>
                  {readyState === 'ok'
                    ? 'Runtime configuration ready'
                    : readyState ===
                        'loading'
                      ? 'Checking runtime configuration'
                      : 'Readiness unavailable'}
                </span>

              </div>

            </div>

            <div className="mini-stats">

              <div>
                <span>REPOSITORY ID</span>

                <strong>
                  {activeRepositoryId
                    ? activeRepositoryId.toUpperCase()
                    : '—'}
                </strong>
              </div>

              <div>
                <span>MODE</span>

                <strong>
                  {mode === 'exact'
                    ? 'IDENTIFIER'
                    : 'SEMANTIC'}
                </strong>
              </div>

            </div>

            <div className="mini-stats">

              <div>
                <span>SESSION</span>

                <strong>
                  {SESSION_ID
                    .slice(-6)
                    .toUpperCase()}
                </strong>
              </div>

              <div>
                <span>INDEXED</span>

                <strong>
                  {repositories.filter(
                    (repo) =>
                      repo.indexed
                  ).length}
                  /{repositories.length}
                </strong>
              </div>

            </div>

          </aside>

        </section>

        {/* ====================================================
            QUERY SECTION
        ==================================================== */}

        <section className="query-section">

          <div className="section-header">

            <div>

              <span className="section-kicker">
                02 / EXPLORE
              </span>

              <h2>
                Ask the repository
              </h2>

            </div>

            <span className="query-hint">
              {canQuery
                ? `Collection active · ${repositoryName}`
                : 'Select an indexed repository to unlock search'}
            </span>

          </div>

          {/* ==================================================
              MODE TABS
          ================================================== */}

          <div
            className="mode-tabs"
            role="tablist"
            aria-label="Query mode"
          >

            <button
              type="button"
              className={
                mode === 'exact'
                  ? 'active'
                  : ''
              }
              onClick={() =>
                setMode('exact')
              }
            >
              <Search size={15} />
              Exact lookup
            </button>

            <button
              type="button"
              className={
                mode === 'semantic'
                  ? 'active'
                  : ''
              }
              onClick={() =>
                setMode('semantic')
              }
            >
              <MessageSquareText
                size={15}
              />
              Conceptual answer
            </button>

          </div>

          {/* ==================================================
              QUERY FORM
          ================================================== */}

          <form
            onSubmit={handleQuery}
            className="query-form"
          >

            <textarea
              value={query}
              onChange={(event) =>
                setQuery(event.target.value)
              }
              disabled={!canQuery}
              placeholder={
                mode === 'exact'
                  ? 'Where is loginUser defined? / Find all usages of getRecords'
                  : 'How does authentication work in this project?'
              }
              aria-label="Repository query"
            />

            <div className="query-footer">

              <div className="examples">

                {examples.map(
                  (example) => (
                    <button
                      type="button"
                      key={example}
                      onClick={() =>
                        setQuery(
                          example
                        )
                      }
                      disabled={!canQuery}
                    >
                      {example}
                    </button>
                  )
                )}

              </div>

              <button
                className="query-button"
                disabled={
                  !canQuery ||
                  queryState ===
                    'loading'
                }
                type="submit"
              >

                {queryState ===
                'loading' ? (
                  <LoaderCircle
                    className="spin"
                    size={17}
                  />
                ) : (
                  <ChevronRight
                    size={17}
                  />
                )}

                Run query

              </button>

            </div>

          </form>

          {/* ==================================================
              CONVERSATION ACTIONS
          ================================================== */}

          {result && (
            <div className="conversation-actions">

              <button
                type="button"
                className="secondary-button"
                onClick={
                  handleClearConversation
                }
                disabled={historyLoading}
              >
                Clear conversation
              </button>

            </div>
          )}

        </section>

        {/* ====================================================
            RESULTS
        ==================================================== */}

        <section className="results-section">

          <div className="section-header">

            <div>

              <span className="section-kicker">
                03 / OUTPUT
              </span>

              <h2>
                Evidence and answer
              </h2>

            </div>

            {result && (
              <span className="result-count">
                {result.sources?.length || 0}{' '}
                source references
              </span>
            )}

          </div>

          {/* ==================================================
              EMPTY STATE
          ================================================== */}

          {!result && (
            <div className="empty-state">

              <div className="empty-orbit">
                <Search size={22} />
              </div>

              <strong>
                Nothing queried yet
              </strong>

              <span>
                Your answer will appear here
                with file-level source references.
              </span>

            </div>
          )}

          {/* ==================================================
              RESULTS
          ================================================== */}

          {result && (
            <div className="results-layout">

              <article className="answer-panel">

                <div className="answer-label">
                  <Sparkles size={15} />
                  GROUNDED RESPONSE
                </div>

                <p>
                  {result.answer}
                </p>

                <div className="answer-query">
                  QUERY / {result.query}
                </div>

              </article>

              <div className="sources-list">

                {result.sources?.length ? (
                  result.sources.map(
                    (source, index) => (
                      <SourceCard
                        source={source}
                        index={index}
                        key={`${source.file}-${index}`}
                      />
                    )
                  )
                ) : (
                  <div className="empty-sources">
                    No source references
                    returned for this query.
                  </div>
                )}

              </div>

            </div>
          )}

        </section>

      </main>

      {/* ======================================================
          FOOTER
      ====================================================== */}

      <footer className="footer">

        <span>
          <Activity size={14} />
          CODEBASE NAVIGATOR /
          LOCAL-FIRST INTELLIGENCE
        </span>

        <span>
          FASTAPI + QDRANT + GROQ
        </span>

      </footer>

      {/* ======================================================
          REPOSITORY SELECTOR MODAL
      ====================================================== */}

      {showRepoSelector && (
        <div
          className="modal-overlay"
          onClick={() =>
            setShowRepoSelector(false)
          }
          role="dialog"
          aria-modal="true"
          aria-labelledby="repo-selector-title"
        >

          <div
            className="modal-content"
            onClick={(event) =>
              event.stopPropagation()
            }
          >

            <div className="modal-header">

              <div>
                <span className="section-kicker">
                  REPOSITORY CONTEXT
                </span>

                <h3 id="repo-selector-title">
                  Select repository
                </h3>
              </div>

              <button
                className="icon-button"
                onClick={() =>
                  setShowRepoSelector(
                    false
                  )
                }
                aria-label="Close"
                type="button"
              >
                <X size={18} />
              </button>

            </div>

            {repoSelectionError && (
              <div className="modal-error">
                {repoSelectionError}
              </div>
            )}

            <ul className="repo-list">

              {repositories.map(
                (repo) => {

                  const isActive =
                    repo.id ===
                    activeRepositoryId

                  return (
                    <li
                      key={repo.id}
                      className={
                        isActive
                          ? 'active'
                          : ''
                      }
                      onClick={() => {
                        if (
                          repo.indexed
                        ) {
                          handleRepositorySelect(
                            repo
                          )
                        }
                      }}
                      aria-disabled={
                        !repo.indexed
                      }
                    >

                      <Database size={18} />

                      <div>
                        <strong>
                          {repo.name}
                        </strong>

                        <span>
                          {repo.indexed
                            ? 'Indexed and ready'
                            : 'Not indexed'}
                        </span>
                      </div>

                      {isActive &&
                        repo.indexed && (
                          <Check
                            size={16}
                          />
                        )}

                    </li>
                  )
                }
              )}

            </ul>

            <button
              className="modal-close-btn"
              onClick={() =>
                setShowRepoSelector(
                  false
                )
              }
              type="button"
            >
              Cancel
            </button>

          </div>

        </div>
      )}

    </div>
  )
}