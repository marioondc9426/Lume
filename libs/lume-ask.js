/* Perguntar a um modelo de dentro de um painel (mascote, comparador de modelos, jogos...): usa o mesmo /api/chat do chat, sem mexer na conversa.
     const texto = await lumeAsk({ model: 'pol:openai/gpt-5.4-nano', system: '...', user: '...' });          // devolve o texto inteiro
     await lumeAsk({ model, messages, onText: t => ..., signal });                                            // com o texto chegando aos poucos
   O "model" pode ser o id ou o registro do modelo (MODELS). Se o servidor responder "[Erro: ...]" o lumeAsk lanca um Error com a mensagem. */
(() => {
    const avail = () => (typeof MODELS !== 'undefined' ? MODELS : []).filter(m => { try { return isAvail(m); } catch (e) { return false; } });
    window.lumeModels = avail;
    window.lumeModelById = id => avail().find(m => m.id === id) || null;
    // ---- pollen: quanto uma resposta custou (tokens x preco do modelo, o mesmo calculo do chat) e o saldo da conta
    window.lumePollenOf = (m, s) => (m && m.pol && !m.free && s) ? ((s.prompt_tokens || 0) * (m.priceIn || 0) + (s.tokens || 0) * (m.priceOut || 0)) / 1e6 : 0;
    let balAt = 0, balV = null;
    window.lumePollenBalance = async force => { if (!force && Date.now() - balAt < 4000) return balV; balAt = Date.now(); try { const d = await (await fetch(API + '/api/pollinations_usage')).json(); if (d && d.balance != null) balV = d.balance; } catch (e) { /* sem saldo agora */ } return balV; };
    window.lumeCostBar = function () {   // linha "saldo / gasto neste jogo / ultimo lance" para os xadrezes
        const el = document.createElement('div'), T = x => (typeof tr === 'function' ? tr(x) : x), s = { total: 0, by: {}, last: 0, bal: null }, fmt = n => (n >= 0.01 ? n.toFixed(4) : n.toFixed(6));
        el.style.cssText = 'font-size:.8em;padding:7px 10px;border-radius:12px;background:rgba(128,128,128,.10);color:var(--text-muted);line-height:1.5;word-break:break-word';
        function render() {
            const parts = []; if (s.bal != null) parts.push('🌸 ' + T('saldo') + ' ' + s.bal.toFixed(3) + ' pollen'); parts.push(T('gasto neste jogo') + ': ' + fmt(s.total) + (s.last ? ' (' + T('último lance') + ' +' + fmt(s.last) + ')' : ''));
            const sides = Object.entries(s.by).filter(([, v]) => v > 0).map(([k, v]) => k + ' ' + fmt(v)); if (sides.length > 1) parts.push(sides.join(' · ')); el.textContent = parts.join('  ·  ');
        }
        const api = { el, render, get total() { return s.total; }, async refresh() { s.bal = await window.lumePollenBalance(true); render(); }, spend(key, pollen) { s.last = pollen || 0; s.total += s.last; s.by[key] = (s.by[key] || 0) + s.last; render(); api.refresh(); }, reset() { s.total = 0; s.by = {}; s.last = 0; render(); } };
        render(); api.refresh(); return api;
    };
    window.lumeAsk = async function (o) {
        const m = typeof o.model === 'string' ? window.lumeModelById(o.model) : o.model; if (!m) throw new Error('Modelo indisponível.');
        const messages = o.messages || [{ role: 'system', content: o.system || '' }, { role: 'user', content: o.user || '' }], rid = 'ask' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
        const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), o.timeoutMs || 120000); if (o.signal) o.signal.addEventListener('abort', () => ctl.abort());
        try {
            const r = await fetch(API + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal, body: JSON.stringify({ model: m.id, rid, messages, stream: true, think: false, effort: m.pol && m.effort ? 'none' : undefined, search_web: false, agent: false, lang: typeof curLang === 'function' ? curLang() : 'pt', num_ctx: m.cloud ? undefined : 4096 }) });
            if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
            const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '', out = '', usage = null;
            for (;;) {
                const { value, done } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true });
                let nl; while ((nl = buf.indexOf('\n')) >= 0) {
                    const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
                    try { const j = JSON.parse(line); if (j.stats) usage = j.stats; if (j.message && j.message.content) { out += j.message.content; if (o.onText) o.onText(out); } } catch (e) { /* linha incompleta */ }
                }
            }
            const pollen = window.lumePollenOf(m, usage); if (o.onUsage) { try { o.onUsage({ pollen, tokens: (usage && usage.tokens) || 0, prompt: (usage && usage.prompt_tokens) || 0, model: m }); } catch (e) { /* ok */ } }
            if (o.track && pollen && window.lumeSpend) { try { lumeSpend.add(m, pollen, 0, 0); } catch (e) { /* ok */ } }   // jogos entram no caderno de gastos
            const err = out.match(/\[(?:Erro|Error):\s*([^\]]*)\]/); if (err && out.replace(err[0], '').trim().length < 3) throw new Error(err[1].trim() || 'erro');
            return out.replace(/\n?\[(?:Erro|Error):[^\]]*\]\s*$/, '').trim();
        } finally { clearTimeout(to); }
    };
})();
