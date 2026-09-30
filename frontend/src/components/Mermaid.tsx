import mermaid from 'mermaid'
import { useEffect, useId, useState } from 'react'

mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'default' })

/** Renders a Mermaid diagram; if it fails, shows the source instead (plan requirement). */
export default function Mermaid({ code }: { code: string }) {
  const id = 'mmd' + useId().replace(/[^a-zA-Z0-9]/g, '')
  const [svg, setSvg] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    mermaid
      .render(id, code)
      .then(({ svg }) => {
        if (cancelled) return
        setSvg(svg)
        setError(null)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setSvg(null)
        setError(String(err))
      })
    return () => {
      cancelled = true
    }
  }, [id, code])

  if (error) {
    return (
      <div className="mermaid-error">
        <div className="muted">Diagram could not be rendered; source:</div>
        <pre>{code}</pre>
      </div>
    )
  }
  return svg ? <div className="mermaid" dangerouslySetInnerHTML={{ __html: svg }} /> : <div className="muted">Drawing diagram...</div>
}
