import { useEffect, useRef, useState } from 'react'
import type { Turn } from '../types'
import Markdown from './Markdown'
import Mermaid from './Mermaid'

interface Props {
  turns: Turn[]
  selected: number | null
  canAsk: boolean
  onAsk: (question: string) => void
  onSelect: (turnId: number) => void
  onCitation: (turn: Turn, evidenceId: string) => void
}

export default function Chat({ turns, selected, canAsk, onAsk, onSelect, onCitation }: Props) {
  const [question, setQuestion] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const busy = turns.some((t) => t.running)

  useEffect(() => endRef.current?.scrollIntoView({ behavior: 'smooth' }), [turns])

  return (
    <section className="chat">
      <div className="messages">
        {turns.length === 0 && (
          <div className="empty muted">
            Ask about the loaded repository, for example: <i>What happens when POST /articles is called?</i>
            <br />
            Answers take a few minutes on a laptop CPU; the activity panel shows progress.
          </div>
        )}
        {turns.map((turn) => (
          <div
            key={turn.id}
            className={`turn${turn.id === selected ? ' selected' : ''}`}
            onClick={() => onSelect(turn.id)}
          >
            <div className="question">{turn.question}</div>
            <div className="answer">
              {turn.answer && <Markdown text={turn.answer} onCitation={(id) => onCitation(turn, id)} />}
              {turn.diagram && (
                <details open className="diagram">
                  <summary>Calls followed (solid = confirmed, dashed = ambiguous or unresolved)</summary>
                  <Mermaid code={turn.diagram} />
                </details>
              )}
              {turn.error && <div className="bad">Error: {turn.error}</div>}
              {turn.running && !turn.answer && <div className="muted">Working... see the activity panel.</div>}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form
        className="ask"
        onSubmit={(e) => {
          e.preventDefault()
          if (!question.trim() || busy || !canAsk) return
          onAsk(question.trim())
          setQuestion('')
        }}
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={canAsk ? 'Ask a question about the repository...' : 'Load a repository first'}
          disabled={busy || !canAsk}
        />
        <button type="submit" disabled={busy || !canAsk || !question.trim()}>
          {busy ? 'Working...' : 'Ask'}
        </button>
      </form>
    </section>
  )
}
