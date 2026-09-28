import { CircleAlert, X } from 'lucide-react'

export default function ErrorBanner({ message, onDismiss }) {
  if (!message) return null

  return (
    <div className="error-banner" role="alert">
      <CircleAlert size={17} aria-hidden="true" />

      <span>{message}</span>

      {onDismiss && (
        <button
          type="button"
          className="icon-button"
          onClick={onDismiss}
          aria-label="Dismiss error"
        >
          <X size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  )
}