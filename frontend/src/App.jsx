import { useEffect, useMemo, useState } from 'react'
import {
  Activity,
  ArrowUpRight,
  Check,
  ChevronRight,
  CircleAlert,
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

const examples = [
  'Where is loginUser defined?',
  'Find all usages of getRecords',
  'How does authentication work in this project?',
]

function StatusPill({ state, label }) {
  const tone = state === 'ok' ? 'status-ok' : state === 'loading' ? 'status-loading' : 'status-idle'
  return <span className={`status-pill ${tone}`}><span className="status-dot" />{label}</span>
}

function ErrorBanner({ message, onDismiss }) {
  if (!message) return null
  return (
    <div className="error-banner" role="alert">
      <CircleAlert size={17} />
      <span>{message}</span>
      <button className="icon-button" onClick={onDismiss} aria-label="Dismiss error"><X size={16} /></button>
    </div>
  )
}

function SourceCard({ source, index }) {
  return (
    <article className="source-card">
      <div className="source-index">0{index + 1}</div>
      <div className="source-body">
        <div className="source-meta">
          <span className="source-file"><FileCode2 size={15} />{source.file}</span>
          <span>{source.language}</span>
          {source.start_line && <span>Ln {source.start_line}{source.end_line ? `-${source.end_line}` : ''}</span>}
        </div>
        <div className="source-rule" />
        <p>Referenced by the backend response for this query.</p>
      </div>
      <ArrowUpRight className="source-arrow" size={17} />
    </article>
  )
}

export default function App() {
  const [repoUrl, setRepoUrl] = useState('')
  const [repositoryPath, setRepositoryPath] = useState('')
  const [repositoryName, setRepositoryName] = useState('No repository connected')
  const [ingestState, setIngestState] = useState('idle')
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState('exact')
  const [result, setResult] = useState(null)
  const [queryState, setQueryState] = useState('idle')
  const [error, setError] = useState('')
  const [backendState, setBackendState] = useState('loading')
  const [readyState, setReadyState] = useState('loading')

  const canQuery = Boolean(repositoryPath)
  const currentLabel = useMemo(() => {
    if (ingestState === 'loading') return 'Indexing repository'
    if (repositoryPath) return 'Repository indexed'
    return 'Awaiting repository'
  }, [ingestState, repositoryPath])

  useEffect(() => {
    let active = true
    Promise.allSettled([api.health(), api.readiness()]).then(([health, readiness]) => {
      if (!active) return
      setBackendState(health.status === 'fulfilled' ? 'ok' : 'error')
      setReadyState(readiness.status === 'fulfilled' ? 'ok' : 'error')
    })
    return () => { active = false }
  }, [])

  async function handleIngest(event) {
    event.preventDefault()
    if (!repoUrl.trim()) {
      setError('Enter a public GitHub repository URL to begin.')
      return
    }
    setError('')
    setIngestState('loading')
    try {
      const payload = await api.loadRepository(repoUrl.trim())
      setRepositoryPath(payload.repository_path)
      setRepositoryName(payload.repository_path.split(/[\\/]/).pop() || 'Indexed repository')
      setIngestState('ok')
      setResult(null)
    } catch (requestError) {
      setIngestState('error')
      setError(requestError.message)
    }
  }

  async function handleQuery(event) {
    event.preventDefault()
    if (!repositoryPath) {
      setError('Index a repository before searching it.')
      return
    }
    if (!query.trim()) {
      setError('Enter a search or question first.')
      return
    }
    setError('')
    setQueryState('loading')
    try {
      const prompt = mode === 'exact' ? query.trim() : query.trim()
      const payload = await api.ask(prompt, repositoryPath, SESSION_ID)
      setResult(payload)
      setQueryState('ok')
    } catch (requestError) {
      setQueryState('error')
      setError(requestError.message)
    }
  }

  return (
    <div className="app-shell font-display">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark"><Terminal size={19} /></div>
          <div><strong>CODEBASE</strong><span>NAVIGATOR</span></div>
        </div>
        <div className="topbar-right">
          <StatusPill state={backendState} label={backendState === 'ok' ? 'API online' : 'API offline'} />
          <span className="build-label">LOCAL WORKSPACE / 0.1</span>
        </div>
      </header>

      <main className="workspace">
        <section className="intro-grid">
          <div className="intro-copy">
            <div className="eyebrow"><span className="eyebrow-line" />REPOSITORY INTELLIGENCE</div>
            <h1>Read the codebase<br /><em>between the lines.</em></h1>
            <p>Index a public GitHub repository, then move from exact identifiers to grounded architectural answers without leaving your workspace.</p>
          </div>
          <div className="signal-panel">
            <div className="signal-grid" />
            <Sparkles className="signal-icon" size={27} />
            <span>DETERMINISTIC SEARCH<br />+ GROUNDED RAG</span>
          </div>
        </section>

        <ErrorBanner message={error} onDismiss={() => setError('')} />

        <section className="control-grid">
          <div className="panel ingest-panel">
            <div className="panel-heading"><div><span className="section-kicker">01 / CONNECT</span><h2>Bring in a repository</h2></div><GitBranch size={20} /></div>
            <p className="panel-note">Public GitHub URLs are cloned and indexed locally. Private repository credentials stay outside the application.</p>
            <form onSubmit={handleIngest} className="input-row">
              <div className="field-wrap"><span>github.com /</span><input value={repoUrl} onChange={(event) => setRepoUrl(event.target.value)} placeholder="owner / repository" aria-label="GitHub repository URL" /></div>
              <button className="primary-button" disabled={ingestState === 'loading'}>{ingestState === 'loading' ? <LoaderCircle className="spin" size={17} /> : <ArrowUpRight size={17} />} {ingestState === 'loading' ? 'Indexing' : 'Index repository'}</button>
            </form>
            <div className="panel-foot"><StatusPill state={ingestState === 'ok' ? 'ok' : ingestState === 'loading' ? 'loading' : 'idle'} label={currentLabel} /><span className="foot-detail">{repositoryPath || 'No local collection yet'}</span></div>
          </div>

          <aside className="panel repo-panel">
            <div className="panel-heading"><div><span className="section-kicker">CURRENT CONTEXT</span><h2>{repositoryName}</h2></div><Database size={20} /></div>
            <div className="repo-status"><div className="repo-status-icon"><Check size={18} /></div><div><strong>{repositoryPath ? 'Ready to explore' : 'Connect a repository'}</strong><span>{readyState === 'ok' ? 'Runtime configuration ready' : 'Readiness unavailable'}</span></div></div>
            <div className="mini-stats"><div><span>MODE</span><strong>{mode === 'exact' ? 'IDENTIFIER' : 'SEMANTIC'}</strong></div><div><span>SESSION</span><strong>{SESSION_ID.slice(-6).toUpperCase()}</strong></div></div>
          </aside>
        </section>

        <section className="query-section">
          <div className="section-header"><div><span className="section-kicker">02 / EXPLORE</span><h2>Ask the repository</h2></div><span className="query-hint">{canQuery ? 'Collection active' : 'Index a repository to unlock search'}</span></div>
          <div className="mode-tabs" role="tablist" aria-label="Query mode"><button className={mode === 'exact' ? 'active' : ''} onClick={() => setMode('exact')}><Search size={15} /> Exact lookup</button><button className={mode === 'semantic' ? 'active' : ''} onClick={() => setMode('semantic')}><MessageSquareText size={15} /> Conceptual answer</button></div>
          <form onSubmit={handleQuery} className="query-form">
            <textarea value={query} onChange={(event) => setQuery(event.target.value)} disabled={!canQuery} placeholder={mode === 'exact' ? 'Where is loginUser defined? / Find all usages of getRecords' : 'How does authentication work in this project?'} aria-label="Repository query" />
            <div className="query-footer"><div className="examples">{examples.map((example) => <button type="button" key={example} onClick={() => setQuery(example)} disabled={!canQuery}>{example}</button>)}</div><button className="query-button" disabled={!canQuery || queryState === 'loading'}>{queryState === 'loading' ? <LoaderCircle className="spin" size={17} /> : <ChevronRight size={17} />} Run query</button></div>
          </form>
        </section>

        <section className="results-section">
          <div className="section-header"><div><span className="section-kicker">03 / OUTPUT</span><h2>Evidence and answer</h2></div>{result && <span className="result-count">{result.sources?.length || 0} source references</span>}</div>
          {!result && <div className="empty-state"><div className="empty-orbit"><Search size={22} /></div><strong>Nothing queried yet</strong><span>Your answer will appear here with file-level source references.</span></div>}
          {result && <div className="results-layout"><article className="answer-panel"><div className="answer-label"><Sparkles size={15} /> GROUNDED RESPONSE</div><p>{result.answer}</p><div className="answer-query">QUERY / {result.query}</div></article><div className="sources-list">{result.sources?.length ? result.sources.map((source, index) => <SourceCard source={source} index={index} key={`${source.file}-${index}`} />) : <div className="empty-sources">No source references returned for this query.</div>}</div></div>}
        </section>
      </main>
      <footer className="footer"><span><Activity size={14} /> CODEBASE NAVIGATOR / LOCAL-FIRST INTELLIGENCE</span><span>FASTAPI + QDRANT + GROQ</span></footer>
    </div>
  )
}
