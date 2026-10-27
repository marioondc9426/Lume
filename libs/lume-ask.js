/* Perguntar a um modelo de dentro de um painel (mascote, comparador de modelos, jogos...): usa o mesmo /api/chat do chat, sem mexer na conversa.
     const texto = await lumeAsk({ model: 'pol:openai/gpt-5.4-nano', system: '...', user: '...' });          // devolve o texto inteiro
     await lumeAsk({ model, messages, onText: t => ..., signal });                                            // com o texto chegando aos poucos
   O "model" pode ser o id ou o registro do modelo (MODELS). Se o servidor responder "[Erro: ...]" o lumeAsk lanca um Error com a mensagem. */
(() => {
    const avail = () => (typeof MODELS !== 'undefined' ? MODELS : []).filter(m => { try { return isAvail(m); } catch (e) { return false; } });
    window.lumeModels = avail;
    window.lumeModelById = id => avail().find(m => m.id === id) || null;
    window.lumeAsk = async function (o) {
        const m = typeof o.model === 'string' ? window.lumeModelById(o.model) : o.model; if (!m) throw new Error('Modelo indisponível.');
        const messages = o.messages || [{ role: 'system', content: o.system || '' }, { role: 'user', content: o.user || '' }], rid = 'ask' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5);
        const ctl = new AbortController(), to = setTimeout(() => ctl.abort(), o.timeoutMs || 120000); if (o.signal) o.signal.addEventListener('abort', () => ctl.abort());
        try {
            const r = await fetch(API + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: ctl.signal, body: JSON.stringify({ model: m.id, rid, messages, stream: true, think: false, effort: m.pol && m.effort ? 'none' : undefined, search_web: false, agent: false, lang: typeof curLang === 'function' ? curLang() : 'pt', num_ctx: m.cloud ? undefined : 4096 }) });
            if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
            const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '', out = '';
            for (;;) {
                const { value, done } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true });
                let nl; while ((nl = buf.indexOf('\n')) >= 0) {
                    const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue;
                    try { const j = JSON.parse(line); if (j.message && j.message.content) { out += j.message.content; if (o.onText) o.onText(out); } } catch (e) { /* linha incompleta */ }
                }
            }
            const err = out.match(/\[(?:Erro|Error):\s*([^\]]*)\]/); if (err && out.replace(err[0], '').trim().length < 3) throw new Error(err[1].trim() || 'erro');
            return out.replace(/\n?\[(?:Erro|Error):[^\]]*\]\s*$/, '').trim();
        } finally { clearTimeout(to); }
    };
})();
