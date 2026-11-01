/* Comparar modelos (a arena): a mesma pergunta para 2 ou 3 modelos ao mesmo tempo, lado a lado, com o tempo de cada um.
   Dá para SORTEAR os modelos por criterio (mais rapidos, mais lentos, mais inteligentes, os melhores no seu ranking...), comparar as CEGAS (os nomes so aparecem depois do seu voto)
   e votar em quem respondeu melhor: os votos viram o seu ranking pessoal. A segunda aba mede a velocidade dos seus modelos e mostra tudo numa tabela.
   Botao "Comparar modelos" na lateral. Usa o kit LumeUI, o lumeAsk (nao mexe nas suas conversas) e o libs/lume-scores.js. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const css = document.createElement('style');
    css.textContent = `
        .cp-pick { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; } .cp-pick select { width: 100%; }
        .cp-draw { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; } .cp-draw select { width: auto; min-width: 150px; flex: 0 1 auto; } .cp-draw .btn { margin: 0; } .cp-draw .lu-tog { margin-left: auto; }
        .cp-cols { display: grid; grid-template-columns: repeat(var(--n, 2), minmax(0, 1fr)); gap: 10px; flex: 1 1 auto; min-height: 120px; }
        .cp-col { display: flex; flex-direction: column; min-width: 0; border-radius: 14px; background: rgba(128,128,128,.10); overflow: hidden; }
        .cp-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 12px; font-size: .85em; font-weight: 600; border-bottom: 1px solid var(--border-color); } .cp-head span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .cp-time { font-weight: 400; color: var(--text-muted); font-size: .9em; flex: none; } .cp-time.ok { color: #3fb950; } .cp-time.bad { color: #e5484d; }
        .cp-text { padding: 10px 12px; font-size: .9em; line-height: 1.5; white-space: normal; overflow-y: auto; max-height: 46vh; flex: 1; word-break: break-word; }
        .cp-foot { padding: 6px 10px 10px; display: flex; gap: 6px; } .cp-foot .btn { margin: 0; padding: 4px 11px; font-size: .8em; }
        .cp-q { width: 100%; box-sizing: border-box; min-height: 70px; resize: vertical; }
        .cp-vote { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px 12px; border-radius: 14px; background: rgba(128,128,128,.10); } .cp-vote b { font-size: .9em; } .cp-vote .btn { margin: 0; }
        .cp-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; } .cp-bar .btn { margin: 0; } .cp-bar .lu-tog { margin: 0; }
        .cp-note { font-size: .82em; color: var(--text-muted); }
        .cp-tblw { max-height: 52vh; overflow: auto; border-radius: 12px; border: 1px solid var(--border-color); }
        .cp-tbl { width: 100%; border-collapse: collapse; font-size: .86em; } .cp-tbl th, .cp-tbl td { padding: 7px 10px; text-align: left; white-space: nowrap; border-bottom: 1px solid rgba(128,128,128,.14); } .cp-tbl td:first-child { white-space: normal; min-width: 160px; }
        .cp-tbl th { position: sticky; top: 0; background: var(--bg-sidebar); cursor: pointer; user-select: none; z-index: 1; } .cp-tbl th.on::after { content: ' ▾'; } .cp-tbl th.on.up::after { content: ' ▴'; }
        .cp-tbl td.num { font-variant-numeric: tabular-nums; } .cp-tbl .muted { color: var(--text-muted); } .cp-tbl tr.bad td { opacity: .55; }
        @media (max-width: 760px) { .cp-pick, .cp-cols { grid-template-columns: minmax(0, 1fr); } }
    `;
    document.head.appendChild(css);

    const MODES = [['random', 'Aleatórios'], ['fast', 'Mais rápidos primeiro'], ['slow', 'Mais lentos primeiro'], ['smart', 'Mais inteligentes primeiro'], ['dumb', 'Menos inteligentes primeiro'], ['mine', 'Melhores no seu ranking']];
    const label = m => { let p = ''; try { p = providerName(m); } catch (e) { /* sem provedor */ } return (m.label || m.id) + (p ? ' · ' + p : ''); };
    const provOf = m => { try { return providerName(m); } catch (e) { return ''; } };
    const fmtMs = m => { const v = lumeScores.ms(m); return v == null ? '' : (v / 1000).toFixed(1) + ' s' + (lumeScores.estimated(m) ? ' ~' : ''); };

    window.openCompare = function () {
        if (document.getElementById('cp-modal')) return;
        let ctl = null;   // o pedido em andamento: fecha a janela, cancela
        const u = window.LumeUI, w = u.modal({ title: 'Comparar modelos', id: 'cp-modal', width: 1100, onClose: () => { if (ctl) ctl.abort(); if (bench) bench.abort(); } });
        let bench = null;
        const models = (window.lumeModels ? lumeModels() : []).filter(m => !m.phone);
        if (models.length < 2) { w.body.appendChild(u.el('div', 'lu-hint', T('Preciso de pelo menos 2 modelos disponíveis. Configure uma chave ou ligue o Ollama.'))); return; }
        let runBtn = { style: {} };   // o botao Comparar (so na primeira aba)
        const tabs = u.el('div'), pageA = u.el('div'), pageB = u.el('div'); [pageA, pageB].forEach(p => { p.style.cssText = 'display:flex;flex-direction:column;gap:10px'; });
        pageB.style.display = 'none'; u.seg(tabs, [['a', 'Comparar'], ['b', 'Velocidade e ranking']], 'a', v => { pageA.style.display = v === 'a' ? 'flex' : 'none'; pageB.style.display = v === 'b' ? 'flex' : 'none'; runBtn.style.display = v === 'a' ? '' : 'none'; if (v === 'b') drawTable(); });
        w.body.append(tabs, pageA, pageB);
        lumeScores.load();   // as notas de inteligencia chegam sozinhas (o sorteio por inteligencia espera por elas)

        // ================= aba 1: comparar
        const cur = (typeof selectedModel !== 'undefined' ? models.findIndex(m => m.id === selectedModel) : -1);
        const sels = [0, 1, 2].map(i => { const s = u.select([['', i === 2 ? '(nenhum)' : '(escolha)']].concat(models.map(m => [m.id, label(m)])), '', () => {}); s.value = i === 0 && cur >= 0 ? models[cur].id : i === 1 ? (models[cur === 0 ? 1 : 0].id) : ''; return s; });
        let mode = 'random', count = 2, blind = false;
        const draw = u.el('div', 'cp-draw'); pageA.appendChild(draw);
        draw.appendChild(u.el('span', 'cp-note', T('Sortear:')));
        draw.appendChild(u.select(MODES, mode, v => { mode = v; })); draw.appendChild(u.select([['2', '2 modelos'], ['3', '3 modelos']], '2', v => { count = +v; }));
        const note = u.el('div', 'cp-note', '');
        u.button(draw, 'Sortear', async () => {
            if ((mode === 'smart' || mode === 'dumb') && !lumeScores.ready) { note.textContent = T('Baixando as notas de inteligência…'); await lumeScores.load(); note.textContent = ''; }
            if ((mode === 'smart' || mode === 'dumb') && !lumeScores.ready) { note.textContent = T('Sem as notas de inteligência (') + lumeScores.error + T('). Sorteei sem elas.'); }
            else if ((mode === 'fast' || mode === 'slow') && !models.some(m => lumeScores.ms(m) != null)) note.textContent = T('Ainda não há tempos: meça a velocidade na outra aba. Sorteei sem eles.');
            else if (mode === 'mine' && !models.some(m => lumeScores.rate(m.id) != null)) note.textContent = T('Você ainda não votou em ninguém. Sorteei sem o ranking.');
            else note.textContent = '';
            const pick = lumeScores.lineup(models, mode, count); sels.forEach((s, i) => { s.value = pick[i] ? pick[i].id : ''; });
        });
        u.toggle(draw, 'Às cegas', false, v => { blind = v; });
        const pick = u.el('div', 'cp-pick'); sels.forEach(s => pick.appendChild(s)); pageA.append(pick, note);
        const q = u.el('textarea', 'cp-q'); q.placeholder = T('Escreva a pergunta que todos vão responder…'); pageA.appendChild(q);
        const cols = u.el('div', 'cp-cols'), voteBox = u.el('div'); pageA.append(cols, voteBox);
        const run = async () => {
            const text = q.value.trim(); if (!text) { q.focus(); return; }
            let chosen = sels.map(s => s.value).filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).map(id => lumeModelById(id)).filter(Boolean);
            if (chosen.length < 2) { if (typeof showInfo === 'function') showInfo(T('Escolha pelo menos 2 modelos diferentes.'), 4000); return; }
            if (blind) chosen = lumeScores.order(chosen, 'random');   // as cegas: a ordem e sorteada, e os nomes ficam escondidos
            if (ctl) ctl.abort(); ctl = new AbortController(); const my = ctl; stopBtn.style.display = ''; runBtn.disabled = true; cols.textContent = ''; voteBox.textContent = ''; cols.style.setProperty('--n', chosen.length);
            const names = [], pending = []; let finished = 0;
            chosen.forEach((m, i) => {
                const col = u.el('div', 'cp-col'), head = u.el('div', 'cp-head'), nm = u.el('span', '', blind ? T('Modelo') + ' ' + 'ABC'[i] : label(m)), tm = u.el('span', 'cp-time', '…'); head.append(nm, tm); names.push(nm);
                const body = u.el('div', 'cp-text', ''), foot = u.el('div', 'cp-foot'); let raw = '', pt = 0;   // raw = o markdown como veio; a coluna mostra renderizado (como no chat), no maximo ~8x por segundo
                const paint = () => { pt = 0; body.innerHTML = typeof renderRich === 'function' ? (renderRich(raw) || '') : ''; if (typeof renderRich !== 'function') body.textContent = raw; };
                u.button(foot, 'Copiar', () => { try { navigator.clipboard.writeText(raw); } catch (e) { /* sem area de transferencia */ } }); col.append(head, body, foot); cols.appendChild(col);
                const t0 = performance.now(), tick = setInterval(() => { tm.textContent = ((performance.now() - t0) / 1000).toFixed(1) + ' s'; }, 200);
                const fin = () => { if (++finished === chosen.length && ctl === my) { stopBtn.style.display = 'none'; runBtn.disabled = false; if (!my.signal.aborted) showVote(chosen, names); } };
                lumeAsk({ model: m, user: text, system: '', signal: ctl.signal, onText: t => { raw = t; if (!pt) pt = setTimeout(paint, 120); } })
                    .then(t => { clearInterval(tick); const s = (performance.now() - t0) / 1000, words = (t.match(/\S+/g) || []).length; raw = t; clearTimeout(pt); paint(); tm.className = 'cp-time ok'; tm.textContent = s.toFixed(1) + ' s · ' + words + ' ' + T('palavras'); fin(); })
                    .catch(e => { clearInterval(tick); const stopped = my.signal.aborted; tm.className = stopped ? 'cp-time' : 'cp-time bad'; tm.textContent = stopped ? T('parado') : T('erro'); clearTimeout(pt); if (!raw) body.textContent = String(e.message || e); else paint(); fin(); });
            });
        };
        function showVote(chosen, names) {   // quando todos terminam: voto -> ranking pessoal (e revela os nomes nas cegas)
            if (!voteBox.isConnected) return; voteBox.textContent = ''; const box = u.el('div', 'cp-vote'); box.appendChild(u.el('b', '', T('Qual respondeu melhor?')));
            const done = (win, tie) => { lumeScores.vote(win ? win.id : '', chosen.filter(m => m !== win).map(m => m.id), tie); names.forEach((n, i) => { n.textContent = label(chosen[i]); }); box.textContent = ''; box.appendChild(u.el('span', 'cp-note', tie ? T('Empate registrado.') : T('Voto registrado: ') + label(win) + '.')); };
            chosen.forEach((m, i) => u.button(box, blind ? T('Modelo') + ' ' + 'ABC'[i] : label(m), () => done(m, false)));
            u.button(box, 'Empate', () => done(null, true)); voteBox.appendChild(box);
        }
        const stopBtn = u.button(w.foot, 'Parar', () => { if (ctl) ctl.abort(); }); stopBtn.style.display = 'none';
        runBtn = u.button(w.foot, 'Comparar', run, 'primary');
        q.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } });
        setTimeout(() => q.focus(), 50);

        // ================= aba 2: velocidade e ranking
        let sortBy = 'ms', dir = 1, inclPaid = false, inclLocal = false;
        const bar = u.el('div', 'cp-bar'), status = u.el('div', 'cp-note', ''), tblw = u.el('div', 'cp-tblw');
        const mBtn = u.button(bar, 'Medir velocidade', () => startBench()), xBtn = u.button(bar, 'Parar', () => { if (bench) bench.abort(); }); xBtn.style.display = 'none';
        let sampleN = 10; bar.appendChild(u.select([['10', '10 modelos'], ['20', '20 modelos'], ['40', '40 modelos']], '10', v => { sampleN = +v; })); u.button(bar, 'Sortear e medir', () => startBench(sampleN));
        u.toggle(bar, 'Incluir pagos', false, v => { inclPaid = v; }); u.toggle(bar, 'Incluir locais', false, v => { inclLocal = v; });
        u.button(bar, 'Atualizar notas de inteligência', async () => { status.textContent = T('Baixando…'); const ok = await lumeScores.load(true); status.textContent = ok ? T('Notas atualizadas.') : T('Não consegui: ') + lumeScores.error; drawTable(); });
        pageB.append(bar, status, tblw);
        pageB.appendChild(u.el('div', 'cp-note', T('O tempo é de uma pergunta minúscula ("responda só: ok"), então mostra a espera até a primeira resposta, não a velocidade de textos longos. "~" = estimativa pela velocidade do Gratisfy, ainda não medido aqui. Modelos pagos gastam um pouquinho do seu saldo; os locais carregam na GPU na primeira vez, por isso ficam de fora por padrão. Inteligência: Artificial Analysis, pelo Gratisfy.')));
        function startBench(sample) {   // sample: mede so N modelos sorteados (em vez de todos)
            if (bench) return; let todo = models.filter(m => (inclLocal || lumeScores.cloud(m)) && (inclPaid || !lumeScores.paid(m)) && !m.heavy);
            if (sample && todo.length > sample) todo = lumeScores.order(todo, 'random').slice(0, sample);
            if (!todo.length) { status.textContent = T('Nenhum modelo para medir com essas opções.'); return; }
            bench = new AbortController(); mBtn.disabled = true; xBtn.style.display = '';
            lumeScores.measure(todo, { signal: bench.signal, concurrency: 3, onProgress: (d, t, m, r) => { status.textContent = T('Medindo…') + ' ' + d + '/' + t + ' · ' + (m.label || m.id) + ' · ' + (r.ok ? (r.ms / 1000).toFixed(1) + ' s' : T('falhou')); if (d % 4 === 0 || d === t) drawTable(); } })
                .then(d => { status.textContent = T('Pronto: ') + d + T(' modelos medidos.'); }).finally(() => { bench = null; mBtn.disabled = false; xBtn.style.display = 'none'; drawTable(); });
        }
        const COLS = [['name', 'Modelo'], ['prov', 'Provedor'], ['ms', 'Tempo'], ['iq', 'Inteligência'], ['mine', 'Seu ranking']];
        function drawTable() {
            if (!tblw.isConnected) return; tblw.textContent = '';
            const rows = models.map(m => ({ m, name: String(m.label || m.id), prov: provOf(m), ms: lumeScores.ms(m), iq: lumeScores.iq(m), mine: lumeScores.rate(m.id), rec: lumeScores.record(m.id), bad: (lumeScores.measured(m) || {}).ok === false }));
            rows.sort((a, b) => { const x = a[sortBy], y = b[sortBy]; if (x == null || x === '') return y == null || y === '' ? 0 : 1; if (y == null || y === '') return -1; return (typeof x === 'string' ? x.localeCompare(y) : x - y) * dir * (sortBy === 'iq' || sortBy === 'mine' ? -1 : 1); });
            const t = u.el('table', 'cp-tbl'), hr = u.el('tr'); COLS.forEach(([k, l]) => { const th = u.el('th', (sortBy === k ? 'on' + (dir < 0 ? ' up' : '') : ''), T(l)); th.onclick = () => { if (sortBy === k) dir = -dir; else { sortBy = k; dir = 1; } drawTable(); }; hr.appendChild(th); }); t.appendChild(u.el('thead')).appendChild(hr);
            const tb = u.el('tbody'); rows.slice(0, 400).forEach(r => {
                const tr_ = u.el('tr', r.bad ? 'bad' : ''); const td = (x, c) => { const e = u.el('td', c || '', x); tr_.appendChild(e); return e; };
                td(r.name); td(r.prov, 'muted'); td(r.bad ? T('falhou') : fmtMs(r.m), 'num'); td(r.iq == null ? '' : r.iq.toFixed(1), 'num'); td(r.mine == null ? '' : Math.round(r.mine * 100) + '% (' + r.rec.w + '–' + r.rec.l + (r.rec.t ? '–' + r.rec.t : '') + ')', 'num'); tb.appendChild(tr_);
            }); t.appendChild(tb); tblw.appendChild(t);
        }
        lumeScores.load().then(() => { if (pageB.style.display !== 'none') drawTable(); });
    };
})();
