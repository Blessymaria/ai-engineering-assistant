import { useEffect, useRef, useState } from 'react'
import type { Turn } from '../types'
import Markdown from './Markdown'
import Mermaid from './Mermaid'

// Example questions for the demo repository (shown only when it is loaded); clicking one fills the question box
const DEMO_REPO = 'fastapi-realworld-example-app'
const EXAMPLES = [
  'What happens when POST /articles is called?',
  'Which modules depend on app.db.repositories.articles?',
  'How is the JWT token created, and where is it checked on incoming requests?',
  'When was the create_article function in app/db/repositories/articles.py last changed, and by whom?',
]

interface Props {
  repoName: string | null
  turns: Turn[]
  selected: number | null
  canAsk: boolean
  onAsk: (question: string) => void
  onSelect: (turnId: number) => void
  onCitation: (turn: Turn, evidenceId: string) => void
  onStop: (turn: Turn) => void
}

export default function Chat({ repoName, turns, selected, canAsk, onAsk, onSelect, onCitation, onStop }: Props) {
  const [question, setQuestion] = useState('')
  const endRef = useRef<HTMLDivElement>(null)
  const running = turns.find((t) => t.running)
  const busy = Boolean(running)

  useEffect(() => {
    // Braces matter: newer browsers return a Promise from scrollIntoView, and an effect must not return one
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  return (
    <section className="chat">
      <div className="messages">
        {turns.length === 0 && (
          <div className="empty">
            <h2>{repoName ? `Ask anything about ${repoName}` : 'Load a repository to begin'}</h2>
            <p className="muted">
              Every answer cites the code it comes from. When the built-in tools are not enough, the assistant
              writes and tests a new tool for itself. Answers take a few minutes on this laptop.
            </p>
            {canAsk && repoName === DEMO_REPO && (
              <>
                <div className="examples-label">Try one of these</div>
                <div className="examples">
                  {EXAMPLES.map((example) => (
                    <button key={example} type="button" className="example" onClick={() => setQuestion(example)}>
                      {example}
                    </button>
                  ))}
                </div>
              </>
            )}
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
              {turn.cancelled && <div className="muted">Stopped before an answer was written.</div>}
              {turn.running && !turn.answer && (
                <div className="muted">
                  {turn.stopping ? 'Stopping after the current step...' : 'Working... see the activity panel.'}
                </div>
              )}
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
        {running ? (
          <button type="button" className="secondary" disabled={!running.runId || running.stopping}
                  onClick={() => onStop(running)}>
            {running.stopping ? 'Stopping...' : 'Stop'}
          </button>
        ) : (
          <button type="submit" disabled={!canAsk || !question.trim()}>
            Ask
          </button>
        )}
      </form>
    </section>
  )
}
