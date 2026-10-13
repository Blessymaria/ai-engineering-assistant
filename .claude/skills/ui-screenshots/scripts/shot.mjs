// Drive headless Edge over CDP: open the page, run clicks, save screenshots.
import { spawn } from 'node:child_process'
import { writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const proc = spawn(edge, ['--headless=new', '--disable-gpu', '--remote-debugging-port=9333', '--window-size=1440,900',
  `--user-data-dir=${mkdtempSync(join(tmpdir(), 'edge-'))}`, 'about:blank'])
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
let targets
for (let i = 0; i < 40; i++) { try { targets = await (await fetch('http://127.0.0.1:9333/json')).json(); break } catch { await sleep(250) } }
const page = targets.find((t) => t.type === 'page')
const ws = new WebSocket(page.webSocketDebuggerUrl)
await new Promise((r) => ws.addEventListener('open', r))
let id = 0; const pending = new Map()
ws.addEventListener('message', (m) => { const d = JSON.parse(m.data); if (pending.has(d.id)) { pending.get(d.id)(d.result); pending.delete(d.id) } })
const send = (method, params = {}) => new Promise((r) => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })) })
const js = (expr) => send('Runtime.evaluate', { expression: expr, awaitPromise: true })
const shot = async (name) => { const { data } = await send('Page.captureScreenshot', { format: 'png' }); writeFileSync(name, Buffer.from(data, 'base64')) }
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })
await send('Page.navigate', { url: 'http://localhost:5173/' }); await sleep(4000)
for (const step of process.argv.slice(2)) {
  if (step.startsWith('shot:')) await shot(step.slice(5))
  else if (step.startsWith('wait:')) await sleep(Number(step.slice(5)))
  else console.log(JSON.stringify((await js(step)).result?.value))
}
ws.close(); proc.kill()
