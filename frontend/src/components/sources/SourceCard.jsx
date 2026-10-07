import { ArrowUpRight, FileCode2 } from 'lucide-react'

export default function SourceCard({ source, index }) {
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

          {source.language && <span>{source.language}</span>}

          {source.start_line && (
            <span>
              Ln {source.start_line}
              {source.end_line ? `-${source.end_line}` : ''}
            </span>
          )}

          {source.score !== undefined && source.score !== null && (
            <span>
              Score {typeof source.score === 'number' ? source.score.toFixed(2) : source.score}
            </span>
          )}
        </div>

        <div className="source-rule" />

        <p>
          Referenced by the backend response for this query.
        </p>
      </div>

      <ArrowUpRight className="source-arrow" size={17} />
    </article>
  )
}
