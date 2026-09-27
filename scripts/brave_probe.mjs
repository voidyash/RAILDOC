// Renders a URL in headless Brave (same Chromium engine as the user's browser)
// via the DevTools Protocol and reports: network activity, console output,
// JS exceptions, and the final page text. Usage:
//   node scripts/brave_probe.mjs [url] [waitMs]
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';

const URL_TO_TEST = process.argv[2] ?? 'http://localhost:5173';
const WAIT_MS = Number(process.argv[3] ?? 8000);
const PORT = 9223;
const BRAVE = 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe';
const PROFILE = `${tmpdir()}\\brave_probe_${Date.now()}`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const proc = spawn(BRAVE, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  '--disable-extensions', '--disable-sync', '--disable-brave-update',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`,
  'about:blank',
], { stdio: 'ignore' });

let targets = null;
for (let i = 0; i < 40; i++) {
  await sleep(500);
  try {
    targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
    break;
  } catch { /* retry */ }
}
if (!targets) { console.log('RESULT: CDP never came up'); proc.kill(); process.exit(2); }

const page = targets.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));

let msgId = 0;
const pending = new Map();
const send = (method, params = {}) =>
  new Promise((res) => {
    const id = ++msgId;
    pending.set(id, res);
    ws.send(JSON.stringify({ id, method, params }));
  });

ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); return; }
  if (m.method === 'Runtime.consoleAPICalled')
    console.log(`[console.${m.params.type}]`, m.params.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 300));
  else if (m.method === 'Runtime.exceptionThrown')
    console.log('[JS EXCEPTION]', m.params.exceptionDetails.text, m.params.exceptionDetails.exception?.description?.slice(0, 300) ?? '');
  else if (m.method === 'Network.responseReceived')
    console.log('[net]', m.params.response.status, m.params.response.url.slice(0, 140));
  else if (m.method === 'Network.loadingFailed')
    console.log('[net FAIL]', m.params.errorText, m.params.blockedReason ?? '');
};

await send('Runtime.enable');
await send('Network.enable');
await send('Page.enable');

console.log(`--- navigating to ${URL_TO_TEST}, waiting ${WAIT_MS}ms ---`);
await send('Page.navigate', { url: URL_TO_TEST });
await sleep(WAIT_MS);

const text = await send('Runtime.evaluate', { expression: 'JSON.stringify({signIn: !!document.querySelector("button[type=submit]"), inputs: document.querySelectorAll("input").length, demoCreds: document.body.innerText.includes("Demo Credentials"), text: document.body.innerText.slice(0, 400)})', returnByValue: true });
const ready = await send('Runtime.evaluate', { expression: 'document.readyState', returnByValue: true });
const hasRoot = await send('Runtime.evaluate', { expression: "document.getElementById('root')?.children.length ?? 0", returnByValue: true });

console.log('--- RESULT ---');
console.log('readyState:', ready?.result?.value);
console.log('root children:', hasRoot?.result?.value);
console.log('--- PAGE TEXT ---');
console.log(text?.result?.value || '(empty)');

proc.kill();
process.exit(0);
