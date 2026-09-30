import { useCallback, useEffect, useState } from 'react'
import { getRepo, loadRepo, streamAsk } from './api'
import Activity from './components/Activity'
import Chat from './components/Chat'
import Detail from './components/Detail'
import RepoBar from './components/RepoBar'
import { applyEvent } from './events'
import type { DetailView, Evidence, RepoSummary, Step, Turn } from './types'

let nextTurnId = 1

function evidenceView(ev: Evidence): DetailView {
  const result = ev.result as { content?: string }
  if (ev.tool === 'read_file' && typeof result?.content === 'string') {
    return { title: `${ev.id} · ${ev.summary}`, body: result.content, language: 'python' }
  }
  return { title: `${ev.id} · ${ev.summary}`, body: JSON.stringify(ev.result, null, 2), language: 'json' }
}

export default function App() {
  const [repo, setRepo] = useState<RepoSummary | null>(null)
  const [repoLoading, setRepoLoading] = useState(false)
  const [repoError, setRepoError] = useState<string | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [detail, setDetail] = useState<DetailView | null>(null)

  useEffect(() => {
    getRepo()
      .then(setRepo)
      .catch((err: Error) => setRepoError(`Backend not reachable: ${err.message}`))
  }, [])

  const onLoad = async (source: string) => {
    setRepoLoading(true)
    setRepoError(null)
    try {
      setRepo(await loadRepo(source))
      setTurns([])
      setSelected(null)
    } catch (err) {
      setRepoError((err as Error).message)
    } finally {
      setRepoLoading(false)
    }
  }

  const onAsk = async (question: string) => {
    const id = nextTurnId++
    setTurns((prev) => [...prev, { id, question, running: true, steps: [], evidence: {} }])
    setSelected(id)
    const update = (fn: (t: Turn) => Turn) => setTurns((prev) => prev.map((t) => (t.id === id ? fn(t) : t)))
    try {
      await streamAsk(question, (event) => update((t) => applyEvent(t, event)))
    } catch (err) {
      update((t) => applyEvent(t, { type: 'error', data: { message: (err as Error).message } }))
    }
    update((t) => (t.running ? { ...t, running: false } : t))
  }

  const openEvidence = useCallback((turn: Turn, evidenceId: string) => {
    const ev = turn.evidence[evidenceId]
    if (ev) setDetail(evidenceView(ev))
    else if (turn.running) setDetail({ title: evidenceId, body: 'Full evidence is available once the answer is finished.' })
    else setDetail({ title: evidenceId, body: `No evidence with id ${evidenceId} exists for this answer (citation not valid).` })
  }, [])

  const openStep = (turn: Turn, step: Step) => {
    if (step.code) {
      const test = step.test ? JSON.stringify(step.test, null, 2) : ''
      setDetail({ title: step.title, body: `${step.code}\n# --- test run ---\n${test}`, language: 'python' })
    } else if (step.evidenceId) {
      openEvidence(turn, step.evidenceId)
    } else {
      setDetail({ title: step.title, body: step.detail ?? '' })
    }
  }

  const current = turns.find((t) => t.id === selected) ?? null

  return (
    <div className="app">
      <RepoBar repo={repo} loading={repoLoading} error={repoError} onLoad={onLoad} />
      <main className="layout">
        <Chat
          turns={turns}
          selected={selected}
          canAsk={Boolean(repo) && !repoLoading}
          onAsk={onAsk}
          onSelect={setSelected}
          onCitation={openEvidence}
        />
        <Activity turn={current} onOpen={(step) => current && openStep(current, step)} />
      </main>
      {detail && <Detail view={detail} onClose={() => setDetail(null)} />}
    </div>
  )
}
