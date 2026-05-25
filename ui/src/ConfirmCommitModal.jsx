import { useEffect, useState } from 'react'

const CONFIRM_WORD = 'YES'

export default function ConfirmCommitModal({ pending, onCancel }) {
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (pending) {
      setTyped('')
      setBusy(false)
      setError('')
    }
  }, [pending])

  useEffect(() => {
    if (!pending) return
    const onKeyDown = (e) => {
      if (e.key === 'Escape' && !busy) {
        e.preventDefault()
        onCancel()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [pending, busy, onCancel])

  if (!pending) return null

  const canConfirm = typed === CONFIRM_WORD && !busy

  const handleConfirm = async () => {
    if (!canConfirm) return
    setBusy(true)
    setError('')
    try {
      await pending.onConfirm()
      onCancel()
    } catch (e) {
      setError(e.message || 'Request failed')
      setBusy(false)
    }
  }

  return (
    <div
      className="modal-backdrop confirm-backdrop"
      onClick={busy ? undefined : onCancel}
    >
      <div
        className="modal confirm-modal"
        onClick={(e) => e.stopPropagation()}
        role="alertdialog"
        aria-labelledby="confirm-commit-title"
        aria-describedby="confirm-commit-desc"
      >
        <h2 id="confirm-commit-title">{pending.title}</h2>
        <p id="confirm-commit-desc" className="confirm-intro">
          Review what will be written to the database. Type <strong>{CONFIRM_WORD}</strong> to
          proceed.
        </p>
        <dl className="confirm-summary">
          {pending.lines.map((line) => (
            <div key={line.label} className="confirm-row">
              <dt>{line.label}</dt>
              <dd>{line.value}</dd>
            </div>
          ))}
        </dl>
        <label className="confirm-type">
          Type {CONFIRM_WORD} to confirm
          <input
            type="text"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={CONFIRM_WORD}
            autoComplete="off"
            autoFocus
            disabled={busy}
          />
        </label>
        {error && <div className="banner-error confirm-error">{error}</div>}
        <div className="modal-actions">
          <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary btn-danger"
            disabled={!canConfirm}
            onClick={handleConfirm}
          >
            {busy ? 'Committing…' : pending.actionLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
