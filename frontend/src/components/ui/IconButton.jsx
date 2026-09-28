export default function IconButton({
  children,
  onClick,
  label,
  disabled = false,
  className = '',
  type = 'button',
}) {
  return (
    <button
      type={type}
      className={`icon-button ${className}`.trim()}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
    >
      {children}
    </button>
  )
}