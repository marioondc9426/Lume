/* Lume no iPhone: porte em JavaScript do servidor (app.py).
   A interface (index.html) continua a mesma e chama fetch('/api/...'); este arquivo responde a essas chamadas dentro do proprio app,
   sem PC ligado: modelos da nuvem (Pollinations, OpenRouter, Groq, Vercel, LLM7, tomdacat) e, se voce quiser, o Ollama de um PC (configuracoes > Ollama no PC).
   Fica de fora (depende do PC): aba Code com ferramentas, rodar codigo, Cloudflare Workers AI, tunel/compartilhar, atualizador, leitura de PDF/Word.
   Os dados (modelos, precos) vem de backend-data.js, gerado a partir do app.py por ios/gen_data.py. */
(() => {
'use strict';
if (window.__lumeBackend) return;
window.__lumeBackend = true;
window.__LUME_IOS = true;
document.documentElement.classList.add('is-ios');
const D = window.LUME_DATA || { POL_MODELS: [], VERCEL_MODELS: [], TDC_MODELS: [], POL_MAX_PRICE: 4.5, TDC_MAX_CR: 100, MODEL_EXCLUDE: '^$', GROQ_EXCLUDE: '^$' };
const VERSION = '3.0';
const realFetch = window.fetch.bind(window);
const enc = new TextEncoder();
const POL_API = 'https://gen.pollinations.ai', OR_URL = 'https://openrouter.ai/api/v1', GROQ_URL = 'https://api.groq.com/openai/v1';
const VERCEL_URL = 'https://ai-gateway.vercel.sh/v1', LLM7_URL = 'https://api.llm7.io/v1', TDC_URL = 'https://ai.tomdacat.com';
const AC_URL = 'https://www.aichixia.xyz/api/v1', AH_URL = 'https://aihubmix.com/v1', LR_URL = 'https://api.literouter.com/v1', PX_URL = 'https://api.paxsenix.org/v1', TK_URL = 'https://api.tokenreply.com/v1', VD_URL = 'https://api.voidai.app/v1';
const XPROV = { lr: ['literouter_api_key', LR_URL, 'LiteRouter', 8000], ac: ['aichixia_api_key', AC_URL, 'Aichixia', 1500], ah: ['aihubmix_api_key', AH_URL, 'AIHubMix', 1500], px: ['paxsenix_api_key', PX_URL, 'Paxsenix', 1500], vd: ['voidai_api_key', VD_URL, 'VoidAI', 1500], tk: ['tokenreply_api_key', TK_URL, 'TokenReply', 1500] };   // um lugar so para colocar outro provedor
const CLOUD_PREFIX = /^(groq|or:|cf:|pol:|tdc:|vc:|l7:|ac:|ah:|lr:|px:|vd:)/;
const now = () => Date.now() / 1000;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const re = (src, flags) => { try { return new RegExp(src.replace(/\(\?i\)/g, ''), flags || 'i'); } catch (e) { return /^$/; } };

// ---------------------------------------------------------------- armazenamento (IndexedDB; se faltar, localStorage)
const LS = {
    get(k, d) { try { const v = localStorage.getItem('lume.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('lume.' + k, JSON.stringify(v)); } catch (e) { /* cheio */ } },
};
// contas: sem senha, so separam as conversas, memorias, temas e estatisticas de quem usa o aparelho (as chaves de API sao do aparelho)
const ACCT_KEYS = ['history', 'state', 'stats', 'themes', 'ollama_key'];
let ACCT = String(LS.get('account', '') || '');
const scoped = k => (ACCT && ACCT_KEYS.includes(k)) ? 'a:' + ACCT + ':' + k : k;
const kv = (() => {
    // guarda em DOIS lugares (IndexedDB e localStorage) e le de onde houver dado; se o IndexedDB travar ou falhar, o localStorage segura
    let dbp = null, idbState = 'nao testado';
    const open = () => dbp || (dbp = new Promise((res, rej) => { const r = indexedDB.open('lume', 1); r.onupgradeneeded = () => r.result.createObjectStore('kv'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); r.onblocked = () => rej(new Error('bloqueado')); }));
    const limit = (p, ms) => { let t; return Promise.race([p, new Promise((_, rej) => { t = setTimeout(() => rej(new Error('demorou demais')), ms); })]).finally(() => clearTimeout(t)); };
    const idbGet = async k => { const db = await open(); return new Promise((res, rej) => { const q = db.transaction('kv').objectStore('kv').get(k); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); }); };
    const idbPut = async (k, v) => { const db = await open(); return new Promise((res, rej) => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = res; t.onerror = () => rej(t.error); t.onabort = () => rej(t.error || new Error('abortou')); }); };
    const lsGet = k => { try { const v = localStorage.getItem('lume.' + k); return v == null ? undefined : JSON.parse(v); } catch (e) { return undefined; } };
    const lsPut = (k, v) => { try { localStorage.setItem('lume.' + k, JSON.stringify(v)); return true; } catch (e) { return false; } };
    return {
        get state() { return idbState; },
        async get(k, d) { return this.rawGet(scoped(k), d); },
        async rawGet(k, d) {
            let v; try { v = await limit(idbGet(k), 2500); idbState = 'ok'; } catch (e) { v = undefined; idbState = 'falhou: ' + String(e && e.message || e).slice(0, 40); }
            if (v === undefined) v = lsGet(k);
            return v === undefined ? d : v;
        },
        async del(k) { try { await limit((async () => { const db = await open(); await new Promise((res, rej) => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').delete(k); t.oncomplete = res; t.onerror = () => rej(t.error); }); })(), 2500); } catch (e) { /* so o localStorage */ } try { localStorage.removeItem('lume.' + k); } catch (e) { /* nada */ } },
        async set(k, v) { return this.rawSet(scoped(k), v); },
        async rawSet(k, v) {
            let ok = false; try { await limit(idbPut(k, v), 2500); ok = true; idbState = 'ok'; } catch (e) { idbState = 'falhou: ' + String(e && e.message || e).slice(0, 40); }
            const l = lsPut(k, v); return ok || l;
        },
        async probe() {   // grava e le de volta nos dois lugares (para o diagnostico)
            const stamp = String(Date.now()); let idb = false, ls = false;
            try { await limit(idbPut('__probe', stamp), 2500); idb = (await limit(idbGet('__probe'), 2500)) === stamp; } catch (e) { idb = false; }
            ls = lsPut('__probe', stamp) && lsGet('__probe') === stamp; return { idb, ls };
        },
    };
})();

const CFG_DEFAULTS = { groq_api_key: '', openrouter_api_key: '', pollinations_api_key: '', vercel_api_key: '', llm7_api_key: '', tomdacat_api_key: '', exa_api_key: '', cloudflare_api_token: '', cloudflare_account_id: '',
    search_provider: 'auto', exa_type: 'lite', search_results: 8, search_daily_limit: 100, auto_allow: false, workdir: '', ollama_url: '', usage: { groq: 0 } };
let _cfg = null;
async function loadConfig() { if (!_cfg) _cfg = Object.assign({}, CFG_DEFAULTS, await kv.get('config', {})); return _cfg; }
async function saveConfig(c) { _cfg = c; await kv.set('config', c); }

const json = (obj, status) => new Response(JSON.stringify(obj), { status: status || 200, headers: { 'Content-Type': 'application/json' } });
const slug = s => String(s || '').replace(/[^\w\- ]/g, '_').trim().slice(0, 40) || 'tema';

// ---------------------------------------------------------------- rede
async function fetchT(url, opts, ms, label) {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort('timeout'), ms || 45000);
    const ext = opts && opts.signal; if (ext) ext.addEventListener('abort', () => ctl.abort(ext.reason));
    try { return await realFetch(url, Object.assign({}, opts, { signal: ctl.signal })); }
    catch (e) {
        if (ctl.signal.reason === 'timeout') throw new Error(`${label || 'O servidor'} nao respondeu em ${Math.round((ms || 45000) / 1000)} s (sem conexao ou fora do ar).`);
        if (ext && ext.aborted) throw e;
        throw new Error(`Sem conexao com ${label || 'o servidor'}: ${String(e && e.message || e).slice(0, 100)}`);
    } finally { clearTimeout(t); }
}
const bearer = (key, extra) => Object.assign({ Authorization: 'Bearer ' + key, 'Content-Type': 'application/json' }, extra || {});
async function getJson(url, headers, ms, label) { const r = await fetchT(url, { headers: headers || {} }, ms || 20000, label); if (!r.ok) throw new Error(`${label || 'Servidor'} respondeu ${r.status}`); return r.json(); }
const errMsg = async (r, n) => { const body = await r.text().catch(() => ''); let m = body.slice(0, n || 250); try { const j = JSON.parse(body); m = String((j.error && j.error.message) || (typeof j.error === 'string' && j.error) || m).slice(0, n || 250); } catch (e) { /* texto puro */ } return { body, msg: m }; };

// ---------------------------------------------------------------- listas de modelos
const cache = { pol: { t: 0, key: '', cat: null }, lat: { t: 0, v: {} }, or: { t: 0, v: null }, groq: { t: 0, v: null }, vc: { t: 0, v: null }, l7: { t: 0, v: null }, tdc: { t: 0, v: null } };

async function polCatalog(key) {
    const c = cache.pol; if (c.cat && c.key === key && now() - c.t < 1800) return c.cat;
    const h = bearer(key); let data;
    try { data = (await getJson(POL_API + '/v1/models?reliability=all&limit=500', h, 30000, 'O Pollinations')).data || []; }
    catch (e) { data = (await getJson(POL_API + '/v1/models', h, 30000, 'O Pollinations')).data || []; }
    c.t = now(); c.key = key; c.cat = Object.fromEntries(data.filter(m => m.id).map(m => [m.id, m])); return c.cat;
}
async function polLatency(key) {
    const c = cache.lat; if (now() - c.t < 600) return c.v; const lat = {};
    try { const rows = (await getJson(POL_API + '/models/status', bearer(key), 15000)).data || []; rows.forEach(r => { if (String(r.event_type || '').endsWith('text') && r.model && r.latency_p50_ms) lat[r.model] = Math.round(r.latency_p50_ms / 100) / 10; }); } catch (e) { /* sem latencia */ }
    c.t = now(); c.v = lat; return lat;
}
const rememberEfforts = async (slug, levels) => { polEffortOk[slug] = levels; const c = Object.assign({}, await loadConfig()); c.pol_effort_ok = Object.assign({}, c.pol_effort_ok, { [slug]: levels }); await saveConfig(c); };
const polPrice = m => { const p = (m && m.pricing) || {}; return [(+p.promptTextTokens || 0) * 1e6, (+p.completionTextTokens || 0) * 1e6]; };

async function pollinationsModels(cfg) {
    const key = cfg.pollinations_api_key || '', cat = await polCatalog(key), lat = await polLatency(key), out = [];
    for (const [mid, ex] of D.POL_MODELS) {
        const m = cat[mid] || {}, has = !!cat[mid]; let [pin, pout] = has ? polPrice(m) : [ex.pin || 0, ex.pout || 0];
        if (has && !m.pricing) { pin = ex.pin || 0; pout = ex.pout || 0; }
        const hl = m.health || {}, inm = m.input_modalities || ['text'], free = !!ex.free || (has && pin === 0 && pout === 0);
        const pimg = has ? (+((m.pricing || {}).promptImageTokens) || 0) * 1e6 : 0;
        if (!free && !ex.keep && Math.max(pin, pout, pimg) > D.POL_MAX_PRICE) continue;
        const caps = m.capabilities || [], rpm = m.per_user_rpm, parts = mid.split('/');
        out.push({ id: mid, name: m.title || parts[parts.length - 1], provider: mid.startsWith('community/') ? parts[1] : 'oficial', ctx: m.context_length || 128000, vision: inm.includes('image'), pin, pout, free, guess: !!ex.guess,
            health: hl.status || (ex.flaky ? 'degraded' : '?'), success: hl.success_rate == null ? null : hl.success_rate, official: !mid.startsWith('community/'), prio: !!ex.prio, speed: ex.speed || 0, tabs: ex.tabs || 'chat',
            warn: ex.warn || (rpm && rpm <= 5 ? `Limite de ${rpm} pedidos por minuto: se mandar varias mensagens seguidas pode dar erro de limite.` : ''),
            reasoning: has && (caps.includes('reasoning') || !!m.reasoning), effort: (m.supported_parameters || []).includes('reasoning_effort'),
            tools: has ? (caps.includes('tool_calling') || !!m.tools) : null, rpm: rpm == null ? null : rpm, p50: lat[mid] == null ? null : lat[mid], efforts: polEffortOk[mid] || (cfg.pol_effort_ok || {})[mid] || null });
    }
    return out;
}
async function openrouterModels() {
    const c = cache.or; if (c.v && now() - c.t < 3600) return c.v;
    const data = (await getJson(OR_URL + '/models', {}, 15000, 'O OpenRouter')).data || [], ex = re(D.MODEL_EXCLUDE), out = [];
    for (const m of data) {
        const pr = m.pricing || {}; let free = false;
        try { free = ['prompt', 'completion', 'request', 'image'].every(k => (+pr[k] || 0) === 0) && pr.prompt != null; } catch (e) { free = false; }
        const arch = m.architecture || {}, outm = arch.output_modalities || ['text'], inm = arch.input_modalities || ['text'];
        if (!free || JSON.stringify(outm) !== '["text"]' || !m.id || ex.test(m.id)) continue;
        out.push({ id: m.id, name: m.name || m.id, ctx: m.context_length || 0, vision: inm.includes('image'), think: (m.supported_parameters || []).includes('reasoning') });
    }
    out.sort((a, b) => a.name.toLowerCase() < b.name.toLowerCase() ? -1 : 1); c.t = now(); c.v = out; return out;
}
async function groqModels(cfg) {
    const c = cache.groq; if (c.v && now() - c.t < 3600) return c.v; const ex = re(D.GROQ_EXCLUDE);
    const data = (await getJson(GROQ_URL + '/models', { Authorization: 'Bearer ' + cfg.groq_api_key }, 20000, 'O Groq')).data || [];
    const out = data.filter(m => m.id && m.active !== false && !ex.test(m.id)).map(m => ({ id: m.id, ctx: m.context_window || 0, max_out: m.max_completion_tokens || 0 })).sort((a, b) => a.id < b.id ? -1 : 1);
    c.t = now(); c.v = out; return out;
}
async function oaiModels(base, key) { return (await getJson(base + '/models', { Authorization: 'Bearer ' + key }, 20000)).data || []; }
async function vercelModels(cfg) {
    const c = cache.vc; if (c.v && now() - c.t < 3600) return c.v;
    const have = Object.fromEntries((await oaiModels(VERCEL_URL, cfg.vercel_api_key)).map(m => [m.id, m]));
    const out = D.VERCEL_MODELS.filter(([id]) => have[id]).map(([id, name]) => ({ id, name, ctx: have[id].context_window || 128000 })); c.t = now(); c.v = out; return out;
}
async function llm7Models(cfg) {
    const c = cache.l7; if (c.v && now() - c.t < 3600) return c.v; const out = [];
    for (const m of await oaiModels(LLM7_URL, cfg.llm7_api_key)) {
        const mo = m.modalities || {};
        if (m.usage_based_only !== false || JSON.stringify(mo.output) !== '["text"]' || /whisper|Voxtral/.test(m.id || '')) continue;
        out.push({ id: m.id, ctx: m.context_window || 32768, tools: !!m.tools_calling, vision: (mo.input || []).includes('image') });
    }
    out.sort((a, b) => a.id < b.id ? -1 : 1); c.t = now(); c.v = out; return out;
}
async function tomdacatModels(cfg) {
    const c = cache.tdc; if (c.v && now() - c.t < 1800) return c.v;
    const data = Object.fromEntries(((await getJson(TDC_URL + '/api/models', { Authorization: 'Bearer ' + cfg.tomdacat_api_key }, 20000, 'O tomdacat')).data || []).filter(m => m.id).map(m => [m.id, m])); const out = [];
    for (const [id, name, tools, warn] of D.TDC_MODELS) {
        const m = data[id]; if (!m) continue; const pr = m.pricing || {}, cin = pr.credits_per_million_input || 0, cout = pr.credits_per_million_output || 0;
        if (pr.paid_only || Math.max(cin, cout) > D.TDC_MAX_CR) continue; out.push({ id, name, tools, warn, cr_in: cin, cr_out: cout });
    }
    c.t = now(); c.v = out; return out;
}

function polCost(model, ptok, otok) {   // pollen gasto (precos por milhao de tokens do catalogo; gratis = 0)
    if (!String(model).startsWith('pol:')) return 0; const slug = model.slice(4), ex = (D.POL_MODELS.find(x => x[0] === slug) || [0, {}])[1];
    if (ex.free) return 0; const m = cache.pol.cat && cache.pol.cat[slug], [pin, pout] = (m && m.pricing) ? polPrice(m) : [ex.pin || 0, ex.pout || 0];
    return (ptok * pin + otok * pout) / 1e6;
}
// ---------------------------------------------------------------- Aichixia / AIHubMix / LiteRouter: lista crua + teste de saude a cada 10 min
const XEX = () => re(D.X_EXCLUDE || '^$'), XNONCHAT = /safety|guard|embed|whisper|tts|image/i, SHOW_ALL = new Set(['vd', 'px', 'lr', 'tk']);   // vd/px/lr: todos os modelos de chat, sem teste de saude nem filtro de plano
   // modelos que nao entram (aleatorios, Llama, Grok...)
const XFIELD = Object.fromEntries(Object.entries(XPROV).map(([p, v]) => [p, v[0]])), XBASE = Object.fromEntries(Object.entries(XPROV).map(([p, v]) => [p, v[1]]));
let tkFreeSet = null, tkPrice = {};
async function tkFree() {   // TokenReply: so os gratis (model_ratio 0); a tabela de precos e publica
    if (tkFreeSet) return tkFreeSet;
    try { const d = await getJson(TK_URL.replace(/\/v1$/, '') + '/api/pricing', {}, 20000, 'O TokenReply'); const ok = (d.data || []).filter(x => x.access_tier === 'free' || x.access_tier === 'weekly_featured'); tkFreeSet = new Set(ok.map(x => x.model_name)); ok.forEach(x => { const r = Number(x.model_ratio || 0); tkPrice[x.model_name] = [r * 2e-6, r * Number(x.completion_ratio || 1) * 2e-6]; }); } catch (e) { return new Set(); }
    return tkFreeSet;
}
async function extraRaw(p, cfg) {
    const c = cache[p] || (cache[p] = { t: 0, v: null }); if (c.v && now() - c.t < 3600) return c.v;
    const list = [];
    for (const m of await oaiModels(XBASE[p], cfg[XFIELD[p]])) {
        if (/mythomax/i.test(String(m.id || ''))) continue;
        const id = String(m.id || ''); if (!id) continue;
        if (p === 'ac') { const caps = m.capabilities || []; if (m.tier !== 'free' || !caps.includes('chat') || XEX().test(id)) continue; list.push({ id, name: id.split('/').pop(), ctx: m.context_window || 128000, vision: caps.includes('multimodal') }); }
        else if (p === 'ah') { if (!/(^|[-:/])free$/.test(id) || XEX().test(id)) continue; list.push({ id, name: id.split('/').pop(), ctx: 128000, vision: false }); }
        else if (p === 'vd') { if (!(m.endpoints || []).includes('/v1/chat/completions') || /gemma/i.test(id) || XNONCHAT.test(id)) continue; if (m.supports_streaming === false) noStream.add(XBASE[p] + '|' + id); list.push({ id, name: id, ctx: m.max_context_tokens || 128000, vision: false, cin: m.input_multiplier || 0, cout: m.output_multiplier || 0, cbase: m.base_cost || 0 }); }
        else if (p === 'tk') { if (!(await tkFree()).has(id) || XNONCHAT.test(id) || /grok/i.test(id)) continue; list.push({ id, name: id.split('/').pop(), ctx: 128000, vision: false, cin: (tkPrice[id] || [0, 0])[0], cout: (tkPrice[id] || [0, 0])[1] }); }
        else if (p === 'px') { if (m.type !== 'chat.completions' || XNONCHAT.test(id)) continue; list.push({ id, name: m.name || id, ctx: m.max_context_tokens || 128000, vision: !!m.supports_vision }); }
        else { if (!id.endsWith(':free') || m.type !== 'chat' || XNONCHAT.test(id)) continue; list.push({ id, name: m.display_name || id, ctx: m.context_window || 128000, vision: !!(m.capabilities || {}).vision }); }
    }
    list.sort((a, b) => a.id < b.id ? -1 : 1); c.v = list; c.t = now(); return list;
}
async function healthTest(p, id, cfg) {   // 1 pedido de verdade: ok se vier texto (modelos que pensam precisam de espaco: 512 tokens)
    const t0 = now();
    try {
        const r = await fetchT(XBASE[p] + '/chat/completions', { method: 'POST', headers: bearer(cfg[XFIELD[p]]), body: JSON.stringify({ model: id, messages: [{ role: 'user', content: 'Responda so a palavra: ok' }], max_tokens: 512 }) }, 90000, 'O provedor');
        if (!r.ok) { const body = await r.text().catch(() => ''); if (r.status === 429 || (r.status === 403 && /ate limit|oncurrent/.test(body))) return { ok: null }; return { ok: false, ms: Math.round((now() - t0) * 1000), err: 'HTTP ' + r.status }; }
        const j = await r.json().catch(() => ({})), m = ((j.choices || [{}])[0] || {}).message || {};
        return String(m.content || m.reasoning_content || m.reasoning || '').trim() ? { ok: true, ms: Math.round((now() - t0) * 1000) } : { ok: false, ms: Math.round((now() - t0) * 1000), err: 'resposta vazia' };
    } catch (e) { return { ok: false, ms: 0, err: String(e.message || e).slice(0, 80) }; }
}
let healthRunning = false;
async function healthCycle() {   // reconfere os que falharam + 12 dos outros; falhou duas vezes seguidas = some da lista
    if (healthRunning || (typeof document !== 'undefined' && document.visibilityState === 'hidden')) return; healthRunning = true;
    try {
        const cfg = await loadConfig(), health = await kv.rawGet('health', {}), gap = Object.fromEntries(Object.entries(XPROV).map(([p, v]) => [p, v[3]]));
        for (const p of Object.keys(XPROV)) {
            if (!cfg[XFIELD[p]] || SHOW_ALL.has(p)) continue; let ids; try { ids = (await extraRaw(p, cfg)).map(m => m.id); } catch (e) { continue; }
            const bad = ids.filter(i => (health[p + ':' + i] || {}).ok === false), rest = ids.filter(i => !bad.includes(i)).sort((a, b) => ((health[p + ':' + a] || {}).ts || 0) - ((health[p + ':' + b] || {}).ts || 0)).slice(0, 12);
            for (const id of bad.concat(rest)) {
                if (Object.keys(stops).length) { healthRunning = false; return; }   // conversando: nao disputa o limite de pedidos
                let r = await healthTest(p, id, cfg); if (r.ok === false) { await sleep(gap[p]); r = await healthTest(p, id, cfg); }
                if (r.ok === null) { await sleep(gap[p] + 4000); continue; }
                health[p + ':' + id] = { ok: !!r.ok, ts: now(), ms: r.ms || 0, err: r.err || '' }; await kv.rawSet('health', health); await sleep(gap[p]);
            }
        }
    } finally { healthRunning = false; }
}
if (typeof setInterval !== 'undefined') { setTimeout(() => { healthCycle(); setInterval(healthCycle, 600000); }, 30000); }
window.__lumeHealthCycle = healthCycle;

// ---------------------------------------------------------------- estatisticas
async function recordEvent(ev) { const s = await kv.get('stats', { events: [] }); s.events.push(Object.assign({ ts: now() }, ev)); if (s.events.length > 5000) s.events = s.events.slice(-5000); await kv.set('stats', s); }
async function buildStats(days) {
    const t = now(), all = (await kv.get('stats', { events: [] })).events, evs = all.filter(e => e.ts >= t - days * 86400 && !e.user);
    const models = {}, daily = {}, tot = { requests: 0, tokens: 0, seconds: 0, pollen: 0 }, day = ts => { const d = new Date(ts * 1000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
    for (const e of evs) {
        if (e.type !== 'chat') continue;
        const d = daily[day(e.ts)] || (daily[day(e.ts)] = { requests: 0, tokens: 0, exa_cost: 0, pollen: 0 }), m = models[e.model || '?'] || (models[e.model || '?'] = { requests: 0, tokens: 0, seconds: 0, best_tps: 0, cloud: !!e.cloud });
        const tk = e.tokens || 0, sec = e.seconds || 0; m.requests++; m.tokens += tk; m.seconds += sec; if (sec > 0.2 && tk) m.best_tps = Math.max(m.best_tps, tk / sec);
        const pl = e.pollen || 0; d.pollen += pl; m.pollen = (m.pollen || 0) + pl; tot.pollen += pl; d.requests++; d.tokens += tk; tot.requests++; tot.tokens += tk; tot.seconds += sec;
    }
    Object.values(models).forEach(m => { m.avg_tps = m.seconds > 0 ? m.tokens / m.seconds : 0; });
    const series = []; for (let i = Math.min(days, 14) - 1; i >= 0; i--) { const k = day(t - i * 86400); series.push(Object.assign({ day: k }, daily[k] || { requests: 0, tokens: 0, exa_cost: 0, pollen: 0 })); }
    const z = () => ({ requests: 0, seconds: 0, tokens: 0 });
    return { days, totals: tot, models, exa: { searches: 0, reads: 0, cost: 0 }, series, since: evs.length ? Math.min(...evs.map(e => e.ts)) : null, ollama: { h5: z(), d7: z(), month: {}, local: z() } };
}

// ---------------------------------------------------------------- chat: leitura do SSE (formato OpenAI)
const EFFORT_ORDER = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'], polEffortOk = {};
function nearEffort(want, allowed) {
    allowed = EFFORT_ORDER.filter(a => allowed.includes(a)); if (!allowed.length) return null; if (allowed.includes(want)) return want;
    const wi = EFFORT_ORDER.includes(want) ? EFFORT_ORDER.indexOf(want) : 3;
    return allowed.slice().sort((a, b) => Math.abs(EFFORT_ORDER.indexOf(a) - wi) - Math.abs(EFFORT_ORDER.indexOf(b) - wi) || EFFORT_ORDER.indexOf(a) - EFFORT_ORDER.indexOf(b))[0];
}
async function readTimed(reader, ms) {
    let t; const to = new Promise((_, rej) => { t = setTimeout(() => rej(new Error(`O provedor parou de responder (sem dados por ${Math.round(ms / 1000)} s).`)), ms); });
    try { return await Promise.race([reader.read(), to]); } finally { clearTimeout(t); }
}
async function* sseChat(resp, t0, errMap, firstMs, idleMs) {
    const reader = resp.body.getReader(), dec = new TextDecoder(); let buf = '', first = 0, usage = null, cut = false, started = false, done = false;
    try {
        while (!done) {
            const { value, done: end } = await readTimed(reader, started ? (idleMs || 60000) : (firstMs || 60000)); started = true;
            if (end) break; buf += dec.decode(value, { stream: true });
            let nl; while ((nl = buf.indexOf('\n')) >= 0) {
                const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1);
                if (!line.startsWith('data:')) continue; const d = line.slice(5).trim(); if (d === '[DONE]') { done = true; break; }
                let j; try { j = JSON.parse(d); } catch (e) { continue; }
                if (j.error) { const e = typeof j.error === 'object' ? j.error : { message: j.error }; throw new Error((errMap && errMap[e.code]) || String(e.message || JSON.stringify(e)).slice(0, 200)); }
                if (j.usage) usage = j.usage;
                for (const ch of j.choices || []) {
                    const delta = ch.delta || {}, rs = delta.reasoning || delta.reasoning_content;
                    if (rs != null && rs !== '') { first = first || now(); yield ['thinking', String(rs)]; }
                    if (delta.content != null && delta.content !== '') { first = first || now(); yield ['content', String(delta.content)]; }
                    if (ch.finish_reason === 'length') cut = true;
                }
            }
        }
    } finally { try { reader.cancel(); } catch (e) { /* ja fechou */ } }
    if (cut) yield ['content', '\n\n[Cortado: o modelo atingiu o limite de tokens da resposta]'];
    if (usage && usage.completion_tokens) {
        const t = now(), win = Math.max(0.001, t - (first || t0)), total = Math.max(0.001, t - t0), burst = !!first && win < 0.25;
        const gen = (burst || usage.completion_tokens / win > 2500) ? total : win;
        yield ['stats', { tokens: usage.completion_tokens, seconds: gen, buffered: gen === total, limits: null, prompt_tokens: usage.prompt_tokens || 0, prompt_seconds: first ? first - t0 : 0, load_seconds: 0, total_seconds: total }];
    }
}
const toOai = messages => messages.map(m => (m.images && m.images.length && m.role === 'user')
    ? { role: 'user', content: [{ type: 'text', text: m.content }].concat(m.images.map(b => ({ type: 'image_url', image_url: { url: 'data:image/jpeg;base64,' + b } }))) }
    : { role: m.role, content: m.content });

const HTTP_ERR = {
    pol: { 401: 'Chave do Pollinations invalida (401). Confira a chave em Configuracoes.', 403: 'A chave do Pollinations nao tem permissao (403).', 402: 'Saldo de pollen insuficiente (402). Ganhe pollen nas missoes ou compre mais.', 429: 'Limite do Pollinations atingido (429). Espere um pouco.' },
    or: { 401: 'Chave do OpenRouter invalida (401). Confira a chave em Configuracoes.', 402: 'O OpenRouter pediu credito (402): este modelo nao e gratis para a sua conta.', 429: 'Limite do plano gratis do OpenRouter atingido (429). Espere um pouco ou tente amanha.', 404: 'O OpenRouter nao achou esse modelo (404): talvez ele saiu da lista gratis.' },
};
function oaiFail(label, code, body, msg) {
    if (/credit card|customer_verification_required/.test(body)) throw new Error('A Vercel exige um cartao cadastrado na conta para usar o AI Gateway (mesmo nos modelos gratis). Adicione em vercel.com > AI Gateway.');
    if (code === 403 && /ate limit|oncurrent/.test(body)) throw new Error(`${label}: limite de pedidos. ${msg}`);
    if (code === 401 || code === 403) throw new Error(`${label}: chave invalida ou sem permissao (${code}). ${msg}`);
    if (code === 402) throw new Error(`${label}: sem saldo (402).`);
    if (code === 429) throw new Error(`${label}: limite de pedidos (429). ${msg}`);
    throw new Error(`${label} respondeu ${code}: ${msg}`);
}
const noStream = new Set();   // modelos que responderam "streaming nao suportado": a resposta passa a vir inteira
async function* oaiNonStream(model, messages, base, key, label, maxTokens, signal, t0) {
    const payload = { model, messages: toOai(messages), stream: false }; if (maxTokens) payload.max_tokens = +maxTokens;
    const r = await fetchT(base + '/chat/completions', { method: 'POST', headers: bearer(key), body: JSON.stringify(payload), signal }, 120000, label);
    if (!r.ok) { const { body, msg } = await errMsg(r); oaiFail(label, r.status, body, msg); }
    const j = await r.json().catch(() => ({})), m = ((j.choices || [{}])[0] || {}).message || {}, think = m.reasoning_content || m.reasoning;
    if (think) yield ['thinking', String(think)]; if (m.content) yield ['content', String(m.content)];
    const u = j.usage || {}, total = Math.max(0.001, now() - t0);
    if (u.completion_tokens) yield ['stats', { tokens: u.completion_tokens, seconds: total, buffered: true, limits: null, prompt_tokens: u.prompt_tokens || 0, prompt_seconds: 0, load_seconds: 0, total_seconds: total }];
}
async function* streamOaiCompat(model, messages, base, key, label, maxTokens, signal) {
    key = (key || '').trim(); if (!key) throw new Error(`${label} sem chave. Abra Configuracoes e cole a chave.`);
    const payload = { model, messages: toOai(messages), stream: true, stream_options: { include_usage: true } }; if (maxTokens) payload.max_tokens = +maxTokens;
    const t0 = now();
    if (noStream.has(base + '|' + model)) { yield* oaiNonStream(model, messages, base, key, label, maxTokens, signal, t0); return; }
    for (let attempt = 0; attempt < 3; attempt++) {
        const r = await fetchT(base + '/chat/completions', { method: 'POST', headers: bearer(key), body: JSON.stringify(payload), signal }, 45000, label);
        if (r.ok) { yield* sseChat(r, t0, {}); return; }
        const { body, msg } = await errMsg(r);
        if (r.status === 400 && /treaming is not supported/.test(body)) { noStream.add(base + '|' + model); yield ['status', 'Este modelo nao aceita streaming: a resposta chega inteira']; yield* oaiNonStream(model, messages, base, key, label, maxTokens, signal, t0); return; }
        if ((r.status === 429 || (r.status === 403 && /ate limit|oncurrent/.test(body))) && attempt < 2) { let wait = parseFloat(r.headers.get('Retry-After') || (/[Rr]etry after (\d+(?:\.\d+)?)/.exec(msg) || /\((\d+(?:\.\d+)?) seconds/.exec(msg) || [0, 1])[1]) || 1; yield ['status', `Limite de pedidos; esperando ${Math.min(wait, 8).toFixed(0)} s`]; await sleep(Math.min(wait, 8) * 1000 + 300); continue; }
        oaiFail(label, r.status, body, msg);
    }
}
async function* streamPollinations(model, messages, think, cfg, maxTokens, effort, signal) {
    const key = (cfg.pollinations_api_key || '').trim(); if (!key) throw new Error('Chave do Pollinations nao configurada. Abra Configuracoes e cole sua chave.');
    const sl = model.slice(4); if (!/^[\w.\-/:]+$/.test(sl)) throw new Error('Modelo do Pollinations invalido.');
    const payload = { model: sl, messages: toOai(messages), stream: true, stream_options: { include_usage: true } }; if (maxTokens) payload.max_tokens = +maxTokens;
    const cat = await polCatalog(key).catch(() => null), m = cat && cat[sl];
    const useEffort = m ? (m.supported_parameters || []).includes('reasoning_effort') : (/(^|\/)gpt-[56]/.test(sl) && !/oss|codex/.test(sl));
    if (useEffort) { const want = EFFORT_ORDER.includes(effort) ? effort : (think ? 'medium' : 'none'), known = polEffortOk[sl] || (cfg.pol_effort_ok || {})[sl]; payload.reasoning_effort = (known ? nearEffort(want, known) : want) || want; }
    const t0 = now();
    for (let attempt = 0; attempt < 3; attempt++) {
        const r = await fetchT(POL_API + '/v1/chat/completions', { method: 'POST', headers: bearer(key), body: JSON.stringify(payload), signal }, 45000, 'O Pollinations');
        if (r.ok) { yield* sseChat(r, t0, {}); return; }
        const { body, msg } = await errMsg(r, 200);
        if (r.status === 429 && attempt < 2) { const wait = Math.min(15, parseFloat(r.headers.get('Retry-After') || 3) || 3); yield ['status', `Limite de pedidos do provedor; esperando ${wait.toFixed(0)} s`]; await sleep(wait * 1000); continue; }
        if (r.status === 400 && payload.reasoning_effort && attempt < 2) {
            const mm = /upported values are:?([^."]*)/.exec(body), ok = mm ? (mm[1].match(/'(\w+)'/g) || []).map(x => x.replace(/'/g, '')).filter(x => EFFORT_ORDER.includes(x)) : [];
            if (ok.length) { rememberEfforts(sl, ok); payload.reasoning_effort = nearEffort(payload.reasoning_effort, ok); } else delete payload.reasoning_effort; continue;
        }
        throw new Error(HTTP_ERR.pol[r.status] || `Pollinations respondeu ${r.status}: ${msg}`);
    }
}
async function* streamOpenrouter(model, messages, think, cfg, maxTokens, signal) {
    const key = cfg.openrouter_api_key || ''; if (!key) throw new Error('Chave do OpenRouter nao configurada. Abra Configuracoes e cole sua chave.');
    const sl = model.slice(3), payload = { model: sl, messages: toOai(messages), stream: true, stream_options: { include_usage: true } }; if (maxTokens) payload.max_tokens = +maxTokens; if (think) payload.reasoning = { enabled: true };
    const headers = bearer(key, { 'HTTP-Referer': 'https://github.com/marioondc9426/Lume', 'X-Title': 'Lume' }), t0 = now();
    for (let attempt = 0; attempt < 2; attempt++) {
        const r = await fetchT(OR_URL + '/chat/completions', { method: 'POST', headers, body: JSON.stringify(payload), signal }, 45000, 'O OpenRouter');
        if (r.ok) { yield* sseChat(r, t0, HTTP_ERR.or); return; }
        const body = await r.text().catch(() => '');
        if (attempt === 0 && payload.reasoning && r.status === 400) { delete payload.reasoning; continue; }
        throw new Error(HTTP_ERR.or[r.status] || `OpenRouter respondeu ${r.status}: ${body.slice(0, 200)}`);
    }
}
async function* streamGroq(model, messages, cfg, maxTokens, signal) {
    const key = (cfg.groq_api_key || '').trim(); if (!key) throw new Error('Chave do Groq nao configurada. Abra Configuracoes e cole sua chave.');
    const payload = { model: model.replace('groq-', ''), messages: messages.map(m => ({ role: m.role, content: m.content })), stream: true, stream_options: { include_usage: true } }; if (maxTokens) payload.max_tokens = +maxTokens;
    const r = await fetchT(GROQ_URL + '/chat/completions', { method: 'POST', headers: bearer(key), body: JSON.stringify(payload), signal }, 45000, 'O Groq');
    if (!r.ok) {
        const { msg } = await errMsg(r, 300), wait = r.headers.get('retry-after');
        if (r.status === 429) throw new Error(`Limite do Groq atingido (tokens por minuto ou pedidos por dia)${wait ? `. Tente de novo em ${wait} s` : ''}. ${msg}`);
        if (r.status === 401 || r.status === 403) throw new Error('Chave do Groq invalida ou sem permissao. Confira em Configuracoes.');
        throw new Error(`Groq respondeu ${r.status}: ${msg}`);
    }
    yield* sseChat(r, now(), {});
}
async function* streamTomdacat(model, messages, cfg, maxTokens, signal) {
    const key = (cfg.tomdacat_api_key || '').trim(); if (!key) throw new Error('Chave do tomdacat nao configurada. Abra Configuracoes e cole sua chave.');
    const payload = { model: model.slice(4), messages: toOai(messages), stream: true, stream_options: { include_usage: true } }; if (maxTokens) payload.max_tokens = +maxTokens;
    const r = await fetchT(TDC_URL + '/v1/chat/completions', { method: 'POST', headers: bearer(key), body: JSON.stringify(payload), signal }, 45000, 'O tomdacat');
    if (!r.ok) {
        const { msg } = await errMsg(r, 200);
        if (r.status === 401 || r.status === 403) throw new Error('Chave do tomdacat invalida ou sem permissao. Confira em Configuracoes.');
        if (r.status === 402) throw new Error('Os creditos do tomdacat acabaram (402).');
        if (r.status === 429) throw new Error(`Limite de pedidos do tomdacat (429)${msg ? ': ' + msg : ''}`);
        throw new Error(`O tomdacat respondeu ${r.status}: ${msg}`);
    }
    yield* sseChat(r, now(), {});
}
const isOllamaCloud = m => /(:|-)cloud$/.test(m || '');
async function* streamOllamaCloud(model, messages, think, numCtx, maxTokens, signal) {
    // modelos "Nuvem Ollama": a API da nuvem (ollama.com) com a chave da conta do Ollama; o nome na nuvem nao leva o "-cloud"
    const key = String(await kv.get('ollama_key', '') || '').trim();
    if (!key) throw new Error('Este modelo e da Nuvem Ollama. Entre com o Ollama em Configuracoes > Chaves de API > "Logar com o Ollama" (crie a chave em ollama.com/settings/keys).');
    const names = [...new Set([model.replace(/-cloud$/, ''), model.replace(/:cloud$/, ''), model.replace(/:cloud$/, ':latest')])];
    let lastErr = null;
    for (const name of names) {
        let got = false;
        try { for await (const ev of streamOllama(name, messages, think, numCtx, maxTokens, {}, signal, { base: 'https://ollama.com', headers: { Authorization: 'Bearer ' + key }, label: 'A nuvem do Ollama' })) { got = true; yield ev; } return; }
        catch (e) { if (got || e.status !== 404) throw e; lastErr = e; }
    }
    throw lastErr || new Error('A nuvem do Ollama nao achou este modelo.');
}
async function* streamOllama(model, messages, think, numCtx, maxTokens, cfg, signal, via) {
    const base = via ? via.base : (cfg.ollama_url || '').trim().replace(/\/+$/, '');
    if (!base) throw new Error('Este modelo roda no Ollama de um PC. Em Configuracoes > Ollama no PC, coloque o endereco do seu PC (ex.: http://192.168.0.10:11434). Os modelos da nuvem funcionam sem PC.');
    const payload = { model, messages, stream: true }; if (think) payload.think = true;
    const opts = {}; if (numCtx) opts.num_ctx = +numCtx; if (maxTokens) opts.num_predict = +maxTokens; if (Object.keys(opts).length) payload.options = opts;
    const r = await fetchT(base + '/api/chat', { method: 'POST', headers: Object.assign({ 'Content-Type': 'application/json' }, via ? via.headers : {}), body: JSON.stringify(payload), signal }, 30000, via ? via.label : 'O Ollama do PC');
    if (!r.ok) {
        const txt = (await r.text().catch(() => '')).slice(0, 200), e = new Error(r.status === 401 || r.status === 403 ? 'A chave do Ollama nao foi aceita (' + r.status + '). Entre de novo em Configuracoes > Chaves de API.' : `O Ollama respondeu ${r.status}: ${txt}`); e.status = r.status; throw e;
    }
    const reader = r.body.getReader(), dec = new TextDecoder(); let buf = '', tFirst = null;
    try {
        for (;;) {
            const { value, done } = await readTimed(reader, 300000); if (done) break; buf += dec.decode(value, { stream: true });
            let nl; while ((nl = buf.indexOf('\n')) >= 0) {
                const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue; let d; try { d = JSON.parse(line); } catch (e) { continue; }
                if (d.error) throw new Error(String(d.error).slice(0, 200));
                const m = d.message || {}; if ((m.thinking || m.content) && tFirst == null) tFirst = now();
                if (m.thinking) yield ['thinking', m.thinking]; if (m.content) yield ['content', m.content];
                if (d.done && d.eval_count) {
                    if (d.eval_duration) yield ['stats', { tokens: d.eval_count, seconds: d.eval_duration / 1e9, prompt_tokens: d.prompt_eval_count || 0, prompt_seconds: (d.prompt_eval_duration || 0) / 1e9, load_seconds: (d.load_duration || 0) / 1e9, total_seconds: (d.total_duration || 0) / 1e9 }];
                    else if (tFirst) yield ['stats', { tokens: d.eval_count, seconds: Math.max(0.001, now() - tFirst), prompt_tokens: d.prompt_eval_count || 0, prompt_seconds: 0, load_seconds: 0, total_seconds: (d.total_duration || 0) / 1e9 }];
                }
            }
        }
    } finally { try { reader.cancel(); } catch (e) { /* ja fechou */ } }
}

// chaves de reserva: se a principal morrer antes de qualquer resposta, tenta a proxima (evita a que falhou por 10 min)
const KEY_FIELDS = [...Object.entries(XPROV).map(([p, v]) => [p + ':', v[0]]), ['pol:', 'pollinations_api_key'], ['tdc:', 'tomdacat_api_key'], ['vc:', 'vercel_api_key'], ['l7:', 'llm7_api_key'], ['or:', 'openrouter_api_key'], ['groq', 'groq_api_key']];
const KEY_FAIL = /\b(401|402|403|429)\b|chave|saldo|pollen|credit|quota|limite|api key|unauthorized/i, badKeys = {};
function streamOnce(model, messages, o) {
    const { think, cfg, numCtx, maxTokens, effort, signal } = o;
    if (model.startsWith('pol:')) return streamPollinations(model, messages, think, cfg, maxTokens, effort, signal);
    if (model.startsWith('tdc:')) return streamTomdacat(model, messages, cfg, maxTokens, signal);
    if (model.startsWith('vc:')) return streamOaiCompat(model.slice(3), messages, VERCEL_URL, cfg.vercel_api_key, 'A Vercel', maxTokens, signal);
    if (model.startsWith('l7:')) return streamOaiCompat(model.slice(3), messages, LLM7_URL, cfg.llm7_api_key, 'O LLM7', maxTokens, signal);
    for (const [p, v] of Object.entries(XPROV)) if (model.startsWith(p + ':')) return streamOaiCompat(model.slice(p.length + 1), messages, v[1], cfg[v[0]], 'O ' + v[2], maxTokens, signal);
    if (model.startsWith('or:')) return streamOpenrouter(model, messages, think, cfg, maxTokens, signal);
    if (model.startsWith('cf:')) return (async function* () { throw new Error('O Cloudflare Workers AI ainda nao esta disponivel no iPhone. Use os outros provedores.'); })();
    if (model.startsWith('groq')) return streamGroq(model, messages, cfg, maxTokens, signal);
    if (isOllamaCloud(model)) return streamOllamaCloud(model, messages, think, numCtx, maxTokens, signal);
    return streamOllama(model, messages, think, numCtx, maxTokens, cfg, signal);
}
async function* streamModel(model, messages, o) {
    const hit = KEY_FIELDS.find(([pre]) => model.startsWith(pre)), field = hit && hit[1], cfg = o.cfg;
    const keys = field ? [...new Set([(cfg[field] || '').trim()].concat(String(cfg[field + '_backup'] || '').split(/[\s,;]+/)).filter(Boolean))] : [];
    if (!field || keys.length < 2) { yield* streamOnce(model, messages, o); return; }
    const t = now(), order = keys.filter(k => (badKeys[k] || 0) < t).concat(keys.filter(k => (badKeys[k] || 0) >= t));
    for (let i = 0; i < order.length; i++) {
        let got = false;
        try { for await (const ev of streamOnce(model, messages, Object.assign({}, o, { cfg: Object.assign({}, cfg, { [field]: order[i] }) }))) { if (ev[0] === 'content' || ev[0] === 'thinking') got = true; yield ev; } return; }
        catch (e) { if (got || i + 1 >= order.length || !KEY_FAIL.test(String(e.message))) throw e; badKeys[order[i]] = now() + 600; yield ['status', 'Chave principal falhou; usando a de reserva']; }
    }
}

// separa o raciocinio (<think>...</think>) da resposta, mesmo quando a tag chega partida em dois pedacos
class ThinkSplitter {
    constructor() { this.buf = ''; this.inThink = false; }
    feed(piece) {
        this.buf += piece; const out = [];
        for (;;) {
            const tag = this.inThink ? '</think>' : '<think>', i = this.buf.indexOf(tag);
            if (i >= 0) { if (i) out.push([this.inThink ? 'thinking' : 'content', this.buf.slice(0, i)]); this.buf = this.buf.slice(i + tag.length); this.inThink = !this.inThink; continue; }
            let keep = 0; for (let k = Math.min(tag.length - 1, this.buf.length); k > 0; k--) if (tag.startsWith(this.buf.slice(-k))) { keep = k; break; }
            const emit = this.buf.slice(0, this.buf.length - keep); if (emit) out.push([this.inThink ? 'thinking' : 'content', emit]); this.buf = this.buf.slice(this.buf.length - keep); return out;
        }
    }
    flush() { const o = this.buf ? [[this.inThink ? 'thinking' : 'content', this.buf]] : []; this.buf = ''; return o; }
}

// ---------------------------------------------------------------- pesquisa na web (DuckDuckGo, sem chave)
async function searchWeb(query, n) {
    try {
        const r = await fetchT('https://html.duckduckgo.com/html/?q=' + encodeURIComponent(query), { headers: { Accept: 'text/html' } }, 15000, 'O DuckDuckGo');
        const doc = new DOMParser().parseFromString(await r.text(), 'text/html'), out = [];
        doc.querySelectorAll('.result').forEach(el => {
            const a = el.querySelector('.result__a'); if (!a || out.length >= (n || 5)) return;
            let href = a.getAttribute('href') || ''; const m = /[?&]uddg=([^&]+)/.exec(href); if (m) href = decodeURIComponent(m[1]); if (href.startsWith('//')) href = 'https:' + href;
            const sn = el.querySelector('.result__snippet'); if (/^https?:/.test(href)) out.push([a.textContent.trim(), (sn ? sn.textContent.trim() : ''), href]);
        });
        return out;
    } catch (e) { return []; }
}
const needsWeb = q => { const t = String(q || '').trim(); return t.length >= 15 && !t.includes('```') && t.split(/\s+/).length >= 3; };

// ---------------------------------------------------------------- /api/chat (uma linha JSON por evento, como o servidor Python)
const stops = {};
function handleChat(req) {
    const lang = req.lang === 'en' ? 'en' : 'pt', L = (pt, en) => lang === 'en' ? en : pt;
    const rid = String(req.rid || '').slice(0, 40) || Math.random().toString(36).slice(2, 12), ctl = new AbortController(); stops[rid] = ctl;
    const body = new ReadableStream({
        async start(c) {
            const emit = o => { try { c.enqueue(enc.encode(JSON.stringify(o) + '\n')); } catch (e) { /* aba fechada */ } };
            const send = (text, kind) => emit({ message: { role: 'assistant', [kind || 'content']: text } });
            const started = now(); let total = 0, tokens = 0, seconds = 0, prompt = 0; const model = req.model || '';
            try {
                const cfg = await loadConfig(); let messages = (req.messages || []).map(m => Object.assign({}, m));
                if (req.agent) { send(L('A aba Code (ferramentas no computador) precisa do PC e nao existe no iPhone. Use a aba Chat.', 'The Code tab (computer tools) needs a PC and is not available on iPhone. Use the Chat tab.')); return; }
                if (!messages.length || messages[0].role !== 'system') messages.unshift({ role: 'system', content: '' });
                if (CLOUD_PREFIX.test(model)) emit({ status: model.startsWith('vc:') ? 'Esperando a Vercel responder' : model.startsWith('l7:') ? 'Esperando o LLM7 responder' : model.startsWith('tdc:') ? 'Esperando o tomdacat responder' : model.startsWith('pol:') ? 'Esperando o Pollinations responder' : 'Conectando' });
                else emit({ status: isOllamaCloud(model) ? 'Conectando a nuvem do Ollama' : 'Conectando ao Ollama do PC' });
                if (req.search_web) {
                    const query = String([...messages].reverse().find(m => m.role === 'user' && m.content) ?.content || '').slice(0, 200);
                    if (needsWeb(query)) {
                        emit({ status: 'Pesquisando na web' }); const results = await searchWeb(query, Math.min(cfg.search_results || 5, 8));
                        if (results.length) {
                            emit({ sources: results.map(([t, , u]) => ({ title: t, url: u })), provider: 'duckduckgo', query });
                            messages[0].content += L(`\n\n[PESQUISA NA WEB - use se for relevante e cite os links. Quem pesquisou foi o app Lume, automaticamente, com o texto da ultima mensagem: "${query}"]\n`, `\n\n[WEB SEARCH - use it if relevant and cite the links. The Lume app searched automatically with the last message: "${query}"]\n`)
                                + results.map(([t, s, u], i) => `${i + 1}. ${t}\n${s}\n${u}`).join('\n\n');
                        } else messages[0].content += L('\n\n[A pesquisa na web falhou: voce NAO tem dados atuais. Se a pergunta depender de informacao recente, diga isso em vez de inventar.]', '\n\n[The web search failed: you do NOT have current data. If the question depends on recent information, say so instead of making things up.]');
                    }
                }
                if (!messages[0].content) messages.shift();
                const sp = new ThinkSplitter(); let full = '';
                for await (const [kind, piece] of streamModel(model, messages, { think: !!req.think, cfg, numCtx: req.num_ctx, maxTokens: null, effort: String(req.effort || '') || null, signal: ctl.signal })) {
                    if (ctl.signal.aborted) break;
                    if (kind === 'status') { emit({ status: piece }); continue; }
                    if (kind === 'thinking') { send(piece, 'thinking'); continue; }
                    if (kind === 'stats') { tokens += piece.tokens; seconds += piece.seconds; prompt += piece.prompt_tokens; emit({ stats: piece }); continue; }
                    for (const [k2, p2] of sp.feed(piece)) { if (k2 === 'thinking') send(p2, 'thinking'); else { full += p2; send(p2); } }
                }
                for (const [k2, p2] of sp.flush()) { if (k2 === 'thinking') send(p2, 'thinking'); else { full += p2; send(p2); } }
                total = full.length;
                if (ctl.signal.aborted) send(L('\n\n[Geracao parada]', '\n\n[Generation stopped]'));
                await recordEvent({ type: 'chat', model, cloud: CLOUD_PREFIX.test(model), tab: 'chat', tokens: tokens || Math.floor(total / 4), seconds: seconds || (now() - started), prompt_tokens: prompt, chars: total, pollen: polCost(model, prompt, tokens || Math.floor(total / 4)) });
            } catch (e) {
                if (!ctl.signal.aborted) send(L(`\n[Erro: ${e.message || e}]`, `\n[Error: ${e.message || e}]`));
            } finally { delete stops[rid]; try { c.close(); } catch (e) { /* ja fechou */ } }
        },
        cancel() { ctl.abort(); },
    });
    return new Response(body, { status: 200, headers: { 'Content-Type': 'application/x-ndjson' } });
}

// ---------------------------------------------------------------- rotas
const SECRET_KEYS = ['groq_api_key', 'openrouter_api_key', 'pollinations_api_key', 'cloudflare_api_token', 'cloudflare_account_id', 'exa_api_key', 'tomdacat_api_key', 'vercel_api_key', 'llm7_api_key',
    'groq_api_key_backup', 'openrouter_api_key_backup', 'pollinations_api_key_backup', 'tomdacat_api_key_backup', 'vercel_api_key_backup', 'llm7_api_key_backup',
    'aichixia_api_key', 'aihubmix_api_key', 'literouter_api_key', 'paxsenix_api_key', 'voidai_api_key', 'tokenreply_api_key', 'tokenreply_api_key_backup', 'aichixia_api_key_backup', 'aihubmix_api_key_backup', 'literouter_api_key_backup', 'paxsenix_api_key_backup', 'voidai_api_key_backup'];
const NOPE = () => json({ ok: false, error: 'Isto precisa do PC e nao existe no iPhone.' }, 400);
const listModels = (keyName, fn) => async () => {
    const cfg = await loadConfig(); if (!cfg[keyName]) return json({ saved: false, models: [] });
    try { return json({ saved: true, models: await fn(cfg) }); } catch (e) { return json({ saved: true, models: [], error: String(e.message || e).slice(0, 200) }); }
};
const ROUTES = {
    'GET /api/ping': () => json({ app: 'ai-thing', name: 'iPhone', password_required: false }),
    'GET /api/auth/status': () => json({ local: true, root: true, authed: true, role: 'owner', remote_enabled: false, allow_remote_code: false, password_required: false, version: VERSION, app_name: 'Lume', https_port: 0, secure: true, share_open: false, invite_required: false, ios: true }),
    'POST /api/auth/logout': () => json({ ok: true }),
    'GET /api/discover': () => json({ servers: [] }),
    'GET /api/pol_menu': async () => {
        const cfg = await loadConfig(), key = cfg.pollinations_api_key || '';
        try {
            cache.pol.cat = null; cache.lat.t = 0; const cat = await polCatalog(key), lat = await polLatency(key), out = [];
            for (const [mid, m] of Object.entries(cat)) {
                const pr = m.pricing || {}, hl = m.health || {}, price = ['promptTextTokens', 'completionTextTokens', 'promptImageTokens', 'completionImageTokens', 'completionAudioTokens', 'completionVideoTokens'].some(k => (+pr[k] || 0) > 0), quest = /quest/i.test(mid + ' ' + (m.title || ''));
                const [pin, pout] = polPrice(m);
                out.push({ id: mid, title: m.title || mid.split('/').pop(), category: m.category || (m.output_modalities || ['text']).join(','), owner: m.owned_by || '', community: !!m.community, success: hl.success_rate == null ? null : hl.success_rate, status: hl.status || '?', requests: hl.requests, p50: lat[mid] == null ? null : lat[mid],
                    free: !price && !m.paid_only, quest, paid: !!(price || m.paid_only) && !quest, pin, pout, outputs: m.output_modalities || ['text'] });
            }
            out.sort((a, b) => (b.success || 0) - (a.success || 0) || a.title.toLowerCase().localeCompare(b.title.toLowerCase())); return json({ models: out });
        } catch (e) { return json({ error: String(e.message || e).slice(0, 200), models: [] }); }
    },
    'POST /api/pol_effort_probe': async (u, b) => {
        const cfg = await loadConfig(), key = (cfg.pollinations_api_key || '').trim(), slug = String((b && b.model) || '');
        if (!key) return json({ error: 'Chave do Pollinations nao configurada.' });
        if (!/^[\w.\-/:]+$/.test(slug)) return json({ error: 'Modelo invalido.' });
        const ask = async lv => { const r = await fetchT(POL_API + '/v1/chat/completions', { method: 'POST', headers: bearer(key), body: JSON.stringify({ model: slug, messages: [{ role: 'user', content: '1' }], max_tokens: 1, reasoning_effort: lv }) }, 60000, 'O Pollinations'); return { code: r.status, txt: r.ok ? '' : await r.text().catch(() => '') }; };
        try {
            let a = await ask('lume_probe'); if ([401, 402, 403, 429].includes(a.code)) return json({ error: HTTP_ERR.pol[a.code] || 'Pollinations respondeu ' + a.code });
            const mm = /upported values are:?([^."]*)/.exec(a.txt); let levels = mm ? (mm[1].match(/'(\w+)'/g) || []).map(x => x.replace(/'/g, '')).filter(x => EFFORT_ORDER.includes(x)) : [], source = 'lista do proprio modelo';
            if (!levels.length) { source = 'teste um a um'; for (const lv of EFFORT_ORDER) { const r = await ask(lv); if ([401, 402, 403, 429].includes(r.code)) return json({ error: HTTP_ERR.pol[r.code] || 'Pollinations respondeu ' + r.code }); if (r.code === 200) levels.push(lv); } }
            if (levels.length) await rememberEfforts(slug, levels); return json({ ok: true, levels, source });
        } catch (e) { return json({ error: String(e.message || e).slice(0, 200) }); }
    },
    'GET /api/account_export': async u => {
        const all = u.searchParams.get('all') === '1', list = all ? [''].concat(LS.get('accounts', [])) : [ACCT], out = [];
        for (const n of list) { const pre = n ? 'a:' + n + ':' : ''; out.push({ name: n || 'Aparelho (sem conta)', owner: false, noaccount: !n, history: await kv.rawGet(pre + 'history', {}), state: await kv.rawGet(pre + 'state', {}) }); }
        return json({ format: 'lume-accounts', version: 1, exported: now(), accounts: out });
    },
    'POST /api/account_import': async (u, b) => {
        const data = b && b.data; if (!data || data.format !== 'lume-accounts' || !Array.isArray(data.accounts)) return json({ error: 'Esse arquivo nao e uma exportacao de contas do Lume.' }, 400);
        const done = [], names = LS.get('accounts', []);
        for (const a of data.accounts.slice(0, 50)) {
            if (!a || typeof a !== 'object') continue;
            const n = (a.owner || a.noaccount) ? ACCT : String(a.name || '').trim().replace(/\s+/g, ' ').slice(0, 40); const pre = n ? 'a:' + n + ':' : '';
            const h = mergeHistory(await kv.rawGet(pre + 'history', {}), a.history || {}); await kv.rawSet(pre + 'history', h);
            const old = await kv.rawGet(pre + 'state', {}), st = Object.assign({}, a.state || {}, old), mem = Array.isArray(old.memories) ? old.memories.slice() : [];
            for (const m of (a.state && a.state.memories) || []) if (!mem.some(x => JSON.stringify(x) === JSON.stringify(m))) mem.push(m);
            if (mem.length) st.memories = mem; await kv.rawSet(pre + 'state', st);
            if (n && !names.includes(n)) names.push(n); done.push({ name: n || 'Aparelho (sem conta)', chats: Object.keys(h).length });
        }
        LS.set('accounts', names); return json({ ok: true, imported: done });
    },
    'GET /api/account': () => json({ name: ACCT, accounts: LS.get('accounts', []) }),
    'POST /api/account/login': (u, b) => {
        const n = String((b && b.name) || '').trim().replace(/\s+/g, ' ').slice(0, 40); if (!n) { LS.set('account', ''); ACCT = ''; return json({ ok: true, name: '' }); }
        const list = LS.get('accounts', []); if (!list.includes(n)) list.push(n); LS.set('accounts', list); LS.set('account', n); ACCT = n; return json({ ok: true, name: n });
    },
    'POST /api/account/logout': () => { LS.set('account', ''); ACCT = ''; return json({ ok: true }); },
    'POST /api/account/delete': async (u, b) => {
        const n = String((b && b.name) || ''); if (!n) return json({ error: 'Conta invalida.' }, 400);
        for (const k of ACCT_KEYS) await kv.del('a:' + n + ':' + k);
        LS.set('accounts', LS.get('accounts', []).filter(x => x !== n)); if (ACCT === n) { LS.set('account', ''); ACCT = ''; } return json({ ok: true });
    },
    'GET /api/app_options': () => json({ frozen: true, start_with_terminal: false, terminal_open: false, start_with_windows: false, remote_enabled: false, tray: false, tray_available: false, auto_update_models: false, log_full: false, models_updated_at: 0, model_update: {} }),
    'POST /api/app_options': () => json({ ok: true }),
    'GET /api/usage': async () => json((await loadConfig()).usage || {}),
    'GET /api/check_pending': () => json({ cmd: '' }),
    'POST /api/resolve_pending': () => json({ ok: true }),
    'GET /api/metrics': () => json({ vram_used: null, vram_total: null, vram: null, gpu: null, vram_warn: '', generation_active: false, alert: { id: 0 } }),
    'GET /api/server_info': () => json({ remote_enabled: false, allow_remote_code: false, password: '', password_required: false, internet_password_required: false, owner_link_enabled: false, owner_code: '', port: 0, configured_port: 0, listening: '', addresses: [], https_addresses: [], devices: [] }),
    'GET /api/update_check': () => json({ available: false, error: 'No iPhone o Lume se atualiza sozinho ao abrir (avisa se nao conseguir).' }),
    'GET /api/tunnel': () => json({ running: false, url: '', error: '', tool: '', cloudflared: false, tailscale: {}, port: 0 }),
    'GET /api/history': async () => json(await kv.get('history', {})),
    'POST /api/history': async (u, b) => { await kv.set('history', b || {}); schedulePcSync(); return json({ ok: true }); },
    'GET /api/state': async () => json(await kv.get('state', {})),
    'POST /api/state': async (u, b) => { await kv.set('state', b || {}); schedulePcSync(); return json({ ok: true }); },
    'GET /api/custom_themes': async () => { const t = await kv.get('themes', {}); return json(Object.keys(t).sort().map(n => Object.assign({}, t[n], { name: n }))); },
    'POST /api/custom_theme': async (u, b) => { const t = await kv.get('themes', {}), n = slug(b && b.name); t[n] = (b && b.theme) || {}; await kv.set('themes', t); return json({ ok: true, name: n, path: n }); },
    'POST /api/custom_theme_delete': async (u, b) => { const t = await kv.get('themes', {}); delete t[slug(b && b.name)]; await kv.set('themes', t); return json({ ok: true }); },
    'GET /api/stats': async u => json(await buildStats(Math.max(1, Math.min(365, parseInt(u.searchParams.get('days') || '30', 10) || 30)))),
    'POST /api/stats_clear': async () => { await kv.set('stats', { events: [] }); return json({ ok: true }); },
    'GET /api/config_status': async () => {
        const c = await loadConfig();
        return json({ groq_key_saved: !!c.groq_api_key, openrouter_key_saved: !!c.openrouter_api_key, cloudflare_saved: false, pollinations_saved: !!c.pollinations_api_key, tomdacat_saved: !!c.tomdacat_api_key, vercel_saved: !!c.vercel_api_key, llm7_saved: !!c.llm7_api_key, x_saved: Object.fromEntries(Object.entries(XPROV).map(([p, v]) => [p, !!c[v[0]]])), aichixia_saved: !!c.aichixia_api_key, aihubmix_saved: !!c.aihubmix_api_key, literouter_saved: !!c.literouter_api_key,
            exa_key_saved: !!c.exa_api_key, search_provider: c.search_provider, exa_type: c.exa_type, search_results: c.search_results, search_daily_limit: c.search_daily_limit, exa_today: 0, auto_allow: false, workdir: '', default_workdir: '', ollama_url: c.ollama_url || '' });
    },
    'POST /api/save_config': async (u, b) => {
        const c = Object.assign({}, await loadConfig()); b = b || {};
        for (const k of SECRET_KEYS) if (k in b) c[k] = String(b[k]).trim();
        for (const k of ['search_provider', 'exa_type', 'search_results', 'search_daily_limit', 'ollama_url', 'pc_url']) if (k in b) c[k] = (k === 'ollama_url' || k === 'pc_url') ? String(b[k]).trim() : b[k];
        await saveConfig(c); Object.keys(cache).forEach(k => { if (cache[k].v !== undefined) cache[k].v = null; }); cache.pol.cat = null; return json({ ok: true });
    },
    'POST /api/extract_text': async (u, b) => {
        try {
            const bin = atob((b && b.b64) || ''), bytes = Uint8Array.from(bin, ch => ch.charCodeAt(0)), head = bin.slice(0, 8);
            if (head.startsWith('\x89PNG') || head.startsWith('\xff\xd8') || head.startsWith('GIF8')) return json({ kind: 'image', ext: head.startsWith('\x89PNG') ? '.png' : head.startsWith('GIF8') ? '.gif' : '.jpg' });
            if (head.startsWith('%PDF') || head.startsWith('PK')) return json({ error: 'No iPhone ainda so leio arquivos de texto (PDF e Word precisam do PC).' }, 400);
            let text = new TextDecoder('utf-8', { fatal: false }).decode(bytes), truncated = false; if (text.length > 400000) { text = text.slice(0, 400000); truncated = true; }
            return json({ text, truncated, chars: text.length, pages: null, kind: 'text', ext: '.txt' });
        } catch (e) { return json({ error: String(e.message || e) }, 400); }
    },
    'POST /api/chat': (u, b) => handleChat(b || {}),
    'POST /api/stop': (u, b) => { const rid = String((b && b.rid) || ''); if (rid) { stops[rid] && stops[rid].abort(); } else Object.values(stops).forEach(c => c.abort()); return json({ ok: true }); },
    'GET /api/models_status': async () => {
        const cfg = await loadConfig(), base = (cfg.ollama_url || '').trim().replace(/\/+$/, '');
        if (!base) return json({ running: false, loaded: [], vram_total: null, vram_used: null, installed: null, installed_sizes: {} });
        try {
            const tags = (await getJson(base + '/api/tags', {}, 4000)).models || [], ps = await getJson(base + '/api/ps', {}, 4000).then(j => j.models || []).catch(() => []);
            return json({ running: true, loaded: ps.map(m => ({ name: m.name, size: m.size || 0, size_vram: m.size_vram || 0 })), vram_total: null, vram_used: null, installed: tags.map(m => m.name), installed_sizes: Object.fromEntries(tags.map(m => [m.name, m.size || 0])) });
        } catch (e) { return json({ running: false, loaded: [], vram_total: null, vram_used: null, installed: null, installed_sizes: {} }); }
    },
    'GET /api/model_info': async u => {
        const cfg = await loadConfig(), base = (cfg.ollama_url || '').trim().replace(/\/+$/, ''), name = u.searchParams.get('name') || '';
        if (!base || !/^[\w.:\-/]+$/.test(name)) return json({});
        try { const r = await fetchT(base + '/api/show', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model: name }) }, 5000); return json(await r.json()); } catch (e) { return json({}); }
    },
    'GET /api/openrouter_models': async () => {
        const cfg = await loadConfig(); if (!cfg.openrouter_api_key) return json({ key_saved: false, models: [] });
        try { return json({ key_saved: true, models: await openrouterModels() }); } catch (e) { return json({ key_saved: true, models: [], error: String(e.message || e).slice(0, 200) }); }
    },
    'GET /api/pollinations_models': listModels('pollinations_api_key', pollinationsModels),
    'GET /api/groq_models': listModels('groq_api_key', groqModels),
    'GET /api/vercel_models': listModels('vercel_api_key', vercelModels),
    'GET /api/llm7_models': listModels('llm7_api_key', llm7Models),
    'GET /api/tomdacat_models': listModels('tomdacat_api_key', tomdacatModels),
        'GET /api/tokenreply_usage': async () => {
        const key = ((await loadConfig()).tokenreply_api_key || '').trim(); if (!key) return json({ error: 'sem chave' }, 400);
        try { const j = ((await getJson(TK_URL.replace(/\/v1$/, '') + '/api/usage/token/', { Authorization: 'Bearer ' + key }, 15000, 'O TokenReply')) || {}).data || {}; return json({ available: j.total_available_usd, granted: j.total_granted_usd, used: j.total_used_usd }); }
        catch (e) { return json({ error: String(e.message || e).slice(0, 160) }, 502); }
    },
    'GET /api/voidai_credits': async () => {
        const key = ((await loadConfig()).voidai_api_key || '').trim(); if (!key) return json({ error: 'sem chave' }, 400);
        try { const j = await getJson(VD_URL + '/credits', { Authorization: 'Bearer ' + key }, 15000, 'O VoidAI'); return json({ credits: j.current_credits, limit: j.daily_limit, plan: j.plan, used: j.credits_used }); }
        catch (e) { return json({ error: String(e.message || e).slice(0, 160) }, 502); }
    },
    'GET /api/extra_models': async () => {
        const cfg = await loadConfig(), out = {}, health = await kv.rawGet('health', {});
        for (const p of Object.keys(XPROV)) {
            if (!cfg[XFIELD[p]]) { out[p] = { saved: false, models: [] }; continue; }
            try { const list = await extraRaw(p, cfg); out[p] = { saved: true, models: SHOW_ALL.has(p) ? list : list.filter(m => !health[p + ':' + m.id] || health[p + ':' + m.id].ok !== false) }; }
            catch (e) { out[p] = { saved: true, models: [], error: String(e.message || e).slice(0, 200) }; }
        }
        return json(out);
    },
    'GET /api/cloudflare_models': () => json({ saved: false, models: [] }),
    'GET /api/cloudflare_usage': () => json({}),
    'GET /api/pollinations_usage': async () => {
        const key = (await loadConfig()).pollinations_api_key; if (!key) return json({ error: 'sem chave' }, 400);
        try { return json({ balance: (await getJson(POL_API + '/account/balance', bearer(key), 15000)).balance }); } catch (e) { return json({ error: String(e.message || e).slice(0, 160) }, 502); }
    },
    'POST /api/open_url': (u, b) => { if (b && /^https?:\/\//.test(b.url || '')) window.open(b.url, '_blank'); return json({ ok: true }); },
};

window.fetch = async function (input, init) {
    let u; try { u = new URL(typeof input === 'string' ? input : input.url, location.href); } catch (e) { return realFetch(input, init); }
    if (!u.pathname.startsWith('/api/')) return realFetch(input, init);
    const method = String((init && init.method) || (typeof input !== 'string' && input.method) || 'GET').toUpperCase(); let body = null;
    if (method === 'POST') { try { body = JSON.parse((init && init.body) || (typeof input !== 'string' && await input.text()) || '{}'); } catch (e) { body = {}; } }
    const h = ROUTES[method + ' ' + u.pathname];
    try { return h ? await h(u, body) : NOPE(); } catch (e) { return json({ error: String(e && e.message || e).slice(0, 200) }, 500); }
};
window.__lumeBackendRoutes = ROUTES;

// copia/sincronizacao da conta com o PC (opcional). O aparelho tem um id e um segredo proprios; o PC so devolve conversas, memorias e chaves se voce marcar este aparelho como confiavel la
let pcTimer = null;
const setPcStatus = t => { LS.set('pc_status', t); const el = typeof document !== 'undefined' && document.getElementById('pc-sync-status'); if (el) el.textContent = t; };
function deviceId() {
    let d = LS.get('device', null);
    if (!d || !d.id || !d.secret) { const hex = n => Array.from(crypto.getRandomValues(new Uint8Array(n)), x => x.toString(16).padStart(2, '0')).join(''); d = { id: hex(8), secret: hex(24) }; LS.set('device', d); }
    return d;
}
const mergeHistory = (a, b) => { const out = Object.assign({}, a || {}); for (const [id, chat] of Object.entries(b || {})) { const old = out[id]; if (!old || ((chat && chat.messages) || []).length > ((old && old.messages) || []).length) out[id] = chat; } return out; };
async function pcPull(base) {
    const dv = deviceId();
    const r = await fetchT(base + '/api/device_pull', { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ device_id: dv.id, secret: dv.secret, name: ACCT, device: 'iPhone' }) }, 20000, 'O PC');
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { setPcStatus(j.error === 'not_trusted' ? 'copiado ✓ (confie neste aparelho no PC para receber as chaves)' : 'o PC recusou (' + (j.error || r.status) + ')'); return false; }
    let changed = false;
    const lh = await kv.get('history', {}), mh = mergeHistory(lh, j.history); if (JSON.stringify(mh) !== JSON.stringify(lh)) { await kv.set('history', mh); changed = true; }
    const ls = await kv.get('state', {}), ms = Object.assign({}, ls), mem = Array.isArray(ls.memories) ? ls.memories.slice() : [];
    for (const m of (j.state && j.state.memories) || []) if (!mem.some(x => JSON.stringify(x) === JSON.stringify(m))) mem.push(m);
    if (mem.length !== (ls.memories || []).length) { ms.memories = mem; await kv.set('state', ms); changed = true; }
    const cfg = Object.assign({}, await loadConfig()); let keys = 0;
    for (const [k, v] of Object.entries(j.keys || {})) if (!cfg[k] && v) { cfg[k] = v; keys++; }
    if (keys) { await saveConfig(cfg); changed = true; }
    setPcStatus('sincronizado ✓' + (keys ? ' (' + keys + ' chave(s) recebida(s))' : ''));
    if (changed && typeof location !== 'undefined' && typeof document !== 'undefined' && document.getElementById('chat')) setTimeout(() => location.reload(), 600);   // a tela le de novo as conversas/chaves novas
    return changed;
}
async function pcSync() {
    const cfg = await loadConfig(), base = (cfg.pc_url || '').trim().replace(/\/+$/, '');
    if (!base) { setPcStatus('desligado'); return; }
    if (!ACCT) { setPcStatus('entre numa conta'); return; }
    try {
        const dv = deviceId();
        const r = await fetchT(base + '/api/device_sync', { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: JSON.stringify({ name: ACCT, device: 'iPhone', device_id: dv.id, secret: dv.secret, history: await kv.get('history', {}), state: await kv.get('state', {}) }) }, 20000, 'O PC');
        const j = await r.json().catch(() => ({}));
        if (!r.ok) { setPcStatus(j.error === 'remote_off' ? 'ligue "acessar de outros aparelhos" no PC' : j.error === 'taken' ? 'nome ja usado no PC' : j.error === 'owner_untrusted' ? 'confie neste aparelho no PC (Servidor > Aparelhos confiaveis) para sincronizar a conta do dono' : j.error === 'device_secret' ? 'o PC nao reconhece este aparelho (remova-o la)' : j.error === 'forbidden' ? 'o PC so aceita a rede de casa (este endereco veio de fora)' : 'o PC recusou (' + (j.error || r.status) + ')'); return; }
        if (j.trusted) await pcPull(base); else setPcStatus('copiado ✓ (confie neste aparelho no PC para receber as chaves)');
    } catch (e) { setPcStatus('PC fora do ar'); }
}
function schedulePcSync() { clearTimeout(pcTimer); pcTimer = setTimeout(pcSync, 4000); }

// avisos da atualizacao automatica (o app nativo chama window.lumeUpdateReady / window.lumeUpdateFailed)
function updateBanner(text, label, onClick, warn) {
    if (typeof document === 'undefined') return;
    const old = document.getElementById('upd-banner'); if (old) old.remove();
    const b = document.createElement('div'); b.id = 'upd-banner';
    b.style.cssText = 'position:fixed;left:10px;right:10px;top:calc(8px + env(safe-area-inset-top));z-index:9000;display:flex;align-items:center;gap:10px;padding:10px 14px;border-radius:14px;font-size:14px;line-height:1.35;color:#fff;box-shadow:0 8px 28px rgba(0,0,0,.5);background:' + (warn ? '#a15c00' : '#1f7a4d');
    const t = document.createElement('span'); t.style.flex = '1'; t.textContent = text; b.appendChild(t);
    const btn = document.createElement('button'); btn.textContent = label; btn.style.cssText = 'border:0;border-radius:999px;padding:6px 14px;font-weight:600;background:rgba(255,255,255,.22);color:#fff';
    btn.addEventListener('click', () => { b.remove(); if (onClick) onClick(); }); b.appendChild(btn);
    document.body.appendChild(b);
}
window.lumeUpdateReady = v => updateBanner('Atualização do Lume pronta' + (v ? ' (' + v + ')' : '') + '.', 'Reiniciar', () => { try { window.webkit.messageHandlers.lume.postMessage('reload'); } catch (e) { location.reload(); } }, false);
window.lumeUpdateFailed = msg => updateBanner(msg, 'Fechar', null, true);

// diagnostico do armazenamento: mostra se o aparelho esta guardando mesmo e quantas vezes o app abriu
async function storageReport() {
    const el = document.getElementById('storage-row'); if (!el) return;
    const pr = await kv.probe(), cfg = await loadConfig(), hist = await kv.get('history', {}), keys = Object.keys(cfg).filter(k => /_api_key$|_token$/.test(k) && cfg[k]).length;
    const boots = LS.get('boots', 0), ibo = await kv.rawGet('boots', 0);
    el.textContent = 'Armazenamento: IndexedDB ' + (pr.idb ? '✓' : '✗ (' + kv.state + ')') + ' · localStorage ' + (pr.ls ? '✓' : '✗') + ' · aberturas ' + boots + '/' + ibo + ' · conversas ' + Object.keys(hist).length + ' · chaves ' + keys + (ACCT ? ' · conta ' + ACCT : '');
}
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', async () => {
    LS.set('boots', (LS.get('boots', 0) || 0) + 1); await kv.rawSet('boots', ((await kv.rawGet('boots', 0)) || 0) + 1);
    const row = document.getElementById('acct-row'); if (!row) return;
    const el = document.createElement('div'); el.id = 'storage-row'; el.style.cssText = 'margin:0 0 10px;padding:8px 14px;border-radius:12px;background:rgba(128,128,128,0.10);font-size:.78em;color:var(--text-muted);line-height:1.4'; row.after(el);
    storageReport(); setInterval(storageReport, 6000);
});

// o iPhone nao tem terminal, Windows, GPU nem pasta de trabalho: some o que so existe no PC
function iosTrim() {
    const gen = document.getElementById('set-general'); if (!gen) return;
    const hideTitles = ['Code', 'Overlay de desempenho', 'Aplicativo', 'Modelos do Ollama', 'Atualizações'];
    let hide = false;
    [...gen.children].forEach(el => { if (el.classList.contains('section-title')) hide = hideTitles.includes(el.textContent.trim()); if (hide) el.classList.add('ios-hide'); });
    ['opt-winbtn', 'winbtn-custom', 'opt-autostop', 'opt-hidevram', 'opt-legacy'].forEach(id => { const e = document.getElementById(id); const w = e && e.closest('.form-group, .toggle-container, .srv-actions'); if (w) w.classList.add('ios-hide'); });
    ['set-tab-server', 'set-server'].forEach(id => { const e = document.getElementById(id); if (e) e.classList.add('ios-hide'); });
    const tabs = document.querySelector('.set-tabs'); if (tabs) tabs.classList.add('ios-hide');
}
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', iosTrim);

// "Logar com o Ollama": a chave fica na conta do Lume (ou no aparelho, sem conta)
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', () => {
    const box = document.getElementById('ollama-login-box'); if (!box) return; box.style.display = '';
    const inp = document.getElementById('ollama-key-input'), st = document.getElementById('ollama-login-status'), btn = document.getElementById('ollama-login-btn');
    const show = async () => { const k = String(await kv.get('ollama_key', '') || ''); st.textContent = k ? 'logado ✓' + (ACCT ? ' (' + ACCT + ')' : '') : 'não logado'; inp.placeholder = k ? '••••••••• (colar outra troca a chave)' : 'cole a chave do Ollama aqui'; };
    show();
    btn.addEventListener('click', () => window.open('https://ollama.com/settings/keys', '_blank'));
    inp.addEventListener('change', async () => { const v = inp.value.trim(); if (v) await kv.set('ollama_key', v); inp.value = ''; show(); });
});

// campo "Ollama no PC" (Configuracoes): so existe no iPhone e grava direto
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', () => {
    const box = document.getElementById('ollama-url-box'); if (!box) return; box.style.display = '';
    const inp = document.getElementById('ollama-url-input'); loadConfig().then(c => { inp.value = c.ollama_url || ''; });
    inp.addEventListener('change', async () => { const c = Object.assign({}, await loadConfig()); c.ollama_url = inp.value.trim(); await saveConfig(c); });
});
if (typeof document !== 'undefined') document.addEventListener('DOMContentLoaded', () => {
    const box = document.getElementById('pc-url-box'); if (!box) return; box.style.display = '';
    const inp = document.getElementById('pc-url-input'), st = document.getElementById('pc-sync-status'); st.textContent = LS.get('pc_status', 'desligado'); loadConfig().then(c => { inp.value = c.pc_url || ''; });
    inp.addEventListener('change', async () => { const c = Object.assign({}, await loadConfig()); c.pc_url = inp.value.trim(); await saveConfig(c); pcSync(); });
    setTimeout(pcSync, 3000);   // ao abrir o app (e depois a cada conversa salva)
});
})();
