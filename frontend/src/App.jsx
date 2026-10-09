import { useEffect, useState } from 'react'

import { useRepositories } from './hooks/useRepositories'
import { useQuery } from './hooks/useQuery'

import StatusPill from './components/ui/StatusPill'
import ErrorBanner from './components/ui/ErrorBanner'
import IconButton from './components/ui/IconButton'
import SourceCard from './components/sources/SourceCard'

import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronRight,
  Database,
  Folder,
  GitBranch,
  LoaderCircle,
  MessageSquareText,
  Search,
  Sparkles,
  Terminal,
  X,
} from 'lucide-react'

import { api } from './services/api'


// ============================================================
// SESSION
// ============================================================

const SESSION_ID = `navigator-${crypto.randomUUID()}`


// ============================================================
// QUERY EXAMPLES
// ============================================================

const examples = [
  'Where is loginUser defined?',
  'Find all usages of getRecords',
  'How does authentication work in this project?',
]


// ============================================================
// ANSWER RENDERER
// ============================================================

function renderAnswer(answer) {
  if (!answer) {
    return null
  }

  const parts = answer.split(/(```[\s\S]*?```)/g)

  return parts.map((part, index) => {
    // --------------------------------------------------------
    // Code block
    // --------------------------------------------------------

    if (
      part.startsWith('```') &&
      part.endsWith('```')
    ) {
      const codeBlock = part
        .replace(/^```[a-zA-Z0-9+#._-]*\s*/, '')
        .replace(/```$/, '')
        .trimEnd()

      return (
        <pre
          className="answer-code"
          key={`code-${index}`}
        >
          <code>{codeBlock}</code>
        </pre>
      )
    }

    const text = part.trim()

    if (!text) {
      return null
    }

    // --------------------------------------------------------
    // Normal answer content
    // --------------------------------------------------------

    const lines = text.split('\n')

    return (
      <div
        className="answer-text-block"
        key={`text-${index}`}
      >
        {lines.map((line, lineIndex) => {
          const trimmedLine = line.trim()

          // Empty line
          if (!trimmedLine) {
            return (
              <div
                className="answer-spacer"
                key={`space-${lineIndex}`}
              />
            )
          }

          // --------------------------------------------------
          // Markdown headings
          // --------------------------------------------------

          if (trimmedLine.startsWith('### ')) {
            return (
              <h4 key={`heading-${lineIndex}`}>
                {trimmedLine.slice(4)}
              </h4>
            )
          }

          if (trimmedLine.startsWith('## ')) {
            return (
              <h3 key={`heading-${lineIndex}`}>
                {trimmedLine.slice(3)}
              </h3>
            )
          }

          if (trimmedLine.startsWith('# ')) {
            return (
              <h2 key={`heading-${lineIndex}`}>
                {trimmedLine.slice(2)}
              </h2>
            )
          }

          // --------------------------------------------------
          // Bullet points
          // --------------------------------------------------

          if (
            trimmedLine.startsWith('- ') ||
            trimmedLine.startsWith('* ')
          ) {
            return (
              <div
                className="answer-list-item"
                key={`bullet-${lineIndex}`}
              >
                <span className="answer-bullet">
                  •
                </span>

                <span>
                  {trimmedLine.slice(2)}
                </span>
              </div>
            )
          }

          // --------------------------------------------------
          // Numbered list
          // --------------------------------------------------

          const numberedMatch =
            trimmedLine.match(/^(\d+)\.\s+(.*)$/)

          if (numberedMatch) {
            return (
              <div
                className="answer-list-item"
                key={`number-${lineIndex}`}
              >
                <span className="answer-number">
                  {numberedMatch[1]}.
                </span>

                <span>
                  {numberedMatch[2]}
                </span>
              </div>
            )
          }

          // --------------------------------------------------
          // Normal paragraph
          // --------------------------------------------------

          return (
            <p key={`paragraph-${lineIndex}`}>
              {trimmedLine}
            </p>
          )
        })}
      </div>
    )
  })
}


// ============================================================
// APP
// ============================================================

export default function App() {

  // ==========================================================
  // GLOBAL UI STATE
  // ==========================================================

  const [error, setError] = useState('')
  const [backendState, setBackendState] = useState('loading')
  const [readyState, setReadyState] = useState('loading')
  
const [selectedSource, setSelectedSource] = useState(null)
const [sourceCode, setSourceCode] = useState('')
const [sourceViewerState, setSourceViewerState] = useState('idle')
const [sourceViewerError, setSourceViewerError] = useState('')
const [sourceCodeStartLine, setSourceCodeStartLine] = useState(1)
const [sourceCodeTotalLines, setSourceCodeTotalLines] = useState(0)



  // ==========================================================
  // REPOSITORY HOOK
  // ==========================================================

  const {
    repositories,
    activeRepositoryId,
    ingestState,

    currentRepository,
    repositoryName,
    canQuery,
    currentLabel,

    showRepoSelector,
    setShowRepoSelector,

    repoSelectionError,

    historyLoading,

    handleRepositorySelect,
    handleIndexRepository,
    handleClearActiveRepo,
  } = useRepositories({
    setError,
    setResult: () => {},
    setQuery: () => {},
    setQueryState: () => {},
  })


  // ==========================================================
  // QUERY HOOK
  // ==========================================================

  const {
    query,
    setQuery,

    mode,
    setMode,

    result,

    queryState,

    handleQuery,
    handleClearConversation,
  } = useQuery({
    activeRepositoryId,
    currentRepository,
    sessionId: SESSION_ID,
    setError,
  })

  // ==========================================================
  // SOURCE CODE VIEWER
  // ==========================================================

  const handleSourceClick = async (source) => {
    if (!activeRepositoryId) {
      setSelectedSource(source)
      setSourceViewerError('Select a repository first.')
      setSourceViewerState('error')
      return
    }

    setSelectedSource(source)
    setSourceCode('')
    setSourceViewerError('')
    setSourceViewerState('loading')

    const evidenceStart = Math.max(
      1,
      Number(source.start_line) || 1
    )

    const evidenceEnd = Math.max(
      evidenceStart,
      Number(source.end_line) || evidenceStart
    )

    // Expand the evidence range to include surrounding context.
    // The backend limits each response to at most 80 lines.
    const contextStart = Math.max(1, evidenceStart - 10)
    const contextEnd = Math.min(
      Math.max(evidenceEnd + 10, contextStart),
      contextStart + 79
    )

    try {
      const response = await api.repositorySource(
        activeRepositoryId,
        source.file,
        contextStart,
        contextEnd
      )

      setSourceCode(response.content)
      setSourceCodeStartLine(response.start_line)
      setSourceCodeTotalLines(response.total_lines)
      setSourceViewerState('success')
    } catch (err) {
      setSourceViewerError(
        err.message || 'Unable to load this source file.'
      )
      setSourceViewerState('error')
    }
  }

  const closeSourceViewer = () => {
    setSelectedSource(null)
    setSourceCode('')
    setSourceViewerError('')
    setSourceViewerState('idle')
  }


  // ==========================================================
  // INITIALIZE BACKEND STATUS
  // ==========================================================

  useEffect(() => {
    let active = true

    async function initializeRuntime() {
      const [health, readiness] =
        await Promise.allSettled([
          api.health(),
          api.readiness(),
        ])

      if (!active) {
        return
      }

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
    }

    initializeRuntime()

    return () => {
      active = false
    }
  }, [])


  // ==========================================================
  // RENDER
  // ==========================================================

  return (
    <div className="app-shell font-display">

      {/* ====================================================
          TOPBAR
      ==================================================== */}

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


      {/* ====================================================
          MAIN WORKSPACE
      ==================================================== */}

      <main className="workspace">

        {/* ==================================================
            INTRO
        ================================================== */}

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
              Explore your indexed repositories, search exact
              identifiers, and ask grounded architectural
              questions without leaving your workspace.
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


        {/* ==================================================
            ERROR
        ================================================== */}

        <ErrorBanner
          message={error}
          onDismiss={() => setError('')}
        />


        {/* ==================================================
            CONTROL GRID
        ================================================== */}

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
              Codebase Navigator currently supports the
              configured local repositories below.
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
                  repo.id === activeRepositoryId

                return (
                  <button
                    key={repo.id}
                    type="button"
                    className={`repository-choice ${
                      isActive ? 'active' : ''
                    }`}
                    onClick={() =>
                      handleRepositorySelect(
                        repo,
                        SESSION_ID
                      )
                    }
                    disabled={!repo.indexed}
                  >

                    <div className="repository-choice-icon">
                      <Database size={18} />
                    </div>


                    <div className="repository-choice-content">

                      <strong className="repository-choice-name">
                        {repo.name}
                      </strong>


                      <div
                        className={`repository-choice-status ${
                          repo.indexed
                            ? ''
                            : 'not-indexed'
                        }`}
                      >

                        <span
                          className={`repo-status-dot ${
                            repo.indexed
                              ? ''
                              : 'not-indexed'
                          }`}
                        />

                        <span>
                          {repo.indexed
                            ? 'Indexed and ready'
                            : 'Not indexed'}
                        </span>

                      </div>


                      <div className="repository-choice-path">

                        <Folder size={12} />

                        <span>
                          {repo.repository_path}
                        </span>

                      </div>

                    </div>


                    {isActive && repo.indexed ? (

                      <div className="repository-choice-check">
                        <Check size={15} />
                      </div>

                    ) : (

                      <ChevronRight
                        className="repository-choice-arrow"
                        size={17}
                      />

                    )}

                  </button>
                )
              })}

            </div>


            {/* ==================================================
                INDEX BUTTON
            ================================================== */}

            <div className="input-row repository-action-row">

              <button
                type="button"
                className="primary-button"
                disabled={
                  !activeRepositoryId ||
                  ingestState === 'loading'
                }
                onClick={handleIndexRepository}
              >

                {ingestState === 'loading' ? (

                  <LoaderCircle
                    className="spin"
                    size={17}
                  />

                ) : (

                  <ArrowUpRight size={17} />

                )}


                {ingestState === 'loading'
                  ? 'Indexing'
                  : 'Re-index repository'}

              </button>

            </div>


            {/* ==================================================
                PANEL FOOTER
            ================================================== */}

            <div className="panel-foot">

              <StatusPill
                state={
                  ingestState === 'ok'
                    ? 'ok'
                    : ingestState === 'loading'
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
                <IconButton
                  onClick={handleClearActiveRepo}
                  label="Disconnect repository"
                >
                  <X size={16} />
                </IconButton>
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
                    : readyState === 'loading'
                      ? 'Checking runtime configuration'
                      : 'Readiness unavailable'}

                </span>

              </div>

            </div>


            <div className="mini-stats">

              <div>

                <span>
                  REPOSITORY ID
                </span>

                <strong>
                  {activeRepositoryId
                    ? activeRepositoryId.toUpperCase()
                    : '—'}
                </strong>

              </div>


              <div>

                <span>
                  MODE
                </span>

                <strong>
                  {mode === 'exact'
                    ? 'IDENTIFIER'
                    : 'SEMANTIC'}
                </strong>

              </div>

            </div>


            <div className="mini-stats">

              <div>

                <span>
                  SESSION
                </span>

                <strong>
                  {SESSION_ID
                    .slice(-6)
                    .toUpperCase()}
                </strong>

              </div>


              <div>

                <span>
                  INDEXED
                </span>

                <strong>
                  {
                    repositories.filter(
                      (repo) => repo.indexed
                    ).length
                  }
                  /
                  {repositories.length}
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

              <MessageSquareText size={15} />

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

                {examples.map((example) => (

                  <button
                    type="button"
                    key={example}
                    onClick={() =>
                      setQuery(example)
                    }
                    disabled={!canQuery}
                  >
                    {example}
                  </button>

                ))}

              </div>


              <button
                className="query-button"
                disabled={
                  !canQuery ||
                  queryState === 'loading'
                }
                type="submit"
              >

                {queryState === 'loading' ? (

                  <LoaderCircle
                    className="spin"
                    size={17}
                  />

                ) : (

                  <ChevronRight size={17} />

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
                onClick={handleClearConversation}
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

                {result.sources?.length || 0}
                {' '}
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
                Your answer will appear here with
                file-level source references.
              </span>

            </div>

          )}


          {/* ==================================================
              RESULTS
          ================================================== */}

          {result && (

            <div className="results-layout">

              {/* ==================================================
                  ANSWER
              ================================================== */}

              <article className="answer-panel">

                <div className="answer-label">

                  <Sparkles size={15} />

                  GROUNDED RESPONSE

                </div>


                <div className="answer-content">

                  {renderAnswer(result.answer)}

                </div>


                <div className="answer-query">

                  QUERY / {result.query}

                </div>

              </article>


              {/* ==================================================
                  SOURCES
              ================================================== */}

              
<div className="sources-list">
  {result.sources?.length ? (
    result.sources.map((source, index) => (
      <SourceCard
        source={source}
        index={index}
        key={`${source.file}-${index}`}
        onClick={handleSourceClick}
      />
    ))
  ) : (
    <div className="empty-sources">
      No source references returned
      for this query.
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

          CODEBASE NAVIGATOR / LOCAL-FIRST INTELLIGENCE

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


              <IconButton
                onClick={() =>
                  setShowRepoSelector(false)
                }
                label="Close"
              >
                <X size={18} />
              </IconButton>

            </div>


            {/* ==================================================
                MODAL ERROR
            ================================================== */}

            {repoSelectionError && (

              <div className="modal-error">

                {repoSelectionError}

              </div>

            )}


            {/* ==================================================
                REPOSITORY LIST
            ================================================== */}

            <ul className="repo-list">

              {repositories.map((repo) => {

                const isActive =
                  repo.id === activeRepositoryId

                return (

                  <li
                    key={repo.id}
                    className={
                      isActive
                        ? 'active'
                        : ''
                    }
                    onClick={() => {

                      if (repo.indexed) {

                        handleRepositorySelect(
                          repo,
                          SESSION_ID
                        )

                      }

                    }}
                    aria-disabled={!repo.indexed}
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
                        <Check size={16} />
                      )}

                  </li>

                )

              })}

            </ul>


            {/* ==================================================
                CLOSE
            ================================================== */}

            <button
              className="modal-close-btn"
              onClick={() =>
                setShowRepoSelector(false)
              }
              type="button"
            >
              Cancel
            </button>

          </div>

        </div>

      )}

      {/* ======================================================
          SOURCE CODE VIEWER
      ====================================================== */}

      {selectedSource && (
        <div
          className="modal-overlay source-viewer-overlay"
          onClick={closeSourceViewer}
          role="dialog"
          aria-modal="true"
          aria-labelledby="source-viewer-title"
        >
          <div
            className="modal-content source-viewer-modal"
            onClick={(event) => event.stopPropagation()}
            style={{
              width: 'min(1100px, 94vw)',
              maxWidth: '1100px',
              maxHeight: '85vh',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div className="modal-header">
              <div>
                <span className="section-kicker">
                  SOURCE INSPECTOR
                </span>

                <h3 id="source-viewer-title">
                  {selectedSource.file}
                </h3>

                <p style={{ marginTop: '6px', fontSize: '12px' }}>
                  {selectedSource.language || 'Source file'}
                  {' · '}
                  {sourceViewerState === 'success'
                    ? `Lines ${sourceCodeStartLine}–${
                        sourceCodeStartLine +
                        Math.max(0, sourceCode.split('\n').length - 1)
                      } of ${sourceCodeTotalLines}`
                    : 'Repository source'}
                </p>
              </div>

              <IconButton
                onClick={closeSourceViewer}
                label="Close source viewer"
              >
                <X size={18} />
              </IconButton>
            </div>

            <div
              style={{
                overflow: 'auto',
                minHeight: '200px',
                background: '#10151d',
                borderRadius: '8px',
                marginTop: '16px',
              }}
            >
              {sourceViewerState === 'loading' && (
                <div style={{ padding: '24px' }}>
                  <LoaderCircle className="spin" size={20} />
                  <p>Loading source code...</p>
                </div>
              )}

              {sourceViewerState === 'error' && (
                <div
                  role="alert"
                  style={{
                    padding: '24px',
                    color: '#ff9b9b',
                  }}
                >
                  {sourceViewerError}
                </div>
              )}

              {sourceViewerState === 'success' && (
                <pre
                  style={{
                    margin: 0,
                    padding: '16px',
                    color: '#e5e7eb',
                    fontSize: '13px',
                    lineHeight: 1.7,
                    overflow: 'visible',
                    whiteSpace: 'pre',
                    fontFamily: 'monospace',
                  }}
                >
                  {sourceCode.split('\n').map((line, index) => {
                    const lineNumber = sourceCodeStartLine + index
                    const evidenceStart = Math.max(
                      1,
                      Number(selectedSource.start_line) || 1
                    )
                    const evidenceEnd = Math.max(
                      evidenceStart,
                      Number(selectedSource.end_line) || evidenceStart
                    )
                    const isEvidenceLine =
                      lineNumber >= evidenceStart &&
                      lineNumber <= evidenceEnd

                    return (
                      <div
                        key={lineNumber}
                        style={{
                          display: 'flex',
                          minHeight: '22px',
                          background: isEvidenceLine
                            ? 'rgba(234, 179, 8, 0.12)'
                            : 'transparent',
                          borderLeft: isEvidenceLine
                            ? '3px solid #eab308'
                            : '3px solid transparent',
                        }}
                      >
                        <span
                          style={{
                            display: 'inline-block',
                            width: '56px',
                            flexShrink: 0,
                            paddingRight: '16px',
                            textAlign: 'right',
                            color: isEvidenceLine ? '#facc15' : '#778399',
                            userSelect: 'none',
                          }}
                        >
                          {lineNumber}
                        </span>

                        <code
                          style={{
                            whiteSpace: 'pre',
                            fontFamily: 'inherit',
                          }}
                        >
                          {line || ' '}
                        </code>
                      </div>
                    )
                  })}
                </pre>
              )}
            </div>

            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: '16px',
              }}
            >
              <button
                type="button"
                className="secondary-button"
                onClick={closeSourceViewer}
              >
                Close viewer
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
