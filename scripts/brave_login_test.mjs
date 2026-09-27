// Full end-to-end: renders app in headless Brave, logs in via the real form,
// then reports whether the authenticated dashboard rendered.
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';

const APP = 'http://localhost:5173';
const PORT = 9224;
const BRAVE = 'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe';
const PROFILE = `${tmpdir()}\\brave_login_${Date.now()}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const proc = spawn(BRAVE, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
  '--disable-extensions', '--disable-sync', '--disable-brave-update',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${PROFILE}`, 'about:blank',
], { stdio: 'ignore' });

let targets = null;
for (let i = 0; i < 40; i++) {
  await sleep(500);
  try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); break; } catch {}
}
if (!targets) { console.log('FAIL: CDP never came up'); proc.kill(); process.exit(2); }
const page = targets.find((t) => t.type === 'page');
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));

let msgId = 0;
const pending = new Map();
const send = (method, params = {}) =>
  new Promise((res) => { const id = ++msgId; pending.set(id, res); ws.send(JSON.stringify({ id, method, params })); });
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); return; }
  if (m.method === 'Runtime.exceptionThrown')
    console.log('[JS EXCEPTION]', m.params.exceptionDetails.exception?.description?.slice(0, 200) ?? m.params.exceptionDetails.text);
};

await send('Runtime.enable');
await send('Page.enable');
await send('Page.navigate', { url: APP });
await sleep(6000);

// Fill the React-controlled inputs (native setter + input event) and submit.
const loginResult = await send('Runtime.evaluate', {
  expression: `(async () => {
    const setVal = (el, v) => {
      const proto = el.tagName === 'INPUT' ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    const [user, pass] = document.querySelectorAll('input');
    if (!user || !pass) return 'NO_FORM';
    setVal(user, 'admin');
    setVal(pass, 'admin123');
    document.querySelector('button[type=submit]')?.click();
    return 'SUBMITTED';
  })()`,
  awaitPromise: true,
  returnByValue: true,
});
console.log('login action:', loginResult?.result?.value);
await sleep(7000);

const state = await send('Runtime.evaluate', {
  expression: `JSON.stringify({
    signedInAs: document.body.innerText.includes('Sign Out'),
    rolesChip: /admin|planner|operations|engineer/i.test(document.body.innerText),
    dashboardKpis: document.body.innerText.includes('Dashboard'),
    error: document.body.innerText.includes('Login failed'),
    navItems: [...document.querySelectorAll('nav button')].map(b => b.textContent).slice(0, 6),
    text: document.body.innerText.slice(0, 500),
  })`,
  returnByValue: true,
});
console.log('--- RESULT ---');
console.log(state?.result?.value);
proc.kill();
process.exit(0);
