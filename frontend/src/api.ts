import type { HistoryRecord, HistorySummary, RepoIntro, RepoSummary } from './types'

async function errorText(res: Response): Promise<string> {
  try {
    const data = await res.json()
    return typeof data.detail === 'string' ? data.detail : JSON.stringify(data)
  } catch {
    return res.statusText
  }
}

export async function getRepo(): Promise<RepoSummary | null> {
  const res = await fetch('/api/repo')
  if (res.status === 409) return null
  if (!res.ok) throw new Error(await errorText(res))
  return res.json()
}

export async function loadRepo(source: string): Promise<RepoSummary> {
  const res = await fetch('/api/repo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source }),
  })
  if (!res.ok) throw new Error(await errorText(res))
  return res.json()
}

export async function cancelRun(runId: string): Promise<void> {
  const res = await fetch(`/api/ask/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
  if (!res.ok && res.status !== 404) throw new Error(await errorText(res)) // 404: already finished
}

export type AgentEvent = { type: string; data: Record<string, unknown> }

/** POST a question and call onEvent for each Server-Sent Event.
 *  (EventSource only supports GET, so the stream is parsed here.) */
export async function streamAsk(
  question: string,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!res.ok || !res.body) throw new Error(await errorText(res))
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let end
    while ((end = buffer.indexOf('\n\n')) >= 0) {
      const chunk = buffer.slice(0, end)
      buffer = buffer.slice(end + 2)
      let type = 'message'
      let data = ''
      for (const line of chunk.split('\n')) {
        if (line.startsWith('event: ')) type = line.slice(7)
        else if (line.startsWith('data: ')) data += line.slice(6)
      }
      if (data) onEvent({ type, data: JSON.parse(data) })
    }
  }
}

export async function listHistory(): Promise<HistorySummary[]> {
  const res = await fetch('/api/history')
  if (!res.ok) throw new Error(await errorText(res))
  return res.json()
}

export async function getConversation(id: number): Promise<HistoryRecord> {
  const res = await fetch(`/api/history/${id}`)
  if (!res.ok) throw new Error(await errorText(res))
  return res.json()
}

export async function deleteConversation(id: number): Promise<void> {
  const res = await fetch(`/api/history/${id}`, { method: 'DELETE' })
  if (!res.ok && res.status !== 404) throw new Error(await errorText(res))
}

export async function getRepoIntro(): Promise<RepoIntro> {
  const res = await fetch('/api/repo/intro')
  if (!res.ok) throw new Error(await errorText(res))
  return res.json()
}
