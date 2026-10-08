import { useState } from 'react'
import type { RepoSummary } from '../types'

interface Props {
  repo: RepoSummary | null
  loading: boolean
  error: string | null
  onLoad: (source: string) => void
  historyCount: number
  onHistory: () => void
}

export default function RepoBar({ repo, loading, error, onLoad, historyCount, onHistory }: Props) {
  const [source, setSource] = useState('')
  const [changing, setChanging] = useState(false)
  const kinds = repo?.kinds ?? {}
  const showForm = changing || (!repo && !loading)

  return (
    <header className="repo-bar">
      <div className="brand-block">
        <svg className="logo" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="var(--accent)" />
          <circle cx="10" cy="11" r="3" fill="#fff" />
          <circle cx="22" cy="11" r="3" fill="#fff" opacity="0.75" />
          <circle cx="16" cy="22" r="3" fill="#fff" />
          <path d="M10 11 16 22 22 11" stroke="#fff" strokeWidth="1.6" fill="none" opacity="0.8" />
        </svg>
        <div>
          <div className="brand">AI Engineering Assistant</div>
          <div className="tagline">Ask questions about a Python codebase it has never seen</div>
        </div>
      </div>

      <div className="repo-side">
        {repo && !changing && (
          <div className="repo-card" title={repo.root}>
            <span className="repo-label">Repository</span>
            <span className="repo-name">{repo.name}</span>
            <span className="badges">
              {repo.commit && <span className="badge mono">{repo.commit.slice(0, 7)}</span>}
              <span className="badge">{kinds.function ?? 0} functions</span>
              <span className="badge">{kinds.route ?? 0} routes</span>
              <span className="badge">{repo.files} files</span>
            </span>
            <button type="button" className="link-button" onClick={() => setChanging(true)} disabled={loading}>
              Change
            </button>
            <button type="button" className="link-button" onClick={onHistory}>
              History ({historyCount})
            </button>
          </div>
        )}

        {showForm && (
          <form
            className="repo-form"
            onSubmit={(e) => {
              e.preventDefault()
              if (!source.trim()) return
              onLoad(source.trim())
              setChanging(false)
            }}
          >
            <input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="Git URL or local folder of a Python repository"
              disabled={loading}
              autoFocus={changing}
            />
            <button type="submit" disabled={loading || !source.trim()}>
              {loading ? 'Indexing...' : 'Load'}
            </button>
            {repo && (
              <button type="button" className="secondary" onClick={() => setChanging(false)} disabled={loading}>
                Cancel
              </button>
            )}
          </form>
        )}

        {loading && !showForm && <span className="muted">Indexing repository...</span>}
        {error && <div className="bad small">Could not load: {error}</div>}
      </div>
    </header>
  )
}
