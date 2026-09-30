import type { AgentEvent } from './api'
import type { Citations, Evidence, Step, Turn } from './types'

let nextStepId = 1

function argsText(args: unknown): string {
  if (!args || typeof args !== 'object') return ''
  return Object.entries(args as Record<string, unknown>)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? JSON.stringify(v) : String(v)}`)
    .join(', ')
}

function updateLast(steps: Step[], match: (s: Step) => boolean, patch: Partial<Step>): Step[] {
  const index = steps.map(match).lastIndexOf(true)
  if (index < 0) return steps
  return steps.map((s, i) => (i === index ? { ...s, ...patch } : s))
}

/** Pure reducer: fold one agent event into the turn it belongs to. */
export function applyEvent(turn: Turn, event: AgentEvent): Turn {
  const d = event.data
  const add = (step: Omit<Step, 'id'>): Turn => ({
    ...turn,
    pendingModelSeconds: undefined,
    steps: [...turn.steps, { id: nextStepId++, modelSeconds: turn.pendingModelSeconds, ...step }],
  })

  switch (event.type) {
    case 'run':
      return { ...turn, runId: String(d.run_id) }
    case 'cancelled':
      return { ...add({ kind: 'limit', status: 'warn', title: `Stopped after ${d.rounds} tool rounds` }), cancelled: true }
    case 'llm_reply':
      return { ...turn, pendingModelSeconds: (turn.pendingModelSeconds ?? 0) + Number(d.seconds ?? 0) }
    case 'tool_called':
      return add({ kind: 'tool', status: 'running', title: `${d.tool}(${argsText(d.args)})` })
    case 'tool_result':
      return {
        ...turn,
        steps: updateLast(turn.steps, (s) => s.kind === 'tool' && s.status === 'running', {
          status: 'ok',
          detail: String(d.summary ?? ''),
          evidenceId: String(d.evidence_id),
          toolMs: Number(d.ms ?? 0),
        }),
      }
    case 'tool_error':
      return {
        ...turn,
        steps: updateLast(turn.steps, (s) => s.kind === 'tool' && s.status === 'running', {
          status: 'error',
          detail: String(d.error ?? ''),
        }),
      }
    case 'gap_detected':
      return add({ kind: 'gap', status: 'warn', title: `Capability gap: ${d.missing_capability}`, detail: String(d.reason ?? '') })
    case 'tool_generation_started':
      return add({ kind: 'create', status: 'running', title: 'Creating a tool...' })
    case 'tool_created': {
      const params = Object.keys(((d.parameters as { properties?: object })?.properties) ?? {}).join(', ')
      return {
        ...turn,
        steps: updateLast(turn.steps, (s) => s.kind === 'create' && s.status === 'running', {
          status: 'ok',
          title: `Created ${d.name}(${params})`,
          detail: `${d.description} - tested in ${d.seconds}s after ${d.attempts} attempt(s)`,
          code: String(d.code ?? ''),
          test: { input: d.test_input, output: d.test_output },
        }),
      }
    }
    case 'tool_failed':
      return {
        ...turn,
        steps: updateLast(turn.steps, (s) => s.kind === 'create' && s.status === 'running', {
          status: 'error',
          title: 'Tool creation failed',
          detail: (d.errors as string[] | undefined)?.join('; ') ?? '',
        }),
      }
    case 'invalid_action':
      return add({ kind: 'invalid', status: 'warn', title: 'Invalid step, sent back to the model', detail: String(d.error ?? '') })
    case 'limit_reached':
      return add({ kind: 'limit', status: 'warn', title: `Tool limit reached after ${d.rounds} rounds` })
    case 'answer': {
      const citations = d.citations as Citations
      const next = add({
        kind: 'answer',
        status: citations.missing.length ? 'warn' : 'ok',
        title: `Answer - citation refs valid: ${citations.valid}/${citations.total}`,
        detail: citations.missing.length ? `unknown ids: ${citations.missing.join(', ')}` : undefined,
      })
      return { ...next, answer: String(d.text ?? ''), citations, diagram: (d.diagram as string | null) ?? null }
    }
    case 'done':
      return {
        ...turn,
        running: false,
        evidence: (d.evidence as Record<string, Evidence>) ?? {},
        seconds: Number(d.seconds ?? 0),
        rounds: Number(d.rounds ?? 0),
      }
    case 'error':
      return {
        ...add({ kind: 'error', status: 'error', title: 'Error', detail: String(d.message ?? '') }),
        running: false,
        error: String(d.message ?? 'unknown error'),
      }
    default:
      return turn
  }
}
