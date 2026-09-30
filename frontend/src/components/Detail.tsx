import { useEffect } from 'react'
import type { DetailView } from '../types'

export default function Detail({ view, onClose }: { view: DetailView; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="overlay" onClick={onClose}>
      <div className="detail" role="dialog" aria-label={view.title} onClick={(e) => e.stopPropagation()}>
        <div className="detail-head">
          <strong>{view.title}</strong>
          <button onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <pre className={`detail-body ${view.language ?? 'text'}`}>{view.body}</pre>
      </div>
    </div>
  )
}
