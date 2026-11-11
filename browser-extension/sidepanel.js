// Painel lateral do Lume: conversa com a IA do seu PC sem sair da pagina. Fala SO com o Lume em 127.0.0.1 (pelo token do pareamento).
// Nao executa nada no navegador sozinho: so le a pagina quando voce anexa (botao +) ou usa um atalho.
const $ = id => document.getElementById(id);
const store = { get: k => new Promise(r => chrome.storage.local.get(k, o => r(o[k]))), set: (k, v) => new Promise(r => chrome.storage.local.set({ [k]: v }, r)) };
let conn = { ok: false }, msgs = [], convId = null, busy = false, ctl = null, model = '', think = false, installed = [], attach = [], rec = null;
const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
function md(t) {   // markdown minimo: blocos de codigo, `codigo`, **negrito**, *italico*, paragrafos
  return String(t).split(/```/).map((p, i) => i % 2 ? '<pre><code>' + esc(p.replace(/^[\w+-]*\n/, '')) + '</code></pre>'
    : esc(p).replace(/`([^`\n]+)`/g, '<code>$1</code>').replace(/\*\*([^*\n]+)\*\*/g, '<b>$1</b>').replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>').split(/\n{2,}/).map(x => x.trim() ? '<p>' + x.replace(/\n/g, '<br>') + '</p>' : '').join('')).join('');
}
const bg = m => new Promise(r => { try { chrome.runtime.sendMessage(m, x => r(x || {})); } catch (e) { r({}); } });
async function api(path, body, signal) { return fetch(conn.base + path, { method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.assign({ token: conn.token }, body || {})) }); }

// ---------- conexao e modelo ----------
async function connect() {
  conn = await bg({ cmd: 'conn' });
  if (!conn.ok || !conn.base) { banner('Lume não encontrado. Abra o Lume neste PC (porta 8000 a 8010) e tente de novo.'); return false; }
  banner('');
  try { const i = await (await api('/api/browser/panel_info')).json(); installed = i.installed || []; model = (await store.get('model')) || i.model || installed[0] || ''; } catch (e) { model = (await store.get('model')) || ''; }
  think = !!(await store.get('think')); paint(); return true;
}
function banner(t) { const b = $('banner'); b.hidden = !t; b.textContent = t || ''; }
function paint() { $('model').textContent = (model || 'Modelo').replace(/^[a-z0-9]+:/i, '').slice(0, 28); $('effort').textContent = think ? 'Alto' : 'Baixo'; $('effort').classList.toggle('dim', !think); document.body.classList.toggle('chatting', msgs.length > 0); $('send').classList.toggle('stop', busy); $('send').innerHTML = busy ? '<svg viewBox="0 0 24 24"><rect x="7" y="7" width="10" height="10" rx="2"/></svg>' : '<svg viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>'; }

// ---------- conversa ----------
function bubble(role, text) { const d = document.createElement('div'); d.className = 'm ' + (role === 'user' ? 'u' : 'a'); if (role === 'user') d.textContent = text; else d.innerHTML = md(text); $('msgs').appendChild(d); document.body.classList.add('chatting'); $('log').scrollTop = $('log').scrollHeight; return d; }
async function send(textArg) {
  if (busy) { if (ctl) ctl.abort(); return; }
  const text = (textArg || $('in').value).trim(); if (!text) return;
  if (!conn.ok && !(await connect())) return;
  if (!model) { banner('Escolha um modelo (botão ao lado do microfone).'); return; }
  $('in').value = ''; grow();
  let content = text, shown = text;
  if (attach.length) { content = attach.map(a => `[${a.label}: ${a.title}]\n${a.url}\n"""\n${a.text}\n"""`).join('\n\n') + '\n\n' + text; shown = '📎 ' + attach.map(a => a.title).join(', ').slice(0, 80) + '\n' + text; attach = []; chips(); }
  msgs.push({ role: 'user', content }); bubble('user', shown);
  const out = bubble('assistant', ''); out.classList.add('dots'); busy = true; ctl = new AbortController(); paint(); let got = '';
  try {
    const sys = 'Voce e o Lume, um assistente num painel lateral do navegador. Responda em portugues do Brasil, direto e claro. Se o usuario anexou uma pagina ou trecho, use-o como contexto.';
    const res = await api('/api/browser/chat', { model, stream: true, think, search_web: false, agent: false, lang: 'pt', messages: [{ role: 'system', content: sys }].concat(msgs) }, ctl.signal);
    if (!res.ok) { const j = await res.json().catch(() => ({})); throw new Error(j.error || ('o Lume respondeu ' + res.status)); }
    const rd = res.body.getReader(), dec = new TextDecoder(); let buf = '';
    const one = l => { try { const d = JSON.parse(l); if (d.message && d.message.content) { got += d.message.content; out.classList.remove('dots'); out.innerHTML = md(got); $('log').scrollTop = $('log').scrollHeight; } } catch (e) { /* linha incompleta */ } };
    while (true) { const { done, value } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true }); const ls = buf.split('\n'); buf = ls.pop(); ls.forEach(one); }
    one(buf);
    if (/^\s*\[(Erro|Error)/.test(got)) out.classList.add('err');
    if (!got.trim()) { out.classList.remove('dots'); out.textContent = '(sem resposta)'; } else msgs.push({ role: 'assistant', content: got });
  } catch (e) { out.classList.remove('dots'); if (e.name !== 'AbortError') { out.classList.add('err'); out.textContent = 'Não consegui responder: ' + e.message; conn = { ok: false }; } else if (got) msgs.push({ role: 'assistant', content: got }); }
  busy = false; ctl = null; paint(); saveConv(); $('in').focus();
}
function newChat() { if (ctl) ctl.abort(); msgs = []; convId = null; attach = []; $('msgs').textContent = ''; chips(); document.body.classList.remove('chatting'); paint(); $('in').focus(); }
async function saveConv() {
  if (!msgs.length) return; const list = (await store.get('convs')) || [];
  if (!convId) convId = Date.now(); const i = list.findIndex(c => c.id === convId), c = { id: convId, t: Date.now(), title: (msgs[0].content.match(/"""\n[\s\S]*?\n"""\n\n([\s\S]*)$/) || [0, msgs[0].content])[1].slice(0, 60), msgs };
  if (i >= 0) list[i] = c; else list.unshift(c); await store.set('convs', list.slice(0, 30));
}
function openConv(c) { newChat(); convId = c.id; msgs = c.msgs; msgs.forEach(m => { if (m.role === 'user') bubble('user', (m.content.match(/"""\n[\s\S]*?\n"""\n\n([\s\S]*)$/) || [0, m.content])[1]); else if (m.role === 'assistant') bubble('assistant', m.content); }); paint(); }

// ---------- anexos: a pagina da aba ativa (so quando voce pede) ----------
async function pageContext(selOnly) {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab || !tab.id) throw new Error('não achei a aba ativa');
  if (/^(chrome|edge|about|brave|opera|vivaldi|comet|chrome-extension|moz-extension):/i.test(tab.url || '')) throw new Error('esta é uma página interna do navegador e não pode ser lida');
  const [r] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: sel => ({ title: document.title, url: location.href, text: (sel ? String(getSelection() || '') : (document.body ? document.body.innerText : '')).replace(/\n{3,}/g, '\n\n').trim().slice(0, 14000) }), args: [!!selOnly] });
  const v = r && r.result; if (!v || !v.text) throw new Error(selOnly ? 'nenhum trecho selecionado na página' : 'a página está vazia'); return v;
}
async function addPage(selOnly) { try { const v = await pageContext(selOnly); attach = attach.filter(a => a.label !== (selOnly ? 'TRECHO' : 'PAGINA')); attach.push({ label: selOnly ? 'TRECHO' : 'PAGINA', title: (selOnly ? 'Trecho de ' : '') + (v.title || v.url).slice(0, 60), url: v.url, text: v.text }); chips(); return true; } catch (e) { banner('Não consegui ler a página: ' + e.message + '.'); setTimeout(() => banner(''), 4500); return false; } }
function chips() { const b = $('chips'); b.textContent = ''; attach.forEach((a, i) => { const c = document.createElement('div'); c.className = 'cc'; const s = document.createElement('span'); s.textContent = '📎 ' + a.title; const x = document.createElement('button'); x.textContent = '✕'; x.title = 'Remover'; x.onclick = () => { attach.splice(i, 1); chips(); }; c.append(s, x); b.appendChild(c); }); }

// ---------- menus ----------
const pop = $('pop');
function hidePop() { pop.hidden = true; pop.textContent = ''; }
function openPop(anchor, build) {
  if (!pop.hidden && pop.dataset.for === anchor.id) { hidePop(); return; }
  pop.textContent = ''; build(pop); pop.dataset.for = anchor.id; pop.hidden = false;
  const r = anchor.getBoundingClientRect(), up = r.top > innerHeight / 2;
  pop.style.left = Math.max(8, Math.min(r.left, innerWidth - pop.offsetWidth - 8)) + 'px';
  pop.style.top = up ? Math.max(8, r.top - pop.offsetHeight - 8) + 'px' : (r.bottom + 6) + 'px';
}
const item = (p, label, fn, extra) => { const b = document.createElement('button'); b.className = 'it' + (extra && extra.on ? ' on' : ''); b.textContent = label; if (extra && extra.small) { const s = document.createElement('small'); s.textContent = extra.small; b.appendChild(s); } b.onclick = () => { hidePop(); fn(); }; p.appendChild(b); return b; };
const head = (p, t) => { const d = document.createElement('div'); d.className = 'hd'; d.textContent = t; p.appendChild(d); };
document.addEventListener('mousedown', e => { if (!pop.hidden && !pop.contains(e.target) && !e.target.closest('#' + (pop.dataset.for || '_'))) hidePop(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') hidePop(); });

$('plus').onclick = () => openPop($('plus'), p => { item(p, 'Anexar esta página', () => addPage(false)); item(p, 'Anexar o trecho selecionado', () => addPage(true)); });
$('fast').onclick = () => openPop($('fast'), p => {
  head(p, 'Atalhos');
  [['Resumir esta página', 'Resuma esta página em poucos tópicos.', false], ['Pontos principais e dúvidas', 'Liste os pontos principais desta página e o que pode gerar dúvida.', false], ['Traduzir a página', 'Traduza o conteúdo desta página para o português do Brasil.', false], ['Explicar o trecho selecionado', 'Explique de forma simples o trecho anexado.', true]]
    .forEach(([l, q, sel]) => item(p, l, async () => { if (await addPage(sel)) send(q); }));
});
$('model').onclick = () => openPop($('model'), p => {
  const q = document.createElement('input'); q.placeholder = 'Buscar ou digitar o id do modelo...'; p.appendChild(q);
  const box = document.createElement('div'); p.appendChild(box);
  const list = () => {
    box.textContent = ''; const f = q.value.trim().toLowerCase(), all = [...new Set([model, ...installed].filter(Boolean))];
    head(box, 'No seu PC / em uso'); all.filter(m => !f || m.toLowerCase().includes(f)).forEach(m => item(box, m.replace(/^[a-z0-9]+:/i, ''), async () => { model = m; await store.set('model', m); paint(); }, { on: m === model }));
    if (f && !all.some(m => m.toLowerCase() === f)) item(box, 'Usar "' + q.value.trim() + '"', async () => { model = q.value.trim(); await store.set('model', model); paint(); });
  };
  q.oninput = list; list(); setTimeout(() => q.focus(), 30);
});
$('effort').onclick = async () => { think = !think; await store.set('think', think); paint(); };
$('hist').onclick = async () => { const list = (await store.get('convs')) || []; openPop($('hist'), p => { head(p, 'Conversas anteriores'); if (!list.length) { const d = document.createElement('div'); d.className = 'st'; d.textContent = 'Nenhuma ainda.'; p.appendChild(d); } list.forEach(c => item(p, c.title || 'Conversa', () => openConv(c), { small: new Date(c.t).toLocaleDateString('pt-BR') })); }); };
$('new').onclick = newChat;
$('more').onclick = async () => {
  const st = await bg({ cmd: 'status' });
  openPop($('more'), p => {
    const s = document.createElement('div'); s.className = 'st'; s.innerHTML = '<span class="dot ' + (st.ok ? 'ok' : '') + '"></span>' + (st.ok ? 'Conectado ao Lume' : 'Lume não encontrado'); p.appendChild(s);
    if (st.ok && conn.base) item(p, 'Abrir o Lume', () => chrome.tabs.create({ url: conn.base }));
    if (!st.debugger && chrome.debugger && chrome.permissions && chrome.permissions.request) item(p, 'Permitir PDF e foto da página inteira', () => chrome.permissions.request({ permissions: ['debugger'] }, ok => { banner(ok ? 'Liberado. O navegador mostra um aviso amarelo "depurando" por alguns segundos quando a IA pede PDF ou a página inteira.' : 'Não foi liberado.'); setTimeout(() => banner(''), 6000); }));
    const sep = document.createElement('div'); sep.className = 'sep'; p.appendChild(sep);
    item(p, 'Apagar o histórico', async () => { await store.set('convs', []); newChat(); });
  });
};

// ---------- digitar, voz ----------
function grow() { const t = $('in'); t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight, 180) + 'px'; }
$('in').addEventListener('input', grow);
$('in').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
$('send').onclick = () => send();
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) $('mic').hidden = true;
else $('mic').onclick = () => {
  if (rec) { rec.stop(); return; }
  rec = new SR(); rec.lang = 'pt-BR'; rec.interimResults = true; rec.continuous = false; $('mic').classList.add('on'); const base = $('in').value ? $('in').value + ' ' : '';
  rec.onresult = e => { $('in').value = base + [...e.results].map(r => r[0].transcript).join(''); grow(); };
  rec.onerror = e => { banner(e.error === 'not-allowed' ? 'O navegador bloqueou o microfone para este painel.' : 'Não consegui ouvir (' + e.error + ').'); setTimeout(() => banner(''), 4000); };
  rec.onend = () => { rec = null; $('mic').classList.remove('on'); $('in').focus(); };
  try { rec.start(); } catch (e) { rec = null; $('mic').classList.remove('on'); }
};

paint(); connect(); setInterval(() => { if (!conn.ok && !busy) connect(); }, 6000); $('in').focus();
