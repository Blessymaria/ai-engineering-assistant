export interface RepoSummary {
  name: string
  root: string
  commit: string | null
  files: number
  nodes: number
  edges: number
  kinds: Record<string, number>
  suggestions?: string[]
}

export interface Evidence {
  id: string
  tool: string
  args: Record<string, unknown>
  summary: string
  result: unknown
}

export interface Citations {
  cited: string[]
  missing: string[]
  valid: number
  total: number
  problems?: string[] // locations or paths that failed the checks after the one rewrite
}

export type StepKind = 'tool' | 'gap' | 'create' | 'invalid' | 'limit' | 'answer' | 'error'
export type StepStatus = 'running' | 'ok' | 'error' | 'warn'

export interface Step {
  id: number
  kind: StepKind
  status: StepStatus
  title: string
  detail?: string
  evidenceId?: string
  modelSeconds?: number
  toolMs?: number
  // For created tools: code and test result, shown on click
  code?: string
  test?: { input: unknown; output: unknown }
}

export interface Turn {
  id: number
  question: string
  running: boolean
  answer?: string
  diagram?: string | null
  citations?: Citations
  error?: string
  steps: Step[]
  evidence: Record<string, Evidence>
  seconds?: number
  rounds?: number
  // Model time since the last step; attached to the next step that appears
  pendingModelSeconds?: number
  runId?: string // backend id, used to cancel
  historyId?: number // id of the saved conversation, once stored
  savedAt?: string // set when the turn was reopened from history
  stopping?: boolean
  cancelled?: boolean
}

export interface DetailView {
  title: string
  body: string
  language?: 'json' | 'python' | 'text'
}

export interface HistorySummary {
  id: number
  created_at: string
  repo_name: string
  repo_commit: string | null
  question: string
  stopped: string
  rounds: number
  seconds: number
}

export interface HistoryRecord extends HistorySummary {
  answer: string
  diagram: string | null
  citations: Citations
  events: { type: string; data: Record<string, unknown> }[]
  evidence: Record<string, Evidence>
}

export interface RepoIntro {
  text: string
  source: 'model' | 'facts' // 'facts': the model was unreachable, so a plain sentence from the graph
  cached: boolean
}

export interface RecentRepo {
  source: string // the Git URL or local folder as it was typed
  name: string
}
