import { LoaderCircle } from 'lucide-react'

const stateConfig = {
  ok: {
    dot: 'status-dot status-dot-ok',
  },
  loading: {
    dot: 'status-dot status-dot-loading',
  },
  error: {
    dot: 'status-dot status-dot-error',
  },
  idle: {
    dot: 'status-dot status-dot-idle',
  },
}

export default function StatusPill({ state = 'idle', label }) {
  const config = stateConfig[state] || stateConfig.idle

  return (
    <span className={`status-pill status-${state}`}>
      {state === 'loading' ? (
        <LoaderCircle
          size={11}
          className="spin"
          aria-hidden="true"
        />
      ) : (
        <span className={config.dot} aria-hidden="true" />
      )}

      <span>{label}</span>
    </span>
  )
}