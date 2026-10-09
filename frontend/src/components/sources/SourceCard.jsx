
import { ArrowUpRight, FileCode2 } from 'lucide-react'

export default function SourceCard({ source, index, onClick }) {
  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onClick?.(source)
    }
  }

  return (
    <article
      className="source-card"
      role="button"
      tabIndex={0}
      aria-label={`Open source file ${source.file}`}
      onClick={() => onClick?.(source)}
      onKeyDown={handleKeyDown}
      style={{ cursor: 'pointer' }}
    >
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
              {source.end_line ? `-${source.end_line}` : ''}
            </span>
          )}

          {source.score !== undefined &&
            source.score !== null && (
              <span>
                Score{' '}
                {typeof source.score === 'number'
                  ? source.score.toFixed(2)
                  : source.score}
              </span>
            )}
        </div>

        <div className="source-rule" />

        <p>
          Click to view the referenced source code.
        </p>
      </div>

      <ArrowUpRight
        className="source-arrow"
        size={17}
      />
    </article>
  )
}
