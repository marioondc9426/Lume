/* Duelo de xadrez (em Jogos): VOCE ASSISTE. Cada lado pode ser um modelo (qualquer um do seletor) ou o Stockfish (nivel 0 a 20), entao da para ver modelo contra modelo,
   Stockfish contra modelo, ou Stockfish contra Stockfish. Um lance por vez, com pausa, velocidade ajustavel e o PGN no fim.
   Modelo contra modelo (decidido, sem empate) conta como voto no seu ranking pessoal (libs/lume-scores.js).
   Usa o chess.js (libs/chess.min.js), o Stockfish (libs/stockfish) e o lumeAsk; nao mexe nas suas conversas. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const css = document.createElement('style');
    css.textContent = `
        .dl-wrap { display: grid; grid-template-columns: minmax(0, 1fr) minmax(290px, 400px); gap: 18px; align-items: start; } @media (max-width: 860px) { .dl-wrap { grid-template-columns: minmax(0, 1fr); } }
        .dl-main { display: flex; flex-direction: column; gap: 12px; min-width: 0; } .dl-panel { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
        .dl-sides { display: grid; grid-template-columns: 1fr; gap: 8px; }
        .dl-side { padding: 10px 12px; border-radius: 14px; background: rgba(128,128,128,.10); display: flex; flex-direction: column; gap: 8px; } .dl-side h4 { margin: 0; font-size: .9em; } .dl-side .lu-seg { margin: 0; }
        .dl-lvl { display: flex; align-items: center; gap: 10px; font-size: .85em; } .dl-lvl input { flex: 1; }
        .dl-board { display: grid; grid-template-columns: repeat(8, 1fr); grid-template-rows: repeat(8, 1fr); width: min(620px, 100%, calc(100vh - 230px)); min-width: 260px; aspect-ratio: 1; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 24px rgba(0,0,0,.35); }
        .dl-sq { aspect-ratio: 1; min-width: 0; min-height: 0; position: relative; display: flex; align-items: center; justify-content: center; } .dl-sq.l { background: #eeeed2; } .dl-sq.d { background: #769656; } .dl-sq.mv::after { content: ''; position: absolute; inset: 0; background: rgba(255, 220, 60, .42); } .dl-sq img { width: 92%; height: 92%; object-fit: contain; z-index: 1; pointer-events: none; }
        .dl-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: center; } .dl-bar .btn { margin: 0; } .dl-bar select { width: auto; }
        .dl-moves { font-size: .82em; line-height: 1.6; max-height: 120px; overflow-y: auto; padding: 8px 12px; border-radius: 12px; background: rgba(128,128,128,.10); color: var(--text-muted); }
        .dl-plans { display: none; flex-direction: column; gap: 6px; max-height: 260px; overflow-y: auto; padding: 8px; border-radius: 14px; background: rgba(128,128,128,.08); } .dl-plans.on { display: flex; }
        .dl-sq .dl-badge { position: absolute; top: 2px; right: 2px; min-width: 1.5em; height: 1.5em; padding: 0 3px; border-radius: 999px; z-index: 2; display: flex; align-items: center; justify-content: center; font: 700 12px system-ui, sans-serif; color: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.4); }
        .dl-chips { display: none; flex-wrap: wrap; gap: 6px; } .dl-chips.on { display: flex; } .dl-chip { border: 1px solid var(--border-color); background: transparent; color: var(--text-muted); border-radius: 999px; padding: 4px 10px; font-size: .78em; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; } .dl-chip i { font-style: normal; font-weight: 700; } .dl-chip.on { color: var(--text-main); background: rgba(128,128,128,.18); border-color: var(--text-muted); }
        .dl-moves i.dl-cl { font-style: normal; font-weight: 700; font-size: .85em; margin: 0 2px; } .dl-plan .dl-cl { font-style: normal; font-weight: 700; margin-left: 6px; }
        .dl-plan { padding: 8px 10px; border-radius: 12px; background: rgba(128,128,128,.12); font-size: .86em; line-height: 1.45; } .dl-plan b { font-weight: 650; } .dl-plan small { display: block; color: var(--text-muted); margin-bottom: 2px; } .dl-plan.new { outline: 2px solid var(--accent); }
    `;
    document.head.appendChild(css);
    const el = (t, c, x) => window.LumeUI.el(t, c, x);
    const files = 'abcdefgh';

    // ---- Stockfish (um motor so para o duelo; fecha com a janela)
    function xhrText(url) { return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url); x.onload = () => ((x.status === 200 || x.status === 0) && x.responseText ? res(x.responseText) : rej(new Error('HTTP ' + x.status))); x.onerror = () => rej(new Error('rede')); x.send(); }); }
    async function startEngine() {
        let w; if (/^https?:/.test(location.protocol)) { try { w = new Worker('libs/stockfish/stockfish.js'); } catch (e) { w = null; } }
        if (!w) w = new Worker(URL.createObjectURL(new Blob([await xhrText('libs/stockfish/stockfish.asm.js')], { type: 'text/javascript' })));   // iPhone: motor em JS puro
        let on = null, tap = null; w.onmessage = e => { const l = typeof e.data === 'string' ? e.data : String(e.data); if (tap) tap(l); if (on) on(l); };
        const wait = (cmd, re, ms) => new Promise((res, rej) => { const t = setTimeout(() => { on = null; rej(new Error('o Stockfish nao respondeu')); }, ms || 20000); on = l => { const m = re.exec(l); if (m) { clearTimeout(t); on = null; res(m); } }; w.postMessage(cmd); });
        await wait('uci', /uciok/); await wait('isready', /readyok/);
        return {
            async analyze(fen, ms) {   // {best, lines: [{mv, cp}]}: cp do ponto de vista das BRANCAS (mate vira +-10000); forca total, 2 linhas (para achar o "unico lance")
                const white = fen.split(' ')[1] === 'w', lines = {};
                tap = l => { if (l.startsWith('info') && / score (cp|mate) /.test(l) && / pv /.test(l)) { const k = +((/ multipv (\d+)/.exec(l) || [0, 1])[1]), sc = / score (cp|mate) (-?\d+)/.exec(l), mv = (/ pv (\S+)/.exec(l) || [])[1]; let cp = sc[1] === 'cp' ? +sc[2] : (+sc[2] > 0 ? 10000 - +sc[2] : -10000 - +sc[2]); if (!white) cp = -cp; lines[k] = { mv, cp }; } };
                try { w.postMessage('setoption name Skill Level value 20'); w.postMessage('setoption name MultiPV value 2'); w.postMessage('position fen ' + fen); const m = await wait('go movetime ' + ms, /^bestmove (\S+)/, ms + 8000); return { best: m[1], lines: Object.keys(lines).sort().map(k => lines[k]) }; }
                finally { tap = null; w.postMessage('setoption name MultiPV value 1'); }
            },
            async best(fen, level, ms) { w.postMessage('setoption name Skill Level value ' + Math.max(0, Math.min(20, level))); w.postMessage('position fen ' + fen); const m = await wait('go movetime ' + ms, /^bestmove (\S+)/, ms + 15000); return m[1]; },
            stop() { try { w.terminate(); } catch (e) { /* ok */ } },
        };
    }

    const CLS = {   // ranking dos lances (mesmos nomes, simbolos e cores do xadrez normal)
        brilliant: { n: 'Brilhante', en: 'Brilliant', sym: '!!', c: '#1baca6' }, great: { n: 'Ótimo', en: 'Great', sym: '!', c: '#5c8bb0' }, best: { n: 'Melhor', en: 'Best move', sym: '★', c: '#96bc4b' },
        excellent: { n: 'Excelente', en: 'Excellent', sym: '✓', c: '#96bc4b' }, good: { n: 'Bom', en: 'Good', sym: '✓', c: '#a3b27a' }, inaccuracy: { n: 'Imprecisão', en: 'Inaccuracy', sym: '?!', c: '#f7c631' },
        mistake: { n: 'Erro', en: 'Mistake', sym: '?', c: '#e58f2a' }, blunder: { n: 'Erro grave', en: 'Blunder', sym: '??', c: '#ca3431' },
    };
    const PVAL = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 }, wp = cp => 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1);   // wp: chance de ganhar (0..100)
    const cname = k => (typeof curLang === 'function' && curLang() === 'en') ? CLS[k].en : CLS[k].n;
    function startDuel(host) {
        const u = window.LumeUI, kit = window.lumeGamesKit; let game = null, running = false, token = 0, engine = null, log = [], last = null, delay = 700, rank = false, cls = [], an = {}, planCards = [], startFen = '';   // startFen: posicao montada no editor de tabuleiro ('' = a inicial)
        const show = { brilliant: true, great: true, best: true, excellent: false, good: false, inaccuracy: true, mistake: true, blunder: true };
        const side = { w: { kind: 'model', level: 8, pick: null }, b: { kind: 'engine', level: 5, pick: null } };
        const sides = el('div', 'dl-sides'), board = el('div', 'dl-board'), status = el('div', 'gm-status', ''), bar = el('div', 'dl-bar'), moves = el('div', 'dl-moves', '');
        const plans = el('div', 'dl-plans'), main = el('div', 'dl-main'), panel = el('div', 'dl-panel'), wrap = el('div', 'dl-wrap'); let explain = false, plist = [];
        const card = host.closest && host.closest('.lu-card'); if (card) card.style.setProperty('--lu-w', '1060px');   // o duelo usa a janela larga: tabuleiro de um lado, painel do outro
        main.append(board, bar); panel.appendChild(sides);
        u.toggle(panel, 'A IA explica o que está tentando fazer em cada lance', false, v => { explain = v; plans.classList.toggle('on', v); }, 'dl-explain');
        u.toggle(panel, 'Mostrar a classificação dos lances (Brilhante, Ótimo, Melhor, Erro...)', false, v => { rank = v; chips.classList.toggle('on', v); if (v) ensureEngine().catch(() => {}); draw(); refreshPlanBadges(); }, 'dl-rank');
        const chips = el('div', 'dl-chips');
        Object.keys(CLS).forEach(k => { const b = el('button', 'dl-chip' + (show[k] ? ' on' : '')); b.type = 'button'; const ic = el('i', '', CLS[k].sym); ic.style.color = CLS[k].c; b.append(ic, document.createTextNode(cname(k))); b.title = T('Mostrar ou esconder este tipo de lance'); b.onclick = () => { show[k] = !show[k]; b.classList.toggle('on', show[k]); draw(); refreshPlanBadges(); }; chips.appendChild(b); });
        const cost = window.lumeCostBar ? window.lumeCostBar() : null; panel.append(chips, status); if (cost) panel.appendChild(cost.el); panel.append(plans, moves); wrap.append(main, panel); host.appendChild(wrap);
        ['w', 'b'].forEach(c => {
            const box = el('div', 'dl-side'), head = el('h4', '', c === 'w' ? '♔ ' + T('Brancas') : '♚ ' + T('Pretas')), body = el('div'); body.style.cssText = 'display:flex;flex-direction:column;gap:8px';
            box.append(head); u.seg(box, [['model', 'Modelo'], ['engine', 'Stockfish']], side[c].kind, v => { side[c].kind = v; paintSide(c); }); box.appendChild(body); sides.appendChild(box); side[c].body = body; paintSide(c);
        });
        function paintSide(c) {
            const s = side[c], body = s.body; body.textContent = '';
            if (s.kind === 'model') { s.pick = kit.pickerFor(body); if (!s.pick) body.appendChild(el('div', 'lu-hint', T('Nenhum modelo disponível agora.'))); }
            else { const row = el('div', 'dl-lvl'), val = el('span', '', ''), r = u.range(0, 20, s.level, v => { s.level = v; val.textContent = v; }); val.textContent = s.level; row.append(el('span', '', T('Nível')), r, val); body.append(row, el('div', 'lu-hint', T('0 = iniciante, 20 = força máxima.'))); }
        }
        const who = c => side[c].kind === 'engine' ? 'Stockfish ' + side[c].level : (side[c].pick && side[c].pick.get() ? (side[c].pick.get().label || side[c].pick.get().id) : '?');
        function draw() {
            board.textContent = ''; const b = game.board();
            for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) {
                const sq = el('div', 'dl-sq ' + ((r + f) % 2 ? 'd' : 'l') + (last && (last.from === files[f] + (8 - r) || last.to === files[f] + (8 - r)) ? ' mv' : '')), p = b[r][f];
                if (rank && last && last.to === files[f] + (8 - r)) { const c = cls[log.length - 1]; if (c && show[c.key]) { const bd = el('span', 'dl-badge', CLS[c.key].sym); bd.style.background = CLS[c.key].c; bd.title = cname(c.key); sq.appendChild(bd); } }
                if (p) { const img = document.createElement('img'); img.alt = p.type; img.src = (window.CHESS_PIECES || {})[p.color + p.type.toUpperCase()] || ''; sq.appendChild(img); } board.appendChild(sq);
            }
            moves.textContent = ''; if (!log.length) moves.textContent = T('(sem lances ainda)');
            const off = startFen && startFen.split(' ')[1] === 'b' ? 1 : 0;   // posicao que comeca com as pretas: o 1o lance e "1..."
            log.forEach((m, i) => { if ((i + off) % 2 === 0) moves.appendChild(document.createTextNode((Math.floor((i + off) / 2) + 1) + '. ')); else if (i === 0) moves.appendChild(document.createTextNode('1... ')); moves.appendChild(document.createTextNode(m)); const c = cls[i]; if (rank && c && show[c.key]) { const ic = el('i', 'dl-cl', CLS[c.key].sym); ic.style.color = CLS[c.key].c; ic.title = cname(c.key); moves.appendChild(ic); } moves.appendChild(document.createTextNode(' ')); }); moves.scrollTop = moves.scrollHeight;
        }
        const parseModel = (text, legal) => {   // aceita SAN (Nf3) ou coordenadas (g1f3)
            const t = String(text || '').replace(/[*`]/g, ' '); for (const m of legal) { const re = new RegExp('(^|[\\s,.;:()])' + m.san.replace(/[+#]/g, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[+#]?($|[\\s,.;:!?)])'); if (re.test(t)) return m; }
            const c = /([a-h][1-8])\s*[-x:]?\s*([a-h][1-8])\s*=?\s*([qrbn])?/i.exec(t.toLowerCase()); if (c) return legal.find(m => m.from === c[1] && m.to === c[2] && (!m.promotion || m.promotion === (c[3] || 'q'))) || null; return null;
        };
        let lastUse = 0;   // pollen gasto pelo modelo no lance atual (soma as tentativas)
        async function pickMove(c, my) {
            lastUse = 0;
            const legal = game.moves({ verbose: true }), s = side[c];
            if (s.kind === 'engine') { const bm = await engine.best(game.fen(), s.level, 120 + s.level * 40); if (my !== token) return null; const m = legal.find(x => x.from === bm.slice(0, 2) && x.to === bm.slice(2, 4) && (!x.promotion || x.promotion === (bm[4] || 'q'))); return { m: m || legal[0], note: m ? '' : 'lance do motor não reconhecido' }; }
            const mdl = s.pick && s.pick.get(); if (!mdl) return { m: legal[Math.floor(Math.random() * legal.length)], note: 'sem modelo escolhido' };
            const en = typeof curLang === 'function' && curLang() === 'en';
            const sys = explain ? (en ? 'You play real chess and want to win. Answer in EXACTLY two lines. Line 1: ONLY your move, in SAN notation from the list of legal moves (e.g. Nf3, exd5, O-O, e8=Q). Line 2: "PLAN: " followed by ONE short sentence in English saying what you are trying to do with that move (attack, defend, develop, threaten, trade, castle...).' : 'Você joga xadrez de verdade e quer ganhar. Responda em EXATAMENTE duas linhas. Linha 1: SOMENTE o seu lance, em notação SAN da lista de lances legais (ex.: Nf3, exd5, O-O, e8=Q). Linha 2: "PLANO: " e UMA frase curta dizendo o que você está tentando fazer com esse lance (atacar, defender, desenvolver, ameaçar, trocar, rocar...).')
                : 'Você joga xadrez de verdade e quer ganhar. Responda SOMENTE com o seu lance, em notação SAN da lista de lances legais (ex.: Nf3, exd5, O-O, e8=Q). Nada de explicação.';
            for (let i = 0; i < 2; i++) {
                let r; try { r = await lumeAsk({ model: mdl, track: true, onUsage: u => { lastUse += u.pollen || 0; }, system: sys, user: 'Posição (FEN): ' + game.fen() + '\nLances até agora: ' + (log.join(' ') || '(nenhum)') + '\nVocê joga de ' + (c === 'w' ? 'brancas' : 'pretas') + '.\nLances legais: ' + legal.map(x => x.san).join(', ') + '\nResponda só com o seu lance.' + (i ? '\nA resposta anterior não era um lance legal da lista.' : ''), timeoutMs: 60000 }); } catch (e) { if (my !== token) return null; return { m: legal[Math.floor(Math.random() * legal.length)], note: 'o modelo falhou (' + String(e.message || e).slice(0, 60) + '); lance sorteado' }; }
                if (my !== token) return null; const pm = /(?:PLANO|PLAN|WHY)\s*:\s*([\s\S]+)/i.exec(String(r || '')), plan = pm ? pm[1].replace(/\s+/g, ' ').trim().slice(0, 240) : '', m = parseModel(pm ? String(r).slice(0, pm.index) : r, legal); if (m) return { m, note: '', plan };
            }
            return { m: legal[Math.floor(Math.random() * legal.length)], note: 'o modelo não deu um lance válido; lance sorteado' };
        }
        async function ensureEngine() { if (!engine) engine = await startEngine(); return engine; }
        const an1 = async fen => an[fen] || (an[fen] = await engine.analyze(fen, 350));
        const matNet = (g, color) => { let a = 0, b = 0; g.board().forEach(row => row.forEach(p => { if (p) { if (p.color === color) a += PVAL[p.type]; else b += PVAL[p.type]; } })); return a - b; };
        async function classifyPly(i, mv, fen0, my) {   // classifica o lance i comparando o que o Stockfish achava ANTES e DEPOIS (chance de ganhar de quem jogou)
            await ensureEngine(); const A = await an1(fen0); if (my !== token || !A.lines.length) return; const over = game.game_over(), B = over ? null : await an1(game.fen()); if (my !== token) return;
            const pov = cp => (mv.color === 'w' ? cp : -cp), bw = wp(pov(A.lines[0].cp)), aw = over ? (game.in_checkmate() ? 100 : 50) : (B && B.lines.length ? wp(pov(B.lines[0].cp)) : bw), loss = Math.max(0, bw - aw);
            const uci = mv.from + mv.to + (mv.promotion || ''), best = uci === A.best, second = A.lines[1] ? wp(pov(A.lines[1].cp)) : null, onlyMove = best && second !== null && bw - second >= 15;
            let key = best || loss <= 0.5 ? 'best' : loss <= 2 ? 'excellent' : loss <= 5 ? 'good' : loss <= 10 ? 'inaccuracy' : loss <= 20 ? 'mistake' : 'blunder';
            if (best && onlyMove && bw < 92) key = 'great';
            if ((best || loss <= 1) && bw >= 35 && bw < 88 && aw >= 45 && aw >= bw - 3 && B && B.best && B.best.length >= 4) {   // sacrificio de peca que continua bom: depois da melhor resposta do adversario o seu material fica >= 2 pontos pior
                try { const g0 = new Chess(fen0), before = matNet(g0, mv.color), g1 = new Chess(game.fen()); g1.move({ from: B.best.slice(0, 2), to: B.best.slice(2, 4), promotion: B.best[4] }); if (matNet(g1, mv.color) <= before - 2) key = 'brilliant'; } catch (e) { /* sem selo de brilhante */ }
            }
            cls[i] = { key, loss }; draw(); refreshPlanBadges();
        }
        function refreshPlanBadges() {
            planCards.forEach((card, i) => { if (!card) return; const old = card.querySelector('.dl-cl'); if (old) old.remove(); const c = cls[i]; if (rank && c && show[c.key]) { const ic = el('i', 'dl-cl', CLS[c.key].sym + ' ' + cname(c.key)); ic.style.color = CLS[c.key].c; card.querySelector('small').appendChild(ic); } });
        }
        function addPlan(c, san, plan, pollen) {   // cartao com o plano da IA para este lance (o mais novo fica destacado, no fim da lista)
            plans.querySelectorAll('.dl-plan.new').forEach(e => e.classList.remove('new'));
            const card = el('div', 'dl-plan new'), no = Math.floor((log.length - 1 + (startFen && startFen.split(' ')[1] === 'b' ? 1 : 0)) / 2) + 1;
            card.appendChild(el('small', '', no + (c === 'w' ? '. ' : '... ') + who(c) + ' (' + T(c === 'w' ? 'Brancas' : 'Pretas') + ')'));
            const b = el('b', '', san); card.append(b, document.createTextNode(' — ' + (plan || T('(a IA não explicou este lance)')))); if (pollen) card.querySelector('small').appendChild(document.createTextNode('  🌸 ' + pollen.toFixed(6))); plans.appendChild(card); planCards[log.length - 1] = card; plans.scrollTop = plans.scrollHeight;
        }
        const resultText = () => game.in_checkmate() ? (game.turn() === 'w' ? 'Pretas' : 'Brancas') + ' ' + T('ganharam por xeque-mate') : game.in_stalemate() ? T('Empate: afogamento') : game.insufficient_material() ? T('Empate: material insuficiente') : game.in_threefold_repetition() ? T('Empate: repetição') : game.in_draw() ? T('Empate (50 lances)') : '';
        async function loop(my) {
            while (running && my === token) {
                if (game.game_over() || log.length >= 200) break;
                const c = game.turn(); status.textContent = who(c) + ' ' + T('está pensando…') + ' (' + (c === 'w' ? T('Brancas') : T('Pretas')) + ')';
                let res; try { res = await pickMove(c, my); } catch (e) { status.textContent = T('Erro: ') + String(e.message || e).slice(0, 100); running = false; break; }
                if (!res || my !== token) return;
                const fen0 = game.fen(), mv = game.move(res.m.san); log.push(mv.san); last = { from: mv.from, to: mv.to }; draw(); status.textContent = who(c) + ': ' + mv.san + (res.note ? ' — ' + T(res.note) : '');
                if (cost && side[c].kind === 'model') { cost.spend((c === 'w' ? T('Brancas') : T('Pretas')), lastUse); if (lastUse) status.textContent += ' · 🌸 ' + lastUse.toFixed(6); }
                if (explain && side[c].kind === 'model') addPlan(c, mv.san, res.plan, lastUse);
                if (rank) { try { await classifyPly(log.length - 1, mv, fen0, my); } catch (e) { status.textContent = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 60); } }
                await new Promise(r => setTimeout(r, delay)); while (running && my === token && paused) await new Promise(r => setTimeout(r, 200));
            }
            if (my !== token) return; running = false; syncBtns();
            if (game.game_over() || log.length >= 200) {
                const rt = resultText() || T('Parou no limite de 200 lances (empate).'); status.textContent = T('Fim: ') + rt + '.';
                if (game.in_checkmate() && side.w.kind === 'model' && side.b.kind === 'model' && window.lumeScores) { const win = game.turn() === 'w' ? side.b.pick.get() : side.w.pick.get(), lose = game.turn() === 'w' ? side.w.pick.get() : side.b.pick.get(); if (win && lose && win.id !== lose.id) { lumeScores.vote(win.id, [lose.id], false); status.textContent += ' ' + T('(contou no seu ranking)'); } }
            }
        }
        let paused = false; const bPlay = u.button(bar, 'Começar', () => begin()), bPause = u.button(bar, 'Pausar', () => { paused = !paused; bPause.textContent = T(paused ? 'Continuar' : 'Pausar'); }), bCopy = u.button(bar, 'Copiar PGN', () => { const h = '[White "' + who('w') + '"]\n[Black "' + who('b') + '"]\n' + (startFen ? '[SetUp "1"]\n[FEN "' + startFen + '"]\n' : '') + '[Result "' + (game.in_checkmate() ? (game.turn() === 'w' ? '0-1' : '1-0') : game.game_over() ? '1/2-1/2' : '*') + '"]\n\n'; let o = ''; log.forEach((m, i) => { if (i % 2 === 0) o += (i / 2 + 1) + '. '; o += m + ' '; }); try { navigator.clipboard.writeText(h + o.trim()); status.textContent = T('PGN copiado.'); } catch (e) { /* sem area de transferencia */ } });
        const spd = u.select([['1400', 'Devagar'], ['700', 'Normal'], ['200', 'Rápido']], '700', v => { delay = +v; }); bar.appendChild(spd);
        function syncBtns() { bPlay.textContent = T(running ? 'Reiniciar' : 'Começar'); bPause.style.display = running ? '' : 'none'; bCopy.style.display = log.length ? '' : 'none'; }
        async function begin() {
            token++; const my = token; running = false; paused = false; bPause.textContent = T('Pausar'); game = new Chess(); if (startFen) game.load(startFen); log = []; last = null; plans.textContent = ''; cls = []; an = {}; planCards = []; if (cost) cost.reset(); draw();
            const needEngine = side.w.kind === 'engine' || side.b.kind === 'engine';
            if (needEngine && !engine) { status.textContent = T('Ligando o Stockfish…'); try { engine = await startEngine(); } catch (e) { status.textContent = T('Não consegui ligar o Stockfish: ') + String(e.message || e).slice(0, 80); return; } }
            if (my !== token) return; running = true; syncBtns(); loop(my);
        }
        const bEdit = u.button(bar, 'Editar tabuleiro', () => { if (running) { status.textContent = T('Pare a partida (Reiniciar) antes de editar o tabuleiro.'); return; } window.lumeBoardEditor && lumeBoardEditor.open({ fen: startFen || game.fen(), onApply: fen => { startFen = fen; token++; running = false; game = new Chess(); game.load(fen); log = []; last = null; plans.textContent = ''; cls = []; an = {}; planCards = []; draw(); syncBtns(); status.textContent = T('Posição montada. Escolha quem joga de cada lado e aperte Começar.'); } }); });
        bar.insertBefore(bEdit, bar.firstChild); u.button(bar, 'Posição inicial', () => { if (!startFen) return; startFen = ''; token++; running = false; game = new Chess(); log = []; last = null; plans.textContent = ''; cls = []; an = {}; planCards = []; draw(); syncBtns(); status.textContent = T('Escolha quem joga de cada lado e aperte Começar.'); }).title = T('Volta ao tabuleiro normal');
        game = new Chess(); draw(); syncBtns(); status.textContent = T('Escolha quem joga de cada lado e aperte Começar.');
        // limpa ao fechar a janela de jogos / voltar ao menu: o host sai do documento
        const mo = new MutationObserver(() => { if (!host.isConnected) { token++; running = false; if (engine) engine.stop(); if (card) card.style.removeProperty('--lu-w'); mo.disconnect(); } }); mo.observe(document.body, { childList: true, subtree: true });
    }
    if (window.LUME_GAMES) window.LUME_GAMES.push({ id: 'duel', name: 'Duelo de xadrez', desc: 'Você assiste: modelo contra modelo, ou contra o Stockfish.', start: startDuel });
})();
