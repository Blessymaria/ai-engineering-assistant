import type { Step, Turn } from '../types'

const ICON: Record<Step['status'], string> = { running: '...', ok: '✓', error: '✗', warn: '!' }

function timing(step: Step): string {
  const parts = []
  if (step.modelSeconds) parts.push(`model ${step.modelSeconds.toFixed(1)}s`)
  if (step.toolMs !== undefined) parts.push(`tool ${step.toolMs} ms`)
  return parts.join(' · ')
}

interface Props {
  turn: Turn | null
  onOpen: (step: Step) => void
}

/** Shows actions only (tools, gaps, created tools), never model reasoning. */
export default function Activity({ turn, onOpen }: Props) {
  if (!turn) {
    return (
      <aside className="activity">
        <h2>Agent activity</h2>
        <p className="muted">
          Each step the agent takes appears here as it happens: searches, graph lookups, files read, capability gaps
          and any tool it creates. Click a step to see its full result.
        </p>
      </aside>
    )
  }
  return (
    <aside className="activity">
      <h2>Agent activity</h2>
      <ol className="steps">
        {turn.steps.map((step) => {
          const clickable = Boolean(step.evidenceId || step.code || step.detail)
          return (
            <li
              key={step.id}
              className={`step ${step.kind} ${step.status}${clickable ? ' clickable' : ''}`}
              onClick={() => clickable && onOpen(step)}
            >
              <span className="icon">{ICON[step.status]}</span>
              <div className="step-body">
                <div className="step-title">
                  {step.evidenceId && <span className="ev">{step.evidenceId}</span>}
                  {step.title}
                </div>
                {step.detail && <div className="step-detail">{step.detail}</div>}
                {timing(step) && <div className="step-time">{timing(step)}</div>}
              </div>
            </li>
          )
        })}
        {turn.running && (
          <li className="step running">
            <span className="icon spin">◌</span>
            <div className="step-body muted">Model is working (each step takes 10-60 s on this machine)...</div>
          </li>
        )}
      </ol>
      {!turn.running && turn.seconds !== undefined && (
        <p className="muted">
          Finished in {turn.seconds}s, {turn.rounds} tool rounds. Click a step for its full result.
        </p>
      )}
    </aside>
  )
}
