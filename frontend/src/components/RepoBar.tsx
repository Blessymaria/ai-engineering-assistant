import { useState } from 'react'
import type { RecentRepo, RepoSummary } from '../types'

interface Props {
  repo: RepoSummary | null
  loading: boolean
  error: string | null
  onLoad: (source: string) => void
  historyCount: number
  onHistory: () => void
  recent: RecentRepo[] // sources that loaded before, newest first
}

export default function RepoBar({ repo, loading, error, onLoad, historyCount, onHistory, recent }: Props) {
  const [source, setSource] = useState('')
  const [changing, setChanging] = useState(false)
  const [open, setOpen] = useState(false) // the recent-repositories list under the input
  const [active, setActive] = useState(-1) // highlighted entry, for the arrow keys
  const kinds = repo?.kinds ?? {}
  const showForm = changing || (!repo && !loading)
  const filter = source.trim().toLowerCase()
  const matches = recent.filter((r) => !filter || r.source.toLowerCase().includes(filter)
                                       || r.name.toLowerCase().includes(filter))
  const showList = open && !loading && matches.length > 0

  const load = (value: string) => {
    if (!value.trim()) return
    onLoad(value.trim())
    setSource('')
    setOpen(false)
    setChanging(false)
  }

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
            <button type="button" className="link-button" onClick={() => {
              setChanging(true)
              setOpen(true)
            }} disabled={loading}>
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
              load(showList && active >= 0 ? matches[active].source : source)
            }}
          >
            <div className="combo">
              <input
                value={source}
                onChange={(e) => {
                  setSource(e.target.value)
                  setOpen(true)
                  setActive(-1)
                }}
                onFocus={() => setOpen(true)}
                onBlur={() => setOpen(false)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') setOpen(false)
                  else if (e.key === 'ArrowDown' && matches.length) {
                    e.preventDefault()
                    setOpen(true)
                    setActive((i) => (i + 1) % matches.length)
                  } else if (e.key === 'ArrowUp' && matches.length) {
                    e.preventDefault()
                    setActive((i) => (i <= 0 ? matches.length - 1 : i - 1))
                  }
                }}
                placeholder="Git URL or local folder of a Python repository"
                disabled={loading}
                autoFocus={changing}
                role="combobox"
                aria-expanded={showList}
                aria-controls="recent-repos"
                aria-autocomplete="list"
              />
              {showList && (
                <ul className="recent" id="recent-repos" role="listbox">
                  <li className="recent-label" aria-hidden="true">Recent repositories</li>
                  {matches.map((r, i) => (
                    <li
                      key={r.source}
                      role="option"
                      aria-selected={i === active}
                      className={`recent-item${i === active ? ' active' : ''}`}
                      onMouseDown={(e) => e.preventDefault()} // keep focus so the click lands
                      onMouseEnter={() => setActive(i)}
                      onClick={() => load(r.source)}
                    >
                      <span className="recent-name">
                        {r.name}
                        {repo && i === 0 && recent[0] === r && r.name === repo.name && (
                          <span className="recent-current">loaded</span>
                        )}
                      </span>
                      <span className="recent-source">{r.source}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
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
