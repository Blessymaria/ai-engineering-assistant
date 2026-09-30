export interface RepoSummary {
  name: string
  root: string
  commit: string | null
  files: number
  nodes: number
  edges: number
  kinds: Record<string, number>
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
}

export interface DetailView {
  title: string
  body: string
  language?: 'json' | 'python' | 'text'
}
