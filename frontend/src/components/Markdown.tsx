import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import Mermaid from './Mermaid'

// [E3, app/x.py:42] or [E1][E2] -> clickable links to the evidence
const CITATION_RE = /\[(E\d+)((?:[,;]\s*[^\]]*)?)\]/g

function linkCitations(text: string): string {
  return text.replace(CITATION_RE, (_m, id: string, rest: string) => `[${id}${rest}](#ev-${id})`)
}

interface Props {
  text: string
  onCitation: (evidenceId: string) => void
}

export default function Markdown({ text, onCitation }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a({ href, children }) {
          if (href?.startsWith('#ev-')) {
            const id = href.slice(4)
            return (
              <a
                href={href}
                className="citation"
                title={`Show evidence ${id}`}
                onClick={(e) => {
                  e.preventDefault()
                  onCitation(id)
                }}
              >
                {children}
              </a>
            )
          }
          return (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          )
        },
        code({ className, children }) {
          const source = String(children).replace(/\n$/, '')
          if (className === 'language-mermaid') return <Mermaid code={source} />
          return <code className={className}>{children}</code>
        },
      }}
    >
      {linkCitations(text)}
    </ReactMarkdown>
  )
}
