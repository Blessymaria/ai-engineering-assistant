import { useEffect } from 'react'
import type { HistorySummary } from '../types'

interface Props {
  repoName: string | null
  items: HistorySummary[]
  error: string | null
  onOpen: (id: number) => void
  onDelete: (id: number) => void
  onClose: () => void
}

function minutes(seconds: number): string {
  return seconds >= 60 ? `${Math.round(seconds / 60)} min` : `${Math.round(seconds)} s`
}

/** Saved conversations for the loaded repository, newest first. */
export default function HistoryPanel({ repoName, items, error, onOpen, onDelete, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="overlay" onClick={onClose}>
      <div className="detail history" role="dialog" aria-label="Saved answers" onClick={(e) => e.stopPropagation()}>
        <div className="detail-head">
          <strong>Saved answers{repoName ? ` for ${repoName}` : ''}</strong>
          <button onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="history-body">
          {error && <p className="bad">{error}</p>}
          {!error && items.length === 0 && (
            <p className="muted">No saved answers yet. Every answered question is saved here automatically.</p>
          )}
          <ul className="history-list">
            {items.map((item) => (
              <li key={item.id} className="history-item">
                <button type="button" className="history-open" onClick={() => onOpen(item.id)}>
                  <span className="history-question">{item.question}</span>
                  <span className="history-meta">
                    {item.created_at} · {item.rounds} tool rounds · {minutes(item.seconds)}
                    {item.stopped === 'limit' ? ' · stopped at the tool limit' : ''}
                  </span>
                </button>
                <button type="button" className="link-button danger" onClick={() => onDelete(item.id)}
                        aria-label={`Delete saved answer: ${item.question}`}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
