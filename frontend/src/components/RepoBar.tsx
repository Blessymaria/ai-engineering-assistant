import { useState } from 'react'
import type { RepoSummary } from '../types'

interface Props {
  repo: RepoSummary | null
  loading: boolean
  error: string | null
  onLoad: (source: string) => void
}

export default function RepoBar({ repo, loading, error, onLoad }: Props) {
  const [source, setSource] = useState('')
  const kinds = repo?.kinds ?? {}
  return (
    <header className="repo-bar">
      <strong className="brand">AI Engineering Assistant</strong>
      <form
        className="repo-form"
        onSubmit={(e) => {
          e.preventDefault()
          if (source.trim()) onLoad(source.trim())
        }}
      >
        <label htmlFor="repo-source">Repository:</label>
        <input
          id="repo-source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="To analyse another repository, paste its Git URL or local path (questions go in the box at the bottom)"
          disabled={loading}
        />
        <button type="submit" className="secondary" disabled={loading || !source.trim()}>
          {loading ? 'Indexing...' : 'Load'}
        </button>
      </form>
      <div className="repo-status">
        {repo && (
          <span title={repo.root}>
            Loaded: <b>{repo.name}</b>
            {repo.commit && <> @ {repo.commit.slice(0, 7)}</>} · {repo.nodes} nodes · {kinds.function ?? 0} functions ·{' '}
            {kinds.route ?? 0} routes · {repo.files} files
          </span>
        )}
        {!repo && !loading && !error && <span className="muted">No repository loaded</span>}
        {error && <div className="bad">Could not load: {error}</div>}
      </div>
    </header>
  )
}
