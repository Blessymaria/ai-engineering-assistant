import { useCallback, useEffect, useState } from 'react'
import { cancelRun, deleteConversation, getConversation, getRepo, listHistory, loadRepo, streamAsk } from './api'
import Activity from './components/Activity'
import Chat from './components/Chat'
import Detail from './components/Detail'
import HistoryPanel from './components/HistoryPanel'
import RepoBar from './components/RepoBar'
import { applyEvent } from './events'
import type { DetailView, Evidence, HistorySummary, RepoSummary, Step, Turn } from './types'

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
  const [history, setHistory] = useState<HistorySummary[]>([])
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)

  const refreshHistory = useCallback(() => {
    listHistory()
      .then((items) => {
        setHistory(items)
        setHistoryError(null)
      })
      .catch((err: Error) => setHistoryError(`Could not load history: ${err.message}`))
  }, [])

  useEffect(() => {
    getRepo()
      .then((loaded) => {
        setRepo(loaded)
        if (loaded) refreshHistory()
      })
      .catch((err: Error) => setRepoError(`Backend not reachable: ${err.message}`))
  }, [refreshHistory])

  const onLoad = async (source: string) => {
    setRepoLoading(true)
    setRepoError(null)
    try {
      setRepo(await loadRepo(source))
      setTurns([])
      setSelected(null)
      refreshHistory()
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
    refreshHistory()
  }

  // Rebuild a finished turn from its saved events, so it looks exactly as it did live
  const openSaved = async (historyId: number) => {
    setHistoryOpen(false)
    const open = turns.find((t) => t.historyId === historyId)
    if (open) {
      setSelected(open.id)
      return
    }
    try {
      const record = await getConversation(historyId)
      const start: Turn = { id: nextTurnId++, question: record.question, running: true, steps: [], evidence: {},
                            savedAt: record.created_at }
      const replayed = record.events.reduce(applyEvent, start)
      const turn = applyEvent(replayed, {
        type: 'done',
        data: { evidence: record.evidence, rounds: record.rounds, seconds: record.seconds, history_id: record.id },
      })
      setTurns((prev) => [...prev, turn])
      setSelected(turn.id)
    } catch (err) {
      setHistoryError((err as Error).message)
      setHistoryOpen(true)
    }
  }

  const deleteSaved = async (historyId: number) => {
    try {
      await deleteConversation(historyId)
      setTurns((prev) => prev.map((t) => (t.historyId === historyId ? { ...t, historyId: undefined } : t)))
      refreshHistory()
    } catch (err) {
      setHistoryError((err as Error).message)
    }
  }

  const onStop = async (turn: Turn) => {
    if (!turn.runId) return
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, stopping: true } : t)))
    try {
      await cancelRun(turn.runId)
    } catch (err) {
      setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, stopping: false, error: (err as Error).message } : t)))
    }
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

  const closeHistory = useCallback(() => setHistoryOpen(false), [])
  const current = turns.find((t) => t.id === selected) ?? null

  return (
    <div className="app">
      <RepoBar repo={repo} loading={repoLoading} error={repoError} onLoad={onLoad}
               historyCount={history.length} onHistory={() => { refreshHistory(); setHistoryOpen(true) }} />
      <main className="layout">
        <Chat
          repoName={repo?.name ?? null}
          suggestions={repo?.suggestions ?? []}
          turns={turns}
          selected={selected}
          canAsk={Boolean(repo) && !repoLoading}
          onAsk={onAsk}
          onSelect={setSelected}
          onCitation={openEvidence}
          onStop={onStop}
        />
        <Activity turn={current} onOpen={(step) => current && openStep(current, step)} />
      </main>
      {detail && <Detail view={detail} onClose={() => setDetail(null)} />}
      {historyOpen && (
        <HistoryPanel repoName={repo?.name ?? null} items={history} error={historyError}
                      onOpen={openSaved} onDelete={deleteSaved} onClose={closeHistory} />
      )}
    </div>
  )
}
