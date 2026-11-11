/* Lume Auto: o roteador de modelos. Escolha "Lume Auto" no seletor e, a cada pedido, ele:
     1. le o pedido (codigo? conta? texto curto? imagem? arquivo grande?) e separa os modelos mais apropriados (nota de inteligencia do Gratisfy + afinidade com o tipo de pedido);
     2. dos melhores para ESSE pedido, filtra os mais estaveis (historico de acertos/falhas e quedas recentes, medido aqui) e rapidos (tempo medido ou estimado) e usa o primeiro;
     3. se o modelo falhar (erro, sem resposta), o proprio app passa para o proximo da lista sem voce fazer nada (o index.html usa a lista no mesmo lugar onde ja trocava de provedor).
   TUDO que ele faz vai para o log (terminal do Lume + arquivo router.log; no iPhone, no aparelho): pedido, candidatos com as notas, quem foi cortado e por que, escolha, sucesso, falha e troca.
   Configuracoes e o visualizador do log: Configuracoes > Chat > "Lume Auto…" (ou clique no seletor de modelos e veja o log por la).
     lumeRouter.route({ tab, text, hasImages, hasFiles, chatId, exclude })  -> { list, category, why }   (sincrono; a 1a posicao e a escolha)
     lumeRouter.report(model, ok, { ms, why, auto })                         -> alimenta o historico de estabilidade (todo uso de qualquer modelo conta)
     lumeRouter.log(evento, texto)  /  lumeRouter.openLog()  /  lumeRouter.openSettings() */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const AUTO_ID = 'lume:auto', CFG_KEY = 'lume_router_cfg', STAT_KEY = 'lume_router_stats';
    const DEF = { paid: false, local: true, registra: false, balance: 50, k: 8, tries: 4, minStab: 0.3, timeout: 45, excerpt: false, autoSwitch: false };   // balance: 0 = velocidade ... 100 = qualidade
    const rd = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || 'null') || d; } catch (e) { return d; } };
    const wr = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sem armazenamento */ } };
    let cfg = Object.assign({}, DEF, rd(CFG_KEY, {}));
    const save = () => wr(CFG_KEY, cfg);

    // ---------------------------------------------------------------- log (tudo que o roteador faz)
    let queue = [], timer = 0; const ring = [];
    function flush() { timer = 0; if (!queue.length) return; const lines = queue; queue = []; try { fetch(API + '/api/router_log', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lines }) }).catch(() => {}); } catch (e) { /* sem servidor */ } }
    function log(ev, msg) { const l = { t: Date.now(), ev, msg: String(msg) }; ring.push(l); if (ring.length > 300) ring.shift(); queue.push(l); if (!timer) timer = setTimeout(flush, 250); }

    // ---------------------------------------------------------------- historico de estabilidade (por modelo, neste aparelho)
    const stats = () => rd(STAT_KEY, {});
    function report(m, ok, o) {
        if (!m || !m.id || m.auto) return; o = o || {}; const st = stats(), e = st[m.id] || (st[m.id] = { ok: 0, fail: 0, streak: 0, ms: 0 }), now = Date.now();
        if (ok) { e.ok++; e.streak = 0; e.lastOk = now; if (o.ms) e.ms = e.ms ? Math.round(e.ms * 0.7 + o.ms * 0.3) : o.ms; }
        else { e.fail++; e.streak++; e.lastFail = now; e.why = String(o.why || '').slice(0, 120); }
        if (e.ok + e.fail > 60) { e.ok = Math.round(e.ok * 0.5); e.fail = Math.round(e.fail * 0.5); }   // o passado vale cada vez menos
        const ids = Object.keys(st); if (ids.length > 400) delete st[ids[0]];
        wr(STAT_KEY, st);
        if (o.auto !== false) log(ok ? 'sucesso' : 'falha', (m.label || m.id) + (ok ? ' respondeu em ' + ((o.ms || 0) / 1000).toFixed(1) + ' s' : ' falhou: ' + (o.why || '?')) + ' · histórico ' + e.ok + ' ok / ' + e.fail + ' falhas' + (!ok && e.streak >= 2 ? ' (' + e.streak + ' falhas seguidas: fica de molho por 10 min)' : ''));
    }
    function stability(m, st) {   // 0..1: taxa de acerto com um "prior" (2 ok / 1 falha), cai depois de uma falha recente
        const e = (st || stats())[m.id]; if (!e) return { v: 0.67, note: 'sem histórico' }; const now = Date.now();
        let v = (e.ok + 2) / (e.ok + e.fail + 3), note = e.ok + ' ok / ' + e.fail + ' falhas';
        if (e.lastFail && now - e.lastFail < 600000) { v *= e.streak >= 2 ? 0 : 0.45; note += ', falhou há ' + Math.round((now - e.lastFail) / 60000) + ' min'; }
        else if (e.lastFail && now - e.lastFail < 3600000) v *= 0.8;
        return { v: Math.max(0, v), note, cool: e.streak >= 2 && now - e.lastFail < 600000 };
    }

    // ---------------------------------------------------------------- entender o pedido
    const RX = {
        code: /```|\b(?:fun[cç][aã]o|function|class|def|import|c[oó]digo|code|bug|erro|exception|stack ?trace|compil|regex|sql|api|script|programa|refator|python|javascript|typescript|java|c#|c\+\+|html|css|react|node|git|docker)\b|\.(?:py|js|ts|cs|cpp|java|html|css|json|yml|sh|ps1)\b/i,
        math: /\d\s*[+\-*/^=]\s*\d|\b(?:equa[cç][aã]o|integral|derivad|probabilidade|calcul|prove|teorema|matem[aá]tica|geometria|[aá]lgebra|estat[ií]stica|l[oó]gica|puzzle|enigma|quebra-cabe)/i,
        creative: /\b(?:escreva|crie|invente|imagine|conte)\b[^.\n]{0,60}\b(?:hist[oó]ria|poema|poesia|m[uú]sica|letra|roteiro|conto|piada|ideia|nome)/i,
        translate: /\b(?:traduz|translate|tradu[cç][aã]o|em ingl[eê]s|em espanhol|em franc[eê]s|em portugu[eê]s)\b/i,
        hard: /\b(?:otimiz|arquitetura|passo a passo|em detalhes|detalhad|compare|analise|an[aá]lise|explique por que|planeje|projete|refatore|prova|demonstre)\b/i,
    };
    function classify(o) {
        const text = String(o.text || ''), len = text.length, why = [];
        let cat = 'geral';
        if (o.tab === 'code' || RX.code.test(text)) { cat = 'codigo'; why.push(o.tab === 'code' ? 'aba Code' : 'parece código'); }
        else if (RX.math.test(text)) { cat = 'raciocinio'; why.push('conta/lógica'); }
        else if (RX.creative.test(text)) { cat = 'criativo'; why.push('texto criativo'); }
        else if (RX.translate.test(text)) { cat = 'traducao'; why.push('tradução'); }
        else if (len < 90 && !o.hasImages && !o.hasFiles) { cat = 'rapido'; why.push('pedido curto'); }
        const hard = len > 500 || RX.hard.test(text) || (cat === 'codigo' && len > 250);
        if (hard && cat !== 'rapido') why.push('pedido complexo');
        if (o.hasImages) why.push('tem imagem (precisa de visão)'); if (o.hasFiles) why.push('tem arquivo'); if (len > 6000) why.push('texto longo (~' + Math.round(len / 3) + ' tokens)');
        return { cat, hard, len, why };
    }
    // pesos: [qualidade, velocidade] da etapa 1 (a etapa 2 usa estabilidade + velocidade)
    const W = { codigo: 0.7, raciocinio: 0.75, criativo: 0.55, traducao: 0.4, geral: 0.5, rapido: 0.2 };
    const AFF = {
        codigo: /coder|code|devstral|codestral|deepseek|claude|gpt|kimi|glm|qwen|gemini|minimax/i,
        raciocinio: /deepseek|qwen|gpt|claude|gemini|kimi|glm|think|reason|o\d\b/i,
        criativo: /claude|kimi|gemma|llama|mistral|gpt|gemini|glm/i,
        traducao: /gemma|gpt|claude|gemini|qwen|mistral|llama/i,
    };

    // ---------------------------------------------------------------- escolher
    const isLocal = m => { try { return !!isLocalM(m); } catch (e) { return !(m.cloud || m.pol || m.or || m.cf || m.groq || m.tdc || m.vc || m.l7 || m.x); } };
    const nm = m => m.label || m.id;
    function route(o) {
        o = o || {}; const t0 = performance.now(), tab = o.tab === 'code' ? 'code' : 'chat', cl = classify(Object.assign({}, o, { tab }));
        const scoresOk = window.lumeScores && lumeScores.ready; if (window.lumeScores && !scoresOk) lumeScores.load();   // notas de inteligencia: se ainda nao chegaram, esta vez vai sem elas (e chegam para a proxima)
        const all = (typeof MODELS !== 'undefined' ? MODELS : []).filter(m => !m.auto && !m.phone && m.tabs && m.tabs.includes(tab)); let avail = [];
        all.forEach(m => { try { if (isAvail(m)) avail.push(m); } catch (e) { /* ignora */ } });
        log('pedido', 'aba ' + tab + ' · tipo ' + cl.cat + (cl.hard ? ' (complexo)' : '') + ' · ' + cl.len + ' caracteres' + (cl.why.length ? ' · ' + cl.why.join('; ') : '') + (cfg.excerpt ? ' · "' + String(o.text || '').replace(/\s+/g, ' ').slice(0, 60) + '"' : '') + ' · ' + avail.length + ' modelos disponíveis nesta aba' + (scoresOk ? '' : ' · notas de inteligência ainda não carregadas'));
        const cut = {}, drop = (m, why) => { (cut[why] = cut[why] || []).push(nm(m)); };
        const st = stats(), need = cl.len / 3, keep = [];
        avail.forEach(m => {
            if (o.exclude && o.exclude.has(m.id)) return drop(m, 'já tentado neste pedido');
            if (!cfg.paid && window.lumeScores && lumeScores.paid(m)) return drop(m, 'pago');
            if (!cfg.local && isLocal(m)) return drop(m, 'local (desligado nas configurações)');
            if (isLocal(m) && m.heavy) return drop(m, 'local pesado');
            if (!cfg.registra && /registra|grava as conversas|logs? (?:the )?(?:conversations|prompts)/i.test(m.warn || '')) return drop(m, 'registra as conversas (privacidade)');
            if (o.hasImages && !m.vision) return drop(m, 'sem visão (o pedido tem imagem)');
            if (m.ctx && need > m.ctx * 0.8) return drop(m, 'contexto pequeno demais');
            keep.push(m);
        });
        Object.keys(cut).forEach(k => log('corte', k + ': ' + cut[k].length + ' (' + cut[k].slice(0, 6).join(', ') + (cut[k].length > 6 ? '…' : '') + ')'));
        if (!keep.length) { log('sem-modelo', 'nenhum modelo passou pelos filtros'); return { list: [], category: cl.cat, why: cl.why }; }
        // etapa 1: apropriados para ESTE pedido (qualidade + afinidade), com o peso ajustado pelo controle "velocidade <-> qualidade"
        const wq = Math.max(0.05, Math.min(0.95, (W[cl.cat] || 0.5) + (cfg.balance - 50) / 100 * 0.6 + (cl.hard ? 0.1 : 0)));
        const ms = m => (window.lumeScores && lumeScores.ms(m)) || (st[m.id] && st[m.id].ms) || 4500, sp = m => 1 - Math.min(1, ms(m) / 12000);
        const scored = keep.map(m => {
            const iq = window.lumeScores ? lumeScores.iq(m) : null; let q = iq != null ? Math.min(1, iq / 55) : (isLocal(m) ? 0.18 : 0.3);   // sem nota: neutro (local pequeno um pouco abaixo)
            const aff = AFF[cl.cat] && AFF[cl.cat].test((m.id || '') + ' ' + nm(m)) ? 0.08 : 0; q = Math.min(1, q + aff);
            return { m, iq, q, s1: wq * q + (1 - wq) * sp(m) * 0.6, sp: sp(m), ms: ms(m) };
        }).sort((a, b) => b.s1 - a.s1);
        const seen = new Set(), top = [];   // o mesmo modelo por varios provedores conta uma vez so (fica o de melhor etapa 1)
        for (const c of scored) { const fam = nm(c.m).toLowerCase().replace(/\([^)]*\)/g, '').replace(/[^a-z0-9]/g, ''); if (seen.has(fam)) continue; seen.add(fam); top.push(c); if (top.length >= Math.max(3, cfg.k)) break; }
        log('candidatos', 'peso qualidade ' + Math.round(wq * 100) + '% · melhores para o pedido: ' + top.map(c => nm(c.m) + ' (nota ' + (c.iq == null ? '?' : c.iq.toFixed(1)) + ', ~' + (c.ms / 1000).toFixed(1) + ' s)').join(' > '));
        // etapa 2: estabilidade (metade do peso) e velocidade/qualidade (a outra metade, no mesmo equilibrio da etapa 1); quem caiu de molho ou esta instavel sai
        const ranked = top.map(c => { const s = stability(c.m, st); return Object.assign(c, { st: s, s2: 0.5 * s.v + 0.5 * ((1 - wq) * c.sp + wq * c.q) - (c.m.warn ? 0.05 : 0) }); });
        const out = ranked.filter(c => { if (c.st.cool) { log('corte', nm(c.m) + ' de molho: ' + c.st.note); return false; } if (c.st.v < cfg.minStab) { log('corte', nm(c.m) + ' instável demais (' + c.st.v.toFixed(2) + '): ' + c.st.note); return false; } return true; }).sort((a, b) => b.s2 - a.s2);
        const fallbackList = ranked.filter(c => !out.includes(c)).sort((a, b) => b.st.v - a.st.v);   // os cortados por instabilidade ficam como ultimo recurso
        const final = out.concat(fallbackList).map(c => c.m);
        log('escolha', final.length ? 'usar ' + nm(final[0]) + ' (estabilidade ' + (ranked.find(c => c.m === final[0]).st.v).toFixed(2) + ' · ' + ranked.find(c => c.m === final[0]).st.note + ') · se falhar: ' + final.slice(1, cfg.tries).map(nm).join(' > ') + ' · decidido em ' + Math.round(performance.now() - t0) + ' ms' : 'nenhum candidato restou');
        api.last = final[0] ? { id: final[0].id, label: nm(final[0]) } : null;
        return { list: final.slice(0, Math.max(1, cfg.tries)), category: cl.cat, why: cl.why };
    }

    // ---------------------------------------------------------------- janelas
    function openLog() {
        if (document.getElementById('lr-log')) return; const U = window.LumeUI, w = U.modal({ title: 'Log do Lume Auto', id: 'lr-log', width: 900 });
        const pre = U.el('pre'); pre.style.cssText = 'margin:0;max-height:62vh;overflow:auto;font:12px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-word;padding:12px;border-radius:12px;background:rgba(128,128,128,.12)';
        const info = U.el('div', 'lu-hint', ''); w.body.append(info, pre);
        const load = async () => { try { const d = await (await fetch(API + '/api/router_log?n=500')).json(); pre.textContent = (d.lines || []).join('\n') || T('(o Lume Auto ainda não fez nada)'); info.textContent = d.file ? T('Arquivo: ') + d.file : ''; pre.scrollTop = pre.scrollHeight; } catch (e) { pre.textContent = T('Não consegui ler o log.'); } };
        U.button(w.foot, 'Atualizar', () => { flush(); setTimeout(load, 400); }); U.button(w.foot, 'Limpar', async () => { await fetch(API + '/api/router_log_clear', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }); ring.length = 0; load(); });
        flush(); setTimeout(load, 350);
    }
    function openSettings() {
        if (document.getElementById('lr-set')) return; const U = window.LumeUI, w = U.modal({ title: 'Troca automática de modelo', id: 'lr-set', width: 560 });
        w.body.appendChild(U.el('div', 'lu-hint', T('Quando o modelo escolhido falha, o Lume pode passar sozinho para outro parecido, o mais estável e rápido. Ligue em "Trocar sozinho quando falhar". Tudo fica no log.')));
        let s = U.section(w.body, 'Quem pode ser escolhido', { open: true });
        U.toggle(s, 'Modelos pagos (gastam saldo)', cfg.paid, v => { cfg.paid = v; save(); }); U.toggle(s, 'Modelos locais (Ollama)', cfg.local, v => { cfg.local = v; save(); });
        U.toggle(s, 'Modelos que registram as conversas (privacidade)', cfg.registra, v => { cfg.registra = v; save(); });
        s = U.section(w.body, 'Como escolhe', { open: true });
        U.row(s, 'Prioridade: velocidade ← → qualidade', U.range(0, 100, cfg.balance, v => { cfg.balance = v; save(); }), 'Para pedidos de código e raciocínio ele já puxa para a qualidade; para conversa curta, para a velocidade. Isto move os dois.');
        U.row(s, 'Quantos candidatos olhar', U.range(3, 16, cfg.k, v => { cfg.k = v; save(); })); U.row(s, 'Tentativas até desistir', U.range(1, 8, cfg.tries, v => { cfg.tries = v; save(); }), 'Quantos modelos da lista ele tenta antes de mostrar o erro.');
        U.row(s, 'Esperar a primeira resposta (segundos)', U.range(15, 120, cfg.timeout, v => { cfg.timeout = v; save(); }), 'Sem resposta nesse tempo, ele passa para o próximo.');
        U.toggle(s, 'Trocar sozinho quando falhar, mesmo com outro modelo escolhido', cfg.autoSwitch, v => { cfg.autoSwitch = v; save(); });
        s = U.section(w.body, 'Log', { open: true });
        U.toggle(s, 'Guardar um trecho do pedido no log', cfg.excerpt, v => { cfg.excerpt = v; save(); }); U.button(s, 'Ver o log', openLog);
        U.button(w.foot, 'Zerar histórico de estabilidade', () => { wr(STAT_KEY, {}); log('config', 'histórico de estabilidade zerado'); });
    }

    const api = { AUTO_ID, route, report, log, openLog, openSettings, classify, stability, last: null, get config() { return cfg; }, get stats() { return stats(); } };
    window.lumeRouter = api;
    setTimeout(() => { if (window.lumeScores) lumeScores.load(); }, 5000);   // as notas de inteligencia ja estao prontas quando o primeiro pedido chegar
})();
