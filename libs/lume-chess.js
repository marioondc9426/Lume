/* Xadrez do Lume: jogue contra qualquer modelo. Regras e lances legais vem do chess.js; o modelo recebe a posicao (e, se quiser, a lista de lances legais) e responde com um lance.
   Opcoes: permitir lances ILEGAIS do modelo; ranking dos lances (Brilhante, Otimo, Melhor, Excelente, Bom, Imprecisao, Erro, Erro grave, Perdeu) e analise da partida, com o Stockfish (libs/stockfish, GPL v3).
   Botao direito: segure e arraste para desenhar uma seta (Shift = vermelha, Ctrl = azul, Alt = amarela); clique direito numa casa marca a casa; clique esquerdo limpa. No celular: segure o dedo numa casa e arraste. */
(() => {
    'use strict';
    const GLYPH = { k: '♚︎', q: '♛︎', r: '♜︎', b: '♝︎', n: '♞︎', p: '♟︎' };
    const FILES = 'abcdefgh', T = s => (typeof tr === 'function' ? tr(s) : s), PVAL = { p: 1, n: 3, b: 3, r: 5, q: 9, k: 0 };
    const CLS = {   // ranking dos lances (como no chess.com)
        brilliant: { n: 'Brilhante', en: 'Brilliant', sym: '!!', c: '#1baca6' }, great: { n: 'Ótimo', en: 'Great', sym: '!', c: '#5c8bb0' }, best: { n: 'Melhor', en: 'Best move', sym: '★', c: '#96bc4b' },
        excellent: { n: 'Excelente', en: 'Excellent', sym: '✓', c: '#96bc4b' }, good: { n: 'Bom', en: 'Good', sym: '✓', c: '#a3b27a' }, inaccuracy: { n: 'Imprecisão', en: 'Inaccuracy', sym: '?!', c: '#f7c631' },
        mistake: { n: 'Erro', en: 'Mistake', sym: '?', c: '#e58f2a' }, blunder: { n: 'Erro grave', en: 'Blunder', sym: '??', c: '#ca3431' }, miss: { n: 'Perdeu', en: 'Miss', sym: '✕', c: '#ff7769' },
    };
    let game = null, st = null, ov = null, engine = null, engQ = Promise.resolve();

    const css = document.createElement('style');
    css.textContent = `
        .chess-ov { position: fixed; inset: 0; z-index: 6500; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.6); padding: 12px; overflow: auto; }
        .chess-wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; justify-content: center; max-width: 100%; background: var(--bg-main); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 20px; padding: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.55); }
        .chess-bw { display: flex; gap: 8px; } .chess-eval { width: 14px; height: var(--cb, 520px); border-radius: 6px; overflow: hidden; background: #262522; position: relative; display: none; } .chess-eval.on { display: block; } .chess-eval i { position: absolute; left: 0; right: 0; bottom: 0; background: #f2f2f2; transition: height .3s; } .chess-eval b { position: absolute; left: 0; right: 0; font: 600 9px system-ui; text-align: center; color: #888; top: 2px; }
        .chess-board { position: relative; width: var(--cb, 520px); height: var(--cb, 520px); display: grid; grid-template-columns: repeat(8, 1fr); grid-template-rows: repeat(8, 1fr); border-radius: 8px; overflow: hidden; user-select: none; -webkit-user-select: none; touch-action: none; }
        .chess-sq { position: relative; display: flex; align-items: center; justify-content: center; font-size: calc(var(--cb, 520px) / 8 * 0.78); line-height: 1; cursor: pointer; }
        .chess-sq.l { background: #ecd9b4; } .chess-sq.d { background: #ae8a68; }
        .chess-sq.sel { box-shadow: inset 0 0 0 4px rgba(255, 214, 10, .85); } .chess-sq.last { background-image: linear-gradient(rgba(255, 238, 90, .45), rgba(255, 238, 90, .45)); }
        .chess-sq.ill { background-image: linear-gradient(rgba(220, 60, 60, .45), rgba(220, 60, 60, .45)); }
        .chess-sq.chk { background-image: radial-gradient(circle, rgba(255, 40, 40, .9) 0%, rgba(255, 40, 40, 0) 70%); }
        .chess-sq.mark { box-shadow: inset 0 0 0 100px rgba(235, 64, 52, .5); }
        .chess-sq.tgt::after { content: ''; position: absolute; width: 28%; height: 28%; border-radius: 50%; background: rgba(20, 20, 20, .28); }
        .chess-sq.tgt.cap::after { width: 86%; height: 86%; background: none; border: 5px solid rgba(20, 20, 20, .28); }
        .chess-pc { z-index: 1; pointer-events: none; } .chess-pc.w { color: #fff; text-shadow: 0 0 2px #000, 0 0 2px #000, 0 0 3px #000, 0 1px 3px rgba(0,0,0,.6); } .chess-pc.b { color: #151515; text-shadow: 0 0 1px #fff, 0 0 2px rgba(255,255,255,.5); }
        .chess-co { position: absolute; font: 600 10px system-ui, sans-serif; opacity: .65; pointer-events: none; color: #333; } .chess-co.r { top: 2px; left: 3px; } .chess-co.f { bottom: 1px; right: 3px; }
        .chess-badge { position: absolute; top: 2px; right: 2px; min-width: 1.5em; padding: 0 3px; height: 1.5em; border-radius: 999px; z-index: 2; display: flex; align-items: center; justify-content: center; font: 700 12px system-ui, sans-serif; color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.5); pointer-events: none; }
        .chess-arrows { position: absolute; inset: 0; pointer-events: none; z-index: 3; }
        .chess-side { display: flex; flex-direction: column; gap: 10px; width: min(300px, 100%); }
        .chess-side h3 { margin: 0; } .chess-side select { width: 100%; } .chess-row { display: flex; flex-wrap: wrap; gap: 6px; } .chess-row .btn { margin: 0; padding: 8px 12px; flex: 1 1 auto; }
        .chess-opt { display: flex; gap: 8px; align-items: center; font-size: .88em; cursor: pointer; } .chess-opt input { width: auto; }
        .chess-status { padding: 10px 12px; border-radius: 12px; background: rgba(128,128,128,.14); font-size: .92em; min-height: 2.6em; }
        .chess-moves { max-height: 170px; overflow-y: auto; font-size: .88em; line-height: 1.9; padding: 8px 10px; border-radius: 12px; background: rgba(128,128,128,.08); }
        .chess-moves span.mv { cursor: pointer; padding: 1px 4px; border-radius: 6px; } .chess-moves span.mv:hover { background: rgba(128,128,128,.25); } .chess-moves span.mv.cur { background: var(--accent); color: #fff; }
        .chess-moves i.cl { font-style: normal; font-weight: 700; font-size: .85em; margin-left: 1px; }
        .chess-sum { font-size: .82em; line-height: 1.5; padding: 8px 10px; border-radius: 12px; background: rgba(128,128,128,.08); }
        .chess-hint { font-size: .76em; color: var(--text-muted); line-height: 1.4; }
        .chess-promo { position: absolute; inset: 0; z-index: 5; display: flex; align-items: center; justify-content: center; gap: 8px; background: rgba(0,0,0,.55); }
        .chess-promo button { font-size: 2.4em; width: 1.5em; height: 1.5em; border-radius: 12px; border: 0; background: #ecd9b4; cursor: pointer; }`;
    document.head.appendChild(css);

    const sqName = (f, r) => FILES[f] + (r + 1);
    const sqXY = sq => ({ f: FILES.indexOf(sq[0]), r: +sq[1] - 1 });
    const mk = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
    const uciOf = m => m.from + m.to + (m.promotion || '');
    function models() { return (typeof MODELS !== 'undefined' ? MODELS : []).filter(m => { try { return m.tabs.includes('chat') && isAvail(m); } catch (e) { return false; } }); }
    function movesText() { let o = ''; st.log.forEach((e, i) => { if (i % 2 === 0) o += (i / 2 + 1) + '. '; o += e.san + ' '; }); return o.trim(); }

    // ---------------------------------------------------------------- motor (Stockfish) para ranking e analise
    function xhrText(url) { return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url); x.onload = () => ((x.status === 200 || x.status === 0) && x.responseText ? res(x.responseText) : rej(new Error('HTTP ' + x.status))); x.onerror = () => rej(new Error('rede')); x.send(); }); }
    async function makeWorker() {
        if (/^https?:/.test(location.protocol)) { try { const w = new Worker('libs/stockfish/stockfish.js'); return { w, kind: 'wasm' }; } catch (e) { /* tenta o asm.js */ } }
        const txt = await xhrText('libs/stockfish/stockfish.asm.js');   // no iPhone (arquivo local): o motor em JS puro, por um Worker de blob
        return { w: new Worker(URL.createObjectURL(new Blob([txt], { type: 'text/javascript' }))), kind: 'asm' };
    }
    async function getEngine() {
        if (engine) return engine;
        const { w, kind } = await makeWorker(), E = { w, kind, on: null };
        w.onmessage = e => { if (E.on) E.on(typeof e.data === 'string' ? e.data : String(e.data)); };
        const cmd = (c, until) => new Promise((res, rej) => { const t = setTimeout(() => { E.on = null; rej(new Error('o motor nao respondeu')); }, 30000); E.on = l => { if (until.test(l)) { clearTimeout(t); E.on = null; res(); } }; w.postMessage(c); });
        await cmd('uci', /uciok/); w.postMessage('setoption name MultiPV value 2'); await cmd('isready', /readyok/);
        engine = E; return E;
    }
    const wpct = cp => 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1);   // 0..100 (chance de ganhar), do ponto de vista de quem tem o cp positivo
    function analyze(fen, ms) {   // {best, lines:[{mv, cp}]} com cp do ponto de vista das BRANCAS (mate vira +-10000)
        if (st.an[fen]) return Promise.resolve(st.an[fen]);
        const job = engQ.then(async () => {
            if (st.an[fen]) return st.an[fen]; const E = await getEngine(), white = fen.split(' ')[1] === 'w';
            return new Promise((res, rej) => {
                const lines = {}, t = setTimeout(() => { E.on = null; rej(new Error('tempo esgotado')); }, 40000);
                E.on = l => {
                    if (l.startsWith('info') && / score (cp|mate) /.test(l) && / pv /.test(l)) { const pv = +((/ multipv (\d+)/.exec(l) || [0, 1])[1]), sc = / score (cp|mate) (-?\d+)/.exec(l), mv = (/ pv (\S+)/.exec(l) || [])[1]; let cp = sc[1] === 'cp' ? +sc[2] : (+sc[2] > 0 ? 10000 - +sc[2] : -10000 - +sc[2]); if (!white) cp = -cp; lines[pv] = { mv, cp, mate: sc[1] === 'mate' }; }
                    else if (l.startsWith('bestmove')) { clearTimeout(t); E.on = null; const arr = Object.keys(lines).sort().map(k => lines[k]); const r = { best: l.split(' ')[1], lines: arr }; st.an[fen] = r; res(r); }
                };
                E.w.postMessage('position fen ' + fen); E.w.postMessage('go movetime ' + (ms || 600));
            });
        });
        engQ = job.catch(() => { /* a fila segue */ }); return job;
    }
    function materialFor(color, g) { let s = 0; g.board().forEach(row => row.forEach(p => { if (p && p.color === color) s += PVAL[p.type]; })); return s; }
    function classify(i) {   // classifica o lance i (0 = primeiro) com a analise antes e depois
        const e = st.log[i], A = st.an[e.fen], afterFen = i + 1 < st.log.length ? st.log[i + 1].fen : game.fen(), B = st.an[afterFen];
        if (!A || !B || !A.lines.length || !B.lines.length || e.illegal) return null;
        const white = e.color === 'w', pov = cp => (white ? cp : -cp), bw = wpct(pov(A.lines[0].cp)), aw = wpct(pov(B.lines[0].cp)), loss = Math.max(0, bw - aw), best = e.uci === A.best;
        const second = A.lines[1] ? wpct(pov(A.lines[1].cp)) : null, onlyMove = best && second !== null && bw - second >= 15;
        const prev = i > 0 && st.cls[i - 1] ? st.cls[i - 1] : null, oppLoss = prev ? prev.loss : 0;
        let key;
        if (best || loss <= 0.5) key = 'best'; else if (loss <= 2) key = 'excellent'; else if (loss <= 5) key = 'good'; else if (loss <= 10) key = 'inaccuracy'; else if (loss <= 20) key = 'mistake'; else key = 'blunder';
        if (key !== 'blunder' && oppLoss >= 10 && loss >= 7) key = 'miss';
        if (best && onlyMove && bw < 92) key = 'great';
        if (loss <= 2 && bw < 90 && aw >= bw - 3) {   // sacrificio de peca que continua bom
            try { const g = new Chess(e.fen), before = materialFor(e.color, g) - materialFor(e.color === 'w' ? 'b' : 'w', g); g.move({ from: e.uci.slice(0, 2), to: e.uci.slice(2, 4), promotion: e.uci[4] }); const reply = B.best && B.best.length >= 4 ? B.best : null; if (reply) g.move({ from: reply.slice(0, 2), to: reply.slice(2, 4), promotion: reply[4] }); const after = materialFor(e.color, g) - materialFor(e.color === 'w' ? 'b' : 'w', g); if (before - after >= 2.5) key = 'brilliant'; } catch (x) { /* ignora */ }
        }
        return { key, loss, bw, aw };
    }

    // ---------------------------------------------------------------- jogo
    function newGame(o) {
        const human = o.color === 'random' ? (Math.random() < 0.5 ? 'w' : 'b') : o.color, opts = st ? st.opts : { illegal: false, rank: false };
        game = new Chess(); st = { human, model: o.model, flip: human === 'b', sel: null, targets: [], last: null, illegal: [], arrows: [], marks: [], thinking: false, over: '', note: '', rid: null, token: Math.random(), log: [], an: {}, cls: {}, opts, review: null, busy: '' };
        render(); if (human === 'b') aiMove();
    }
    function result() {
        if (game.in_checkmate()) return game.turn() === st.human ? T('Xeque-mate: o modelo ganhou.') : T('Xeque-mate: você ganhou!');
        if (game.in_stalemate()) return T('Empate por afogamento.');
        if (game.insufficient_material()) return T('Empate: material insuficiente.');
        if (game.in_threefold_repetition()) return T('Empate por repetição.');
        if (game.in_draw()) return T('Empate (regra dos 50 lances).');
        return '';
    }
    function pushLegal(fen0, mv) { st.log.push({ san: mv.san, uci: uciOf(mv), fen: fen0, color: mv.color, from: mv.from, to: mv.to }); st.last = { from: mv.from, to: mv.to }; st.illegal = []; }
    function forceMove(from, to, promo) {   // lance ILEGAL do modelo: edita o tabuleiro direto (a peca vai para la, sem checar regra)
        const piece = game.get(from); if (!piece || piece.color !== game.turn()) return null;
        const fen0 = game.fen(), parts = fen0.split(' '), grid = parts[0].split('/').map(r => { const row = []; for (const ch of r) { if (/\d/.test(ch)) for (let k = 0; k < +ch; k++) row.push(''); else row.push(ch); } return row; });
        const fx = FILES.indexOf(from[0]), fr = 8 - +from[1], tx = FILES.indexOf(to[0]), tr_ = 8 - +to[1]; const captured = grid[tr_][tx]; let ch = grid[fr][fx]; grid[fr][fx] = '';
        if (piece.type === 'p' && (to[1] === '8' || to[1] === '1')) ch = piece.color === 'w' ? (promo || 'q').toUpperCase() : (promo || 'q').toLowerCase();
        grid[tr_][tx] = ch; const placement = grid.map(r => { let o = '', n = 0; r.forEach(c => { if (!c) n++; else { if (n) { o += n; n = 0; } o += c; } }); return o + (n || ''); }).join('/');
        const next = piece.color === 'w' ? 'b' : 'w', full = +parts[5] + (piece.color === 'b' ? 1 : 0), newFen = `${placement} ${next} - - 0 ${full}`;
        st.log.push({ san: from + to + (promo || '') + '⚠', uci: from + to + (promo || ''), fen: fen0, color: piece.color, from, to, illegal: true });
        st.last = { from, to }; st.illegal = [from, to];
        if (/k/i.test(captured) && captured.toLowerCase() === 'k') { st.over = piece.color === st.human ? T('Você capturou o rei do modelo.') : T('O modelo capturou o seu rei (lance ilegal): o modelo ganhou.'); return { kingCaptured: true }; }
        if (!game.load(newFen)) { st.log.pop(); return null; } return { ok: true };
    }

    function render() {
        if (!ov) return;
        const rv = st.review, g = rv !== null && rv !== undefined ? new Chess(rv < st.log.length ? st.log[rv].fen : game.fen()) : game, b = g.board();
        const board = ov.querySelector('.chess-board'), kingSq = (() => { if (!g.in_check()) return null; for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) { const p = b[7 - r][f]; if (p && p.type === 'k' && p.color === g.turn()) return sqName(f, r); } return null; })();
        const last = rv !== null && rv !== undefined ? (rv > 0 ? { from: st.log[rv - 1].from, to: st.log[rv - 1].to } : null) : st.last, lastIdx = rv !== null && rv !== undefined ? rv - 1 : st.log.length - 1, lastCls = st.cls[lastIdx];
        board.querySelectorAll('.chess-sq').forEach(e => e.remove());
        for (let row = 0; row < 8; row++) for (let col = 0; col < 8; col++) {
            const f = st.flip ? 7 - col : col, r = st.flip ? row : 7 - row, name = sqName(f, r), p = b[7 - r][f], d = mk('div', 'chess-sq ' + ((f + r) % 2 === 0 ? 'd' : 'l')); d.dataset.sq = name;
            if (st.sel === name) d.classList.add('sel'); if (last && (last.from === name || last.to === name)) d.classList.add('last'); if (st.illegal.includes(name) && !rv && rv !== 0) d.classList.add('ill'); if (kingSq === name) d.classList.add('chk'); if (st.marks.includes(name)) d.classList.add('mark');
            if (st.targets.includes(name)) { d.classList.add('tgt'); if (p) d.classList.add('cap'); }
            if (p) d.appendChild(mk('span', 'chess-pc ' + p.color, GLYPH[p.type]));
            if (col === 0) d.appendChild(mk('span', 'chess-co r', String(r + 1))); if (row === 7) d.appendChild(mk('span', 'chess-co f', FILES[f]));
            if (lastCls && last && last.to === name && (st.opts.rank || rv !== null)) { const bd = mk('span', 'chess-badge', CLS[lastCls.key].sym); bd.style.background = CLS[lastCls.key].c; bd.title = T(CLS[lastCls.key].n) + ' (' + CLS[lastCls.key].en + ')'; d.appendChild(bd); }
            board.insertBefore(d, board.querySelector('.chess-arrows'));
        }
        drawArrows();
        const over = game.game_over() ? result() : st.over; st.over = over || st.over;
        const turnTxt = game.turn() === st.human ? T('Sua vez.') + (game.in_check() ? ' ' + T('Você está em xeque!') : '') : (st.thinking ? T('O modelo está pensando…') : T('Vez do modelo.'));
        let line = st.busy || (rv !== null && rv !== undefined ? '' : (st.over || turnTxt)) + (st.note ? ' ' + st.note : '');
        if (rv !== null && rv !== undefined) { const A = st.an[rv < st.log.length ? st.log[rv].fen : game.fen()]; line = (rv === 0 ? T('Posição inicial.') : T('Depois do lance') + ' ' + rv + ' (' + st.log[rv - 1].san + ')') + (lastCls ? ' · ' + T(CLS[lastCls.key].n) : '') + (A && A.lines[0] ? ' · ' + T('Melhor') + ': ' + sanOf(g, A.best) + ' (' + evalTxt(A.lines[0]) + ')' : ''); }
        else if (st.opts.rank && lastCls && !st.busy) line += ' · ' + T('Último lance') + ': ' + T(CLS[lastCls.key].n);
        ov.querySelector('.chess-status').textContent = line;
        const mv = ov.querySelector('.chess-moves'); mv.textContent = '';
        st.log.forEach((e, i) => {
            if (i % 2 === 0) mv.appendChild(document.createTextNode((i / 2 + 1) + '. '));
            const s = mk('span', 'mv' + (rv === i + 1 ? ' cur' : ''), e.san); s.onclick = () => { if (st.review !== null && st.review !== undefined) { st.review = i + 1; render(); } };
            mv.appendChild(s); const c = st.cls[i]; if (c && (st.opts.rank || rv !== null)) { const ic = mk('i', 'cl', CLS[c.key].sym); ic.style.color = CLS[c.key].c; ic.title = T(CLS[c.key].n); mv.appendChild(ic); } mv.appendChild(document.createTextNode(' '));
        });
        mv.scrollTop = mv.scrollHeight;
        const ev = ov.querySelector('.chess-eval'), curFen = rv !== null && rv !== undefined ? (rv < st.log.length ? st.log[rv].fen : game.fen()) : game.fen(), an = st.an[curFen];
        ev.classList.toggle('on', !!(st.opts.rank || (rv !== null && rv !== undefined)) && !!an); if (an && an.lines[0]) { ev.firstChild.style.height = wpct(an.lines[0].cp) + '%'; ev.lastChild.textContent = evalTxt(an.lines[0]); }
        ov.querySelector('.chess-sum').style.display = st.summary ? '' : 'none'; ov.querySelector('.chess-sum').textContent = st.summary || '';
        ov.querySelector('.chess-nav').style.display = rv !== null && rv !== undefined ? '' : 'none';
    }
    const evalTxt = l => (l.mate ? (l.cp > 0 ? '#' : '-#') : (l.cp >= 0 ? '+' : '') + (l.cp / 100).toFixed(1));
    function sanOf(g, uci) { try { const m = g.moves({ verbose: true }).find(x => uciOf(x) === uci); return m ? m.san : uci; } catch (e) { return uci; } }

    function drawArrows() {
        const svg = ov.querySelector('.chess-arrows'); svg.innerHTML = ''; let arrows = st.arrows.slice();
        if (st.review !== null && st.review !== undefined) { const fen = st.review < st.log.length ? st.log[st.review].fen : game.fen(), A = st.an[fen]; if (A && A.best && A.best.length >= 4) arrows.push({ from: A.best.slice(0, 2), to: A.best.slice(2, 4), color: '#3692e7' }); }
        const c = sq => { const { f, r } = sqXY(sq); return { x: (st.flip ? 7 - f : f) + 0.5, y: (st.flip ? r : 7 - r) + 0.5 }; };
        arrows.forEach(a => {
            const A = c(a.from), B = c(a.to), dx = B.x - A.x, dy = B.y - A.y, len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len, hw = 0.2, hl = 0.34, sx = A.x + ux * 0.28, sy = A.y + uy * 0.28, ex = B.x - ux * hl, ey = B.y - uy * hl;
            const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line'); ln.setAttribute('x1', sx); ln.setAttribute('y1', sy); ln.setAttribute('x2', ex); ln.setAttribute('y2', ey); ln.setAttribute('stroke', a.color); ln.setAttribute('stroke-width', '0.17'); ln.setAttribute('stroke-linecap', 'round'); ln.setAttribute('opacity', '0.85');
            const hd = document.createElementNS('http://www.w3.org/2000/svg', 'polygon'); hd.setAttribute('points', `${B.x - ux * 0.08},${B.y - uy * 0.08} ${ex - uy * hw},${ey + ux * hw} ${ex + uy * hw},${ey - ux * hw}`); hd.setAttribute('fill', a.color); hd.setAttribute('opacity', '0.85');
            svg.append(ln, hd);
        });
    }

    // ---------------------------------------------------------------- o modelo joga
    function parseMove(text, legal) {   // acha na resposta um lance da lista de lances legais
        const t = String(text || '').replace(/0-0-0/g, 'O-O-O').replace(/0-0/g, 'O-O').replace(/[`*_]/g, ' ');
        const toks = t.split(/[\s,;:()\[\]"'—]+/).map(x => x.replace(/^[.\d]+\.+/, '').replace(/[.!?]+$/, '')).filter(Boolean);
        const set = new Set(legal), strip = s => s.replace(/[+#]/g, '');
        for (const x of toks) if (set.has(x)) return x;
        for (const x of toks) { const m = legal.find(l => strip(l) === strip(x)); if (m) return m; }
        return null;
    }
    function parseCoord(text) { const m = /([a-h][1-8])\s*[-x:]?\s*([a-h][1-8])\s*=?\s*([qrbn])?/i.exec(String(text || '').toLowerCase()); return m ? { from: m[1], to: m[2], promo: m[3] || '' } : null; }
    async function askModel(messages, signal) {
        const m = st.model, rid = 'chess' + Date.now().toString(36); st.rid = rid;
        const r = await fetch(API + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, signal, body: JSON.stringify({ model: m.id, rid, messages, stream: true, think: false, effort: m.pol && m.effort ? 'none' : undefined, search_web: false, agent: false, lang: 'pt', num_ctx: m.cloud ? undefined : 4096 }) });
        if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
        const rd = r.body.getReader(), dec = new TextDecoder(); let buf = '', out = '';
        for (;;) {
            const { value, done } = await rd.read(); if (done) break; buf += dec.decode(value, { stream: true });
            let nl; while ((nl = buf.indexOf('\n')) >= 0) { const line = buf.slice(0, nl).trim(); buf = buf.slice(nl + 1); if (!line) continue; try { const o = JSON.parse(line); if (o.message && o.message.content) out += o.message.content; } catch (e) { /* linha parcial */ } }
        }
        return out;
    }
    async function aiMove() {
        if (!game || game.game_over() || st.over || game.turn() === st.human) return;
        const my = st.token; st.thinking = true; st.note = ''; render();
        const color = game.turn() === 'w' ? 'brancas' : 'pretas', legal = game.moves(), free = st.opts.illegal, fen0 = game.fen();
        const sys = free ? 'Você joga xadrez de verdade e quer ganhar. Em cada vez, responda SOMENTE com o seu lance em coordenadas (exemplos: e2e4, g1f3, e7e8q). Nada de explicação, nada de outro texto.'
            : 'Você joga xadrez de verdade e quer ganhar. Em cada vez, responda SOMENTE com um lance da lista de lances legais, exatamente como está escrito (notação SAN, por exemplo: Nf3, exd5, O-O, e8=Q). Nada de explicação, nada de outro texto.';
        const ask = extra => ([{ role: 'system', content: sys }, { role: 'user', content: `Posição (FEN): ${fen0}\nLances até agora: ${movesText() || '(nenhum, é o primeiro lance)'}\nVocê joga de ${color}.${free ? '' : '\nLances legais: ' + legal.join(', ')}\nResponda só com o seu lance.${extra || ''}` }]);
        let chosen = null, forced = null, extra = '', ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 180000);
        try {
            for (let i = 0; i < 3 && !chosen && !forced; i++) {
                const text = await askModel(ask(extra), ctl.signal); if (my !== st.token) return;
                if (/^\s*\[Erro/.test(text)) { st.note = text.trim().slice(0, 220); break; }
                chosen = parseMove(text, legal);
                if (!chosen && free) { const c = parseCoord(text), p = c && game.get(c.from); if (c && p && p.color === game.turn()) { const lg = game.moves({ verbose: true }).find(m => m.from === c.from && m.to === c.to && (!m.promotion || m.promotion === (c.promo || 'q'))); if (lg) chosen = lg.san; else forced = c; } }
                if (!chosen && !forced) extra = free ? `\nA sua resposta anterior ("${String(text).trim().slice(0, 40)}") não tinha um lance em coordenadas (ex.: e2e4) com uma peça sua na casa de origem. Tente de novo.` : `\nA sua resposta anterior ("${String(text).trim().slice(0, 40)}") não era um lance legal. Escolha exatamente um da lista: ${legal.join(', ')}`;
            }
        } catch (e) { if (my !== st.token) return; st.note = T('Não consegui falar com o modelo.'); }
        clearTimeout(to); if (my !== st.token) return;
        st.thinking = false;
        if (!chosen && !forced && !st.note) { chosen = legal[Math.floor(Math.random() * legal.length)]; st.note = T('(o modelo não respondeu um lance válido; joguei um lance qualquer por ele)'); }
        if (forced) { const r = forceMove(forced.from, forced.to, forced.promo); st.note = T('⚠ O modelo jogou um lance ILEGAL.'); if (!r) st.note = T('Lance ilegal sem efeito.'); }
        else if (chosen) { const mv = game.move(chosen); pushLegal(fen0, mv); }
        st.arrows = []; st.marks = []; render(); afterMove();
    }
    function afterMove() { if (st.opts.rank && !st.over) rankNow(); }
    async function rankNow() {   // ranking ao vivo: analisa a posicao nova e classifica o ultimo lance
        const my = st.token, n = st.log.length, fenAfter = game.fen(); if (!n) return;
        try { st.busy = T('Analisando o lance…'); render(); await analyze(st.log[n - 1].fen); await analyze(fenAfter); if (my !== st.token) return; const c = classify(n - 1); if (c) st.cls[n - 1] = c; st.busy = ''; }
        catch (e) { if (my !== st.token) return; st.busy = ''; st.note = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 80); st.opts.rank = false; const cb = ov && ov.querySelector('#chess-rank'); if (cb) cb.checked = false; }
        render();
    }
    function tryMove(from, to, promo) {
        const mv = game.moves({ verbose: true }).find(m => m.from === from && m.to === to && (!m.promotion || m.promotion === (promo || 'q')));
        if (!mv) return false;
        if (mv.promotion && !promo) { askPromo(from, to); return true; }
        const fen0 = game.fen(), done = game.move({ from, to, promotion: promo || undefined }); pushLegal(fen0, done); st.sel = null; st.targets = []; st.note = ''; render();
        if (!game.game_over()) { aiMove(); } afterMove(); return true;
    }
    function askPromo(from, to) {
        const box = mk('div', 'chess-promo'); ['q', 'r', 'b', 'n'].forEach(p => { const b = mk('button', '', GLYPH[p]); b.style.color = st.human === 'w' ? '#fff' : '#151515'; b.style.textShadow = st.human === 'w' ? '0 0 2px #000, 0 0 3px #000' : 'none'; b.onclick = e => { e.stopPropagation(); box.remove(); tryMove(from, to, p); }; box.appendChild(b); });
        ov.querySelector('.chess-board').appendChild(box);
    }
    function undo() {
        if (!game || st.thinking || !st.log.length) return; const e = st.log.pop(); game.load(e.fen); delete st.cls[st.log.length];
        if (game.turn() !== st.human && st.log.length) { const e2 = st.log.pop(); game.load(e2.fen); delete st.cls[st.log.length]; }
        st.over = ''; st.sel = null; st.targets = []; st.arrows = []; st.illegal = []; st.summary = ''; const l = st.log[st.log.length - 1]; st.last = l ? { from: l.from, to: l.to } : null; render();
    }

    // ---------------------------------------------------------------- analise da partida
    async function analyzeGame() {
        if (!game || st.thinking || !st.log.length) return; const my = st.token, fens = st.log.map(e => e.fen).concat(game.fen());
        try {
            for (let i = 0; i < fens.length; i++) { st.busy = T('Analisando a partida…') + ' ' + (i + 1) + '/' + fens.length; render(); await analyze(fens[i], 500); if (my !== st.token) return; }
        } catch (e) { st.busy = ''; st.note = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 80); render(); return; }
        st.cls = {}; for (let i = 0; i < st.log.length; i++) { const c = classify(i); if (c) st.cls[i] = c; }
        const cnt = { w: {}, b: {} }, acc = { w: [], b: [] }; st.log.forEach((e, i) => { const c = st.cls[i]; if (!c) return; cnt[e.color][c.key] = (cnt[e.color][c.key] || 0) + 1; acc[e.color].push(Math.max(0, 100 - c.loss * 1.2)); });
        const fmt = col => Object.keys(CLS).filter(k => cnt[col][k]).map(k => T(CLS[k].n) + ' ' + cnt[col][k]).join(' · ') || '—', avg = a => a.length ? Math.round(a.reduce((s, x) => s + x, 0) / a.length) + '%' : '—';
        const hw = st.human === 'w'; st.summary = T('Você') + ' (' + (hw ? T('brancas') : T('pretas')) + '): ' + avg(acc[st.human]) + ' — ' + fmt(st.human) + '\n' + T('Modelo') + ': ' + avg(acc[hw ? 'b' : 'w']) + ' — ' + fmt(hw ? 'b' : 'w');
        st.busy = ''; st.review = 0; render();
    }
    function nav(d) { if (st.review === null || st.review === undefined) return; st.review = Math.max(0, Math.min(st.log.length, d === 'end' ? st.log.length : d === 'start' ? 0 : st.review + d)); render(); }

    // ---------------------------------------------------------------- interface
    function wire(board) {
        const sqAt = e => { let s = e.pointerType !== 'touch' && e.target && e.target.closest ? e.target.closest('.chess-sq') : null; if (!s) { const el = document.elementFromPoint(e.clientX, e.clientY); s = el && el.closest('.chess-sq'); } return s ? s.dataset.sq : null; };
        let rstart = null, rcolor = '#15781B', press = null, lpress = null;
        board.addEventListener('contextmenu', e => e.preventDefault());
        board.addEventListener('mousedown', e => { if (e.button !== 2) return; rstart = sqAt(e); rcolor = e.shiftKey ? '#cc3333' : e.ctrlKey ? '#2d7be5' : e.altKey ? '#e5b82d' : '#15781B'; });
        board.addEventListener('mouseup', e => {
            if (e.button !== 2 || !rstart) return; const to = sqAt(e), from = rstart; rstart = null; if (!to) return;
            if (to === from) { st.marks = st.marks.includes(to) ? st.marks.filter(x => x !== to) : st.marks.concat(to); }
            else { const i = st.arrows.findIndex(a => a.from === from && a.to === to); if (i >= 0) st.arrows.splice(i, 1); else st.arrows.push({ from, to, color: rcolor }); }
            render();
        });
        board.addEventListener('pointerdown', e => { if (e.pointerType !== 'touch') return; const s = sqAt(e); press = setTimeout(() => { press = null; lpress = s; }, 380); });
        board.addEventListener('pointerup', e => { if (e.pointerType !== 'touch') return; if (press) { clearTimeout(press); press = null; } if (lpress) { const to = sqAt(e), from = lpress; lpress = null; if (to && to !== from) { st.arrows.push({ from, to, color: '#15781B' }); render(); } e.preventDefault(); } });
        board.addEventListener('click', e => {
            if (lpress) return; const s = sqAt(e); if (!s || st.thinking) return;
            if (st.arrows.length || st.marks.length) { st.arrows = []; st.marks = []; }
            if (st.review !== null && st.review !== undefined) { render(); return; }
            if (game.game_over() || st.over || game.turn() !== st.human) { render(); return; }
            if (st.sel && st.targets.includes(s)) { tryMove(st.sel, s); return; }
            const p = game.get(s); if (p && p.color === st.human) { st.sel = s; st.targets = game.moves({ square: s, verbose: true }).map(m => m.to); } else { st.sel = null; st.targets = []; }
            render();
        });
    }

    function open() {
        if (ov) return; if (typeof Chess === 'undefined') { alert('O xadrez não carregou.'); return; }
        const list = models(); if (!list.length) { alert(T('Nenhum modelo disponível agora. Configure uma chave ou ligue o Ollama.')); return; }
        ov = mk('div', 'chess-ov'); const wrap = mk('div', 'chess-wrap'); ov.appendChild(wrap);
        const bsz = Math.max(280, Math.min(560, innerWidth - 80, innerHeight - 120)); wrap.style.setProperty('--cb', bsz + 'px');
        const bw = mk('div', 'chess-bw'); wrap.appendChild(bw); const evb = mk('div', 'chess-eval'); evb.appendChild(mk('i')); evb.appendChild(mk('b')); bw.appendChild(evb);
        const board = mk('div', 'chess-board'); board.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'svg')); const svg = board.lastChild; svg.setAttribute('class', 'chess-arrows'); svg.setAttribute('viewBox', '0 0 8 8'); bw.appendChild(board);
        const side = mk('div', 'chess-side'); wrap.appendChild(side); side.appendChild(mk('h3', '', T('Xadrez contra um modelo')));
        const sel = document.createElement('select'); list.forEach((m, i) => { const o = document.createElement('option'); o.value = i; o.textContent = m.label || m.id; sel.appendChild(o); });
        const cur = list.findIndex(m => m.id === (typeof selectedModel !== 'undefined' ? selectedModel : '')); if (cur >= 0) sel.value = cur; side.appendChild(sel);
        const col = document.createElement('select'); [['w', 'Jogar de brancas'], ['b', 'Jogar de pretas'], ['random', 'Cor aleatória']].forEach(([v, l]) => { const o = document.createElement('option'); o.value = v; o.textContent = T(l); col.appendChild(o); }); side.appendChild(col);
        const opt = (id, label, key) => { const l = mk('label', 'chess-opt'), c = document.createElement('input'); c.type = 'checkbox'; c.id = id; c.onchange = () => { st.opts[key] = c.checked; if (key === 'rank') { if (c.checked) rankBackfill(); render(); } }; l.append(c, document.createTextNode(T(label))); side.appendChild(l); return c; };
        opt('chess-ill', 'Permitir lances ilegais do modelo', 'illegal'); opt('chess-rank', 'Ranking dos lances (Brilhante, Melhor, Erro…)', 'rank');
        const row = mk('div', 'chess-row'); side.appendChild(row);
        const btn = (txt, fn) => { const b = mk('button', 'btn btn-secondary', T(txt)); b.type = 'button'; b.onclick = fn; row.appendChild(b); return b; };
        const start = btn('Novo jogo', () => { if (st) st.token = Math.random(); newGame({ model: list[+sel.value], color: col.value }); }); start.classList.replace('btn-secondary', 'btn-primary');
        btn('Desfazer', undo); btn('Virar', () => { st.flip = !st.flip; render(); });
        btn('Desistir', () => { if (game && !game.game_over() && !st.over) { st.token = Math.random(); st.thinking = false; st.over = T('Você desistiu.'); render(); } });
        btn('Analisar partida', analyzeGame);
        btn('Fechar', () => { if (st) st.token = Math.random(); if (st && st.rid) { try { fetch(API + '/api/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rid: st.rid }) }); } catch (e) { /* ok */ } } ov.remove(); ov = null; });
        const navRow = mk('div', 'chess-row chess-nav'); [['⏮', 'start'], ['◀', -1], ['▶', 1], ['⏭', 'end']].forEach(([t, d]) => { const b = mk('button', 'btn btn-secondary', t); b.type = 'button'; b.onclick = () => nav(d); navRow.appendChild(b); }); const ex = mk('button', 'btn btn-secondary', T('Sair da análise')); ex.type = 'button'; ex.onclick = () => { st.review = null; render(); }; navRow.appendChild(ex); side.appendChild(navRow);
        side.appendChild(mk('div', 'chess-status', '')); side.appendChild(mk('div', 'chess-moves', '')); const sum = mk('div', 'chess-sum', ''); sum.style.whiteSpace = 'pre-line'; side.appendChild(sum);
        side.appendChild(mk('div', 'chess-hint', T('Botão direito: segure e arraste para desenhar uma seta (Shift vermelha, Ctrl azul, Alt amarela); clique direito numa casa marca a casa; clique esquerdo limpa. No celular: segure o dedo numa casa e arraste.')));
        wire(board); document.body.appendChild(ov);
        newGame({ model: list[+sel.value], color: 'w' });
    }
    async function rankBackfill() { for (let i = 0; i < st.log.length; i++) { if (st.cls[i]) continue; const my = st.token; try { await analyze(st.log[i].fen); await analyze(i + 1 < st.log.length ? st.log[i + 1].fen : game.fen()); if (my !== st.token) return; const c = classify(i); if (c) st.cls[i] = c; render(); } catch (e) { st.note = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 80); st.opts.rank = false; render(); return; } } }
    window.openChess = open;
    window.__chess = { get game() { return game; }, get st() { return st; }, parseMove, parseCoord, classify, analyze, wpct, forceMove };
})();
