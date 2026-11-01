// Lume - IA no navegador. Fala SO com o Lume que roda neste PC (127.0.0.1): pergunta "tem comando?" e devolve o resultado.
// Cada acao so acontece quando o dono permite no Lume (a pergunta de permissao aparece la, nao aqui).
// As funcoes page* rodam DENTRO da pagina (chrome.scripting.executeScript) e nao podem usar nada de fora delas.

function pageRead(maxChars) {
  const vis = el => { const r = el.getBoundingClientRect(), cs = getComputedStyle(el); return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0' && r.bottom > 0 && r.right > 0; };
  document.querySelectorAll('[data-lume-i]').forEach(e => e.removeAttribute('data-lume-i'));
  const sel = 'a[href],button,input,textarea,select,summary,[role=button],[role=link],[role=tab],[role=menuitem],[role=checkbox],[role=switch],[role=option],[contenteditable=""],[contenteditable=true],[onclick]';
  const els = [...document.querySelectorAll(sel)].filter(e => !e.disabled && e.type !== 'hidden' && vis(e)).slice(0, 150);
  const clean = s => String(s || '').replace(/\s+/g, ' ').trim();
  const lines = els.map((e, i) => {
    e.setAttribute('data-lume-i', String(i + 1));
    const tag = e.tagName.toLowerCase(), type = (e.getAttribute('type') || '').toLowerCase();
    const isField = tag === 'input' || tag === 'textarea' || tag === 'select';
    const lab = isField && e.labels && e.labels[0] ? clean(e.labels[0].innerText) : '';
    let label = isField && type !== 'submit' && type !== 'button' && type !== 'reset'
      ? (clean(e.getAttribute('aria-label')) || lab || clean(e.placeholder) || clean(e.title) || clean(e.name))   // nunca o valor: pode ser senha
      : (clean(e.innerText) || clean(e.getAttribute('aria-label')) || clean(e.title) || clean(e.alt) || clean(e.value));
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.isContentEditable) {
      const kind = tag === 'select' ? 'lista' : type === 'checkbox' ? 'caixa' : type === 'radio' ? 'opcao' : type === 'submit' || type === 'button' ? 'botao' : 'campo' + (type && type !== 'text' ? ' ' + type : '');
      const val = type === 'password' ? (e.value ? '(preenchida)' : '') : tag === 'select' ? clean(e.options[e.selectedIndex] && e.options[e.selectedIndex].text) : (type === 'checkbox' || type === 'radio') ? (e.checked ? 'marcada' : 'desmarcada') : clean(e.value || e.innerText);
      return `[${i + 1}] ${kind}${label && label !== val ? ' "' + label.slice(0, 60) + '"' : ''}${val ? ' = "' + val.slice(0, 60) + '"' : ''}`;
    }
    if (tag === 'a') return `[${i + 1}] link "${label.slice(0, 80)}" -> ${(e.href || '').slice(0, 90)}`;
    return `[${i + 1}] botao "${label.slice(0, 80)}"`;
  });
  const text = (document.body ? document.body.innerText : '').replace(/\n{3,}/g, '\n\n').trim();
  const cut = text.length > maxChars ? text.slice(0, maxChars) + `\n...[texto cortado: ${text.length - maxChars} caracteres a mais; role a pagina e leia de novo]` : text;
  return `${document.title}\n${location.href}\n\nTEXTO DA PAGINA:\n${cut}\n\nELEMENTOS (use o numero em click/type):\n${lines.join('\n') || '(nenhum)'}`;
}
function pageClick(idx) {
  const el = document.querySelector(`[data-lume-i="${idx}"]`);
  if (!el) return 'Erro: o elemento ' + idx + ' nao existe mais. Chame read_page de novo para ver a numeracao atual.';
  el.scrollIntoView({ block: 'center', inline: 'center' });
  const label = String(el.innerText || el.value || el.getAttribute('aria-label') || el.title || el.tagName).replace(/\s+/g, ' ').trim().slice(0, 60);
  el.click();
  return `Cliquei em [${idx}] ${label}`;
}
function pageType(idx, text, submit) {
  const el = document.querySelector(`[data-lume-i="${idx}"]`);
  if (!el) return 'Erro: o elemento ' + idx + ' nao existe mais. Chame read_page de novo para ver a numeracao atual.';
  el.scrollIntoView({ block: 'center' }); el.focus();
  if (el.isContentEditable) { document.execCommand('selectAll', false); document.execCommand('insertText', false, text); }
  else if (el.tagName === 'SELECT') {
    const o = [...el.options].find(x => x.text.trim().toLowerCase() === text.trim().toLowerCase() || x.value === text);
    if (!o) return 'Erro: a lista nao tem a opcao "' + text + '". Opcoes: ' + [...el.options].map(x => x.text.trim()).slice(0, 15).join(' | ');
    el.value = o.value; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
  } else if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
    const set = Object.getOwnPropertyDescriptor(el.tagName === 'INPUT' ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype, 'value').set;
    set.call(el, text); el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true }));
  } else return 'Erro: o elemento ' + idx + ' nao e um campo de texto.';
  if (submit) {
    const kd = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true });
    const notPrevented = el.dispatchEvent(kd);
    el.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    if (notPrevented && el.form) { if (el.form.requestSubmit) el.form.requestSubmit(); else el.form.submit(); }
  }
  return `Digitei em [${idx}]${submit ? ' e apertei Enter' : ''}.`;
}
function pageScroll(dir) {
  const h = Math.round(innerHeight * 0.8);
  if (dir === 'top') scrollTo({ top: 0, behavior: 'instant' }); else if (dir === 'bottom') scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' });
  else scrollBy({ top: dir === 'up' ? -h : h, behavior: 'instant' });
  return `Rolei (${dir}). Posicao: ${Math.round(scrollY)} de ${document.documentElement.scrollHeight} px.`;
}

// ------------------------------------------------------------------ acoes
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function target(a) {
  if (a && a.tab_id) return Number(a.tab_id);
  let t = (await chrome.tabs.query({ active: true, lastFocusedWindow: true }))[0] || (await chrome.tabs.query({ active: true }))[0];
  if (!t) throw new Error('nao ha nenhuma aba aberta');
  return t.id;
}
async function waitLoaded(id, ms = 15000) {
  const t0 = Date.now(); await sleep(350);
  while (Date.now() - t0 < ms) { const t = await chrome.tabs.get(id); if (t.status === 'complete') return t; await sleep(250); }
  return chrome.tabs.get(id);
}
async function inPage(id, func, args) {
  const t = await chrome.tabs.get(id);
  if (/^(chrome|edge|about|brave|opera|vivaldi|comet|moz-extension|chrome-extension|view-source):/i.test(t.url || '') || /^https:\/\/chromewebstore\.google\.com/.test(t.url || '')) throw new Error('o navegador nao deixa ler paginas internas ou da loja (' + (t.url || '').slice(0, 60) + '). Abra um site normal.');
  const r = await chrome.scripting.executeScript({ target: { tabId: id }, func, args: args || [] });
  return r && r[0] ? r[0].result : '';
}
const line = t => `[${t.id}]${t.active ? ' (ativa)' : ''} ${String(t.title || '').slice(0, 80)} - ${String(t.url || '').slice(0, 100)}`;

async function run(action, a) {
  a = a || {};
  if (action === 'tabs') { const ts = await chrome.tabs.query({}); return { text: ts.map(line).join('\n') || '(nenhuma aba)' }; }
  if (action === 'open_url') {
    let url = String(a.url || '').trim(); if (!url) throw new Error('falta o endereco (url)');
    if (!/^[a-z][a-z0-9+.-]*:/i.test(url)) url = 'https://' + url;
    if (!/^(https?|about):/i.test(url)) throw new Error('so abro enderecos http, https ou about');
    let t;
    if (a.new_tab === false) { const id = await target(a); t = await chrome.tabs.update(id, { url, active: true }); }
    else t = await chrome.tabs.create({ url, active: true });
    t = await waitLoaded(t.id); return { text: 'Aba ' + line(t) };
  }
  if (action === 'read_page') { const id = await target(a); return { text: await inPage(id, pageRead, [6000]) }; }
  if (action === 'click') {
    const id = await target(a), before = await chrome.tabs.get(id), out = await inPage(id, pageClick, [Number(a.index)]);
    if (String(out).startsWith('Erro')) return { text: out };
    await sleep(700); const t = await waitLoaded(id, 8000); return { text: out + `\nAgora: ${t.title} - ${t.url}${t.url !== before.url ? ' (a pagina mudou: chame read_page)' : ''}` };
  }
  if (action === 'type') {
    const id = await target(a), out = await inPage(id, pageType, [Number(a.index), String(a.text == null ? '' : a.text), !!a.submit]);
    if (a.submit && !String(out).startsWith('Erro')) { await sleep(800); await waitLoaded(id, 8000); }
    return { text: out };
  }
  if (action === 'scroll') { const id = await target(a); return { text: await inPage(id, pageScroll, [String(a.direction || 'down')]) }; }
  if (action === 'screenshot') {
    const id = await target(a); const t = await chrome.tabs.update(id, { active: true }); await chrome.windows.update(t.windowId, { focused: true }); await sleep(250);
    const url = await chrome.tabs.captureVisibleTab(t.windowId, { format: 'jpeg', quality: 60 });
    return { text: `Foto da aba ${t.title} - ${t.url}`, image: url.slice(url.indexOf(',') + 1) };
  }
  if (action === 'switch_tab') { const t = await chrome.tabs.update(Number(a.tab_id), { active: true }); await chrome.windows.update(t.windowId, { focused: true }); return { text: 'Aba em primeiro plano: ' + line(t) }; }
  if (action === 'close_tab') { await chrome.tabs.remove(Number(a.tab_id)); return { text: 'Aba ' + a.tab_id + ' fechada.' }; }
  if (action === 'back') { const id = await target(a); await chrome.tabs.goBack(id); const t = await waitLoaded(id); return { text: 'Voltei: ' + line(t) }; }
  throw new Error('acao desconhecida: ' + action);
}

// ------------------------------------------------------------------ conversa com o Lume
let TOKEN = null, BASE = null, running = false, lastOk = false;
const brand = () => { try { const b = (navigator.userAgentData && navigator.userAgentData.brands || []).map(x => x.brand).filter(x => !/not.?a.?brand|chromium/i.test(x)); return b[0] || (/Firefox/.test(navigator.userAgent) ? 'Firefox' : 'Chromium'); } catch (e) { return ''; } };
async function post(path, body, ms) {
  const ctl = new AbortController(), tm = setTimeout(() => ctl.abort(), ms || 30000);
  try { const r = await fetch(BASE + path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}), signal: ctl.signal }); return await r.json(); } finally { clearTimeout(tm); }
}
async function pair() {
  const saved = (await chrome.storage.local.get('port')).port, ports = [saved, 8000, 8001, 8002, 8003, 8004, 8005, 8006, 8007, 8008, 8009, 8010].filter((p, i, l) => p && l.indexOf(p) === i);
  for (const p of ports) {
    try { BASE = 'http://127.0.0.1:' + p; const r = await post('/api/browser/pair', {}, 1500); if (r && r.token && r.app === 'lume') { TOKEN = r.token; chrome.storage.local.set({ port: p }); lastOk = true; chrome.action.setBadgeText({ text: 'ON' }); chrome.action.setBadgeBackgroundColor({ color: '#2fa84f' }); return true; } } catch (e) { /* proxima porta */ }
  }
  BASE = null; lastOk = false; chrome.action.setBadgeText({ text: '' }); return false;
}
async function handle(cmd) {
  let res;
  try { res = await run(cmd.action, cmd.args); } catch (e) { res = { error: String((e && e.message) || e) }; }
  try { await post('/api/browser/result', { token: TOKEN, id: cmd.id, result: res }, 20000); } catch (e) { /* o Lume vai dar tempo esgotado */ }
}
async function loop() {
  if (running) return; running = true;
  while (true) {
    try {
      if (!TOKEN && !(await pair())) { await sleep(4000); continue; }
      const r = await post('/api/browser/poll', { token: TOKEN, info: { brand: brand(), ua: navigator.userAgent.slice(0, 70) } }, 30000);
      if (r.error === 'token') { TOKEN = null; continue; }
      if (r.cmd) handle(r.cmd);   // sem await: o proximo poll ja volta a perguntar (varias acoes em fila)
    } catch (e) { TOKEN = null; lastOk = false; chrome.action.setBadgeText({ text: '' }); await sleep(3000); }
  }
}
chrome.runtime.onMessage.addListener((m, s, send) => { if (m && m.cmd === 'status') { send({ ok: lastOk }); } return false; });
chrome.runtime.onInstalled.addListener(() => { loop(); });
chrome.runtime.onStartup.addListener(() => { loop(); });
chrome.alarms.create('lume-keepalive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => { loop(); });
loop();
