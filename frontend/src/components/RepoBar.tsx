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
        <input
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="Git URL or local path of a Python repository"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !source.trim()}>
          {loading ? 'Indexing...' : 'Load'}
        </button>
      </form>
      <div className="repo-status">
        {error && <span className="bad">{error}</span>}
        {!error && repo && (
          <span title={repo.root}>
            <b>{repo.name}</b>
            {repo.commit && <> @ {repo.commit.slice(0, 7)}</>} · {repo.nodes} nodes · {kinds.function ?? 0} functions ·{' '}
            {kinds.route ?? 0} routes · {repo.files} files
          </span>
        )}
        {!error && !repo && !loading && <span className="muted">No repository loaded</span>}
      </div>
    </header>
  )
}
