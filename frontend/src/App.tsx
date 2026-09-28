import { useEffect, useState } from 'react'

function App() {
  const [status, setStatus] = useState('checking...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus('unreachable'))
  }, [])

  return (
    <main style={{ padding: '1rem' }}>
      <h1>AI Engineering Assistant</h1>
      <p>Backend: {status}</p>
    </main>
  )
}

export default App
