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
        .chess-x { position: fixed; top: 44px; right: 14px; z-index: 2; width: 34px; height: 34px; border-radius: 50%; border: none; background: rgba(0,0,0,.55); color: #fff; font-size: 16px; line-height: 1; cursor: pointer; display: flex; align-items: center; justify-content: center; } .chess-x:hover { background: rgba(220,50,50,.85); }
        .chess-ov { position: fixed; inset: 36px 0 0 0; z-index: 6500; display: flex; align-items: flex-start; justify-content: center; background: rgba(0,0,0,0.6); padding: 12px; overflow: auto; } .chess-ov > .chess-wrap { margin: auto; }
        .chess-wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; justify-content: center; max-width: 100%; background: var(--bg-main); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 20px; padding: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.55); }
        .chess-bw { display: flex; gap: 8px; } .chess-eval { width: 14px; height: var(--cb, 520px); border-radius: 6px; overflow: hidden; background: #262522; position: relative; visibility: hidden; } .chess-eval.on { visibility: visible; } .chess-eval i { position: absolute; left: 0; right: 0; bottom: 0; background: #f2f2f2; transition: height .3s; } .chess-eval b { position: absolute; left: 0; right: 0; font: 600 9px system-ui; text-align: center; color: #888; top: 2px; }
        .chess-board { position: relative; width: var(--cb, 520px); height: var(--cb, 520px); display: grid; grid-template-columns: repeat(8, 1fr); grid-template-rows: repeat(8, 1fr); border-radius: 8px; overflow: hidden; user-select: none; -webkit-user-select: none; touch-action: none; }
        .chess-sq { position: relative; display: flex; align-items: center; justify-content: center; font-size: calc(var(--cb, 520px) / 8 * 0.78); line-height: 1; cursor: pointer; }
        .chess-sq.l { background: var(--cl, #eeeed2); } .chess-sq.d { background: var(--cd, #769656); }
        .chess-sq.sel { box-shadow: inset 0 0 0 4px rgba(255, 214, 10, .85); } .chess-sq.last { background-image: linear-gradient(rgba(255, 238, 90, .45), rgba(255, 238, 90, .45)); }
        .chess-sq.ill { background-image: linear-gradient(rgba(220, 60, 60, .45), rgba(220, 60, 60, .45)); }
        .chess-sq.chk { background-image: radial-gradient(circle, rgba(255, 40, 40, .9) 0%, rgba(255, 40, 40, 0) 70%); }
        .chess-sq.pre { background-image: linear-gradient(rgba(40, 120, 255, .5), rgba(40, 120, 255, .5)); }
        .chess-sq.mark { box-shadow: inset 0 0 0 100px rgba(235, 64, 52, .5); }
        .chess-sq.tgt::after { content: ''; position: absolute; width: 28%; height: 28%; border-radius: 50%; background: rgba(20, 20, 20, .28); }
        .chess-sq.tgt.cap::after { width: 86%; height: 86%; background: none; border: 5px solid rgba(20, 20, 20, .28); }
        .chess-pc { z-index: 1; pointer-events: none; } img.chess-pc { width: 92%; height: 92%; object-fit: contain; filter: drop-shadow(0 1px 1px rgba(0,0,0,.25)); } .chess-promo button img.chess-pc { width: 100%; height: 100%; } .chess-pc.w { color: #fff; text-shadow: 0 0 2px #000, 0 0 2px #000, 0 0 3px #000, 0 1px 3px rgba(0,0,0,.6); } .chess-pc.b { color: #151515; text-shadow: 0 0 1px #fff, 0 0 2px rgba(255,255,255,.5); }
        .chess-co { position: absolute; font: 600 10px system-ui, sans-serif; opacity: .65; pointer-events: none; color: #333; } .chess-co.r { top: 2px; left: 3px; } .chess-co.f { bottom: 1px; right: 3px; }
        .chess-badge { position: absolute; top: 2px; right: 2px; min-width: 1.5em; padding: 0 3px; height: 1.5em; border-radius: 999px; z-index: 2; display: flex; align-items: center; justify-content: center; font: 700 12px system-ui, sans-serif; color: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.5); pointer-events: none; }
        .chess-arrows { position: absolute; inset: 0; pointer-events: none; z-index: 3; }
        .chess-side { display: flex; flex-direction: column; gap: 10px; width: min(300px, 100%); }
        .chess-side h3 { margin: 0; } .chess-side select { width: 100%; } .chess-row { display: flex; flex-wrap: wrap; gap: 6px; } .chess-row .btn { margin: 0; padding: 8px 12px; flex: 1 1 auto; }
        .chess-opt { display: flex; gap: 8px; align-items: center; font-size: .88em; cursor: pointer; } .chess-opt input { width: auto; }
        .chess-status { padding: 10px 12px; border-radius: 12px; background: rgba(128,128,128,.14); font-size: .92em; min-height: 3.4em; }
        .chess-moves { height: 170px; flex: none; overflow-y: auto; font-size: .88em; line-height: 1.9; padding: 8px 10px; border-radius: 12px; background: rgba(128,128,128,.08); }
        .chess-moves span.mv { cursor: pointer; padding: 1px 4px; border-radius: 6px; } .chess-moves span.mv:hover { background: rgba(128,128,128,.25); } .chess-moves span.mv.cur { background: var(--accent); color: #fff; }
        .chess-moves i.cl { font-style: normal; font-weight: 700; font-size: .85em; margin-left: 1px; }
        .chess-sum { min-height: 3.6em; font-size: .82em; line-height: 1.5; padding: 8px 10px; border-radius: 12px; background: rgba(128,128,128,.08); }
        .chess-lk { flex: 1 1 45%; min-width: 0; padding: 7px 8px; border-radius: 10px; font-size: .85em; }
        .chess-hint { font-size: .76em; color: var(--text-muted); line-height: 1.4; }
        .chess-ov { animation: chFade .22s ease both; } .chess-ov.out { animation: chFadeOut .18s ease both; } .chess-wrap { animation: chPop .32s cubic-bezier(.2,.85,.25,1.05) both; } .chess-ov.out .chess-wrap { animation: chPopOut .18s ease both; }
        @keyframes chFade { from { opacity: 0; } to { opacity: 1; } } @keyframes chFadeOut { from { opacity: 1; } to { opacity: 0; } }
        @keyframes chPop { from { opacity: 0; transform: translateY(18px) scale(.96); } to { opacity: 1; transform: none; } } @keyframes chPopOut { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateY(10px) scale(.97); } }
        @media (prefers-reduced-motion: reduce) { .chess-ov, .chess-wrap { animation: none !important; } }
        .chess-tog { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 12px; border-radius: 12px; background: rgba(128,128,128,.10); font-size: .88em; cursor: pointer; }
        .chess-tog input { position: absolute; opacity: 0; pointer-events: none; } .chess-tog .sw { position: relative; flex: none; width: 38px; height: 22px; border-radius: 999px; background: rgba(128,128,128,.45); transition: background .2s; } .chess-tog .sw::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform .2s cubic-bezier(.3,.9,.3,1.2); box-shadow: 0 1px 3px rgba(0,0,0,.4); }
        .chess-tog input:checked + .sw { background: var(--accent); } .chess-tog input:checked + .sw::after { transform: translateX(16px); } .chess-tog input:focus-visible + .sw { outline: 2px solid var(--accent); outline-offset: 2px; }
        .chess-seg { display: flex; padding: 3px; border-radius: 12px; background: rgba(128,128,128,.14); gap: 2px; } .chess-seg button { flex: 1; border: 0; background: transparent; color: var(--text-muted); padding: 8px 6px; border-radius: 9px; cursor: pointer; font-size: .86em; transition: background .2s, color .2s; } .chess-seg button.on { background: var(--bg-main); color: var(--text-main); box-shadow: 0 1px 4px rgba(0,0,0,.3); }
        .chess-side .custom-select { position: relative; height: auto; display: block; } .chess-side .select-trigger { height: 42px; box-sizing: border-box; } .chess-side .select-options { position: absolute; top: calc(100% + 6px); bottom: auto; left: 0; right: 0; width: auto; min-width: 0; margin: 0; max-height: min(460px, 62vh); z-index: 30; box-shadow: 0 14px 40px rgba(0,0,0,.5); } .chess-side .select-options .mo-list { max-height: 240px; }
        .cm-wrap { position: relative; } .cm-btn { width: 100%; display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 12px; border: 1px solid var(--border-color); background: rgba(128,128,128,.10); color: var(--text-main); cursor: pointer; text-align: left; font-size: .92em; transition: border-color .2s, background .2s; } .cm-btn:hover, .cm-btn.on { border-color: var(--accent); background: rgba(128,128,128,.16); }
        .cm-logo { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; flex: none; } .cm-logo > * { max-height: 20px; max-width: 22px; height: 20px; display: inline-block; object-fit: contain; }
        .cm-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; } .cm-prov { font-size: .8em; color: var(--text-muted); white-space: nowrap; } .cm-car { color: var(--text-muted); transition: transform .2s; } .cm-btn.on .cm-car { transform: rotate(180deg); }
        .cm-pop { position: absolute; z-index: 20; left: 0; right: 0; top: calc(100% + 6px); display: none; flex-direction: column; background: var(--bg-input, var(--bg-main)); border: 1px solid var(--border-color); border-radius: 14px; box-shadow: 0 14px 40px rgba(0,0,0,.5); overflow: hidden; } .cm-pop.on { display: flex; animation: chPop .2s cubic-bezier(.2,.85,.25,1.05) both; transform-origin: top; }
        .cm-pop input { margin: 8px; width: calc(100% - 16px); } .cm-list { overflow-y: auto; max-height: min(340px, 48vh); padding-bottom: 6px; }
        .cm-grp { position: sticky; top: 0; padding: 6px 12px 4px; font-size: .68em; letter-spacing: .1em; text-transform: uppercase; color: var(--text-muted); background: var(--bg-input, var(--bg-main)); } .cm-row { display: flex; align-items: center; gap: 10px; padding: 8px 12px; cursor: pointer; font-size: .9em; } .cm-row:hover { background: rgba(128,128,128,.16); } .cm-row.on { background: color-mix(in srgb, var(--accent) 22%, transparent); } .cm-row .cm-name { font-weight: 500; }
        .chess-promo { position: absolute; inset: 0; z-index: 5; display: flex; align-items: center; justify-content: center; gap: 8px; background: rgba(0,0,0,.55); }
        .chess-promo button { font-size: 2.4em; width: 1.5em; height: 1.5em; border-radius: 12px; border: 0; background: #ecd9b4; cursor: pointer; }`;
    document.head.appendChild(css);

    const sqName = (f, r) => FILES[f] + (r + 1);
    const sqXY = sq => ({ f: FILES.indexOf(sq[0]), r: +sq[1] - 1 });
    const mk = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
    const uciOf = m => m.from + m.to + (m.promotion || '');
    function models() { return (typeof MODELS !== 'undefined' ? MODELS : []).filter(m => { try { return isAvail(m); } catch (e) { return false; } }); }   // qualquer modelo disponivel, de qualquer aba
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
        w.onerror = () => { if (engine === E) engine = null; if (E.fail) E.fail(new Error('o motor caiu')); };
        w.onmessage = e => { if (E.on) E.on(typeof e.data === 'string' ? e.data : String(e.data)); };
        const cmd = E.cmd = (c, until, ms) => new Promise((res, rej) => { const t = setTimeout(() => { E.on = null; rej(new Error('o motor nao respondeu')); }, ms || 30000); E.on = l => { if (until.test(l)) { clearTimeout(t); E.on = null; res(); } }; w.postMessage(c); });
        await cmd('uci', /uciok/); w.postMessage('setoption name MultiPV value 2'); await cmd('isready', /readyok/);
        engine = E; return E;
    }
    const wpct = cp => 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * cp)) - 1);   // 0..100 (chance de ganhar), do ponto de vista de quem tem o cp positivo
    function fenSafe(fen) {   // lance ilegal do modelo pode deixar uma posicao impossivel (sem rei, reis colados, quem acabou de jogar em xeque...): o Stockfish cai com isso
        try {
            const parts = fen.split(' '), rows = parts[0].split('/'); if (rows.length !== 8) return false;
            const flat = rows.map(r => r.replace(/\d/g, m => '.'.repeat(+m))); if (flat.some(r => r.length !== 8)) return false;
            const all = flat.join(''); if ((all.match(/K/g) || []).length !== 1 || (all.match(/k/g) || []).length !== 1) return false;
            if (/[Pp]/.test(flat[0] + flat[7])) return false;
            const ki = all.indexOf('K'), kj = all.indexOf('k'); if (Math.abs((ki >> 3) - (kj >> 3)) <= 1 && Math.abs((ki & 7) - (kj & 7)) <= 1) return false;
            const other = new Chess([parts[0], parts[1] === 'w' ? 'b' : 'w', '-', '-', '0', '1'].join(' ')); if (other.in_check()) return false;   // o lado que nao joga nao pode estar em xeque
            return !!new Chess(fen).fen();
        } catch (e) { return false; }
    }
    function analyze(fen, ms) {   // {best, lines:[{mv, cp}]} com cp do ponto de vista das BRANCAS (mate vira +-10000)
        if (st.an[fen]) return Promise.resolve(st.an[fen]);
        if (!fenSafe(fen)) return Promise.resolve(st.an[fen] = { best: '', lines: [], bad: true });   // posicao impossivel: nao manda para o motor
        const job = engQ.then(async () => {
            if (st.an[fen]) return st.an[fen]; const E = await getEngine(), white = fen.split(' ')[1] === 'w', S = st;
            E.w.postMessage('stop'); await E.cmd('isready', /readyok/, 8000);   // descarta qualquer busca antiga que ainda estivesse rodando
            return new Promise((res, rej) => {
                const lines = {}; E.fail = err => { clearTimeout(t); E.on = null; E.fail = null; rej(err); }; const t = setTimeout(() => { E.on = null; try { E.w.terminate(); } catch (x) { /* ok */ } if (engine === E) engine = null; rej(new Error('tempo esgotado')); }, 15000);   // travou: joga o motor fora, o proximo recria
                E.on = l => {
                    if (l.startsWith('info') && / score (cp|mate) /.test(l) && / pv /.test(l)) { const pv = +((/ multipv (\d+)/.exec(l) || [0, 1])[1]), sc = / score (cp|mate) (-?\d+)/.exec(l), mv = (/ pv (\S+)/.exec(l) || [])[1]; let cp = sc[1] === 'cp' ? +sc[2] : (+sc[2] > 0 ? 10000 - +sc[2] : -10000 - +sc[2]); if (!white) cp = -cp; lines[pv] = { mv, cp, mate: sc[1] === 'mate' }; }
                    else if (l.startsWith('bestmove')) { clearTimeout(t); E.on = null; E.fail = null; const arr = Object.keys(lines).sort().map(k => lines[k]); const r = { best: l.split(' ')[1], lines: arr }; S.an[fen] = r; res(r); }
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
        const human = o.color === 'random' ? (Math.random() < 0.5 ? 'w' : 'b') : o.color, opts = st ? st.opts : { illegal: false, rank: false, noSpawn: true };
        game = new Chess(); st = { human, model: o.model, flip: human === 'b', sel: null, targets: [], last: null, illegal: [], arrows: [], marks: [], thinking: false, over: '', note: '', rid: null, token: Math.random(), log: [], an: {}, cls: {}, opts, review: null, busy: '', rk: 0, pre: null, psel: null };
        render(); if (human === 'b') aiMove();
    }
    function mateOk() {   // xeque-mate de verdade: posicao possivel e quem da o mate tem alguma peca alem do rei
        if (!game.in_checkmate() || !fenSafe(game.fen())) return false; const winner = game.turn() === 'w' ? 'b' : 'w';
        return game.board().some(row => row.some(p => p && p.color === winner && p.type !== 'k'));
    }
    function result() {
        if (game.in_checkmate() && !mateOk()) return T('Empate: material insuficiente.');
        if (game.in_checkmate()) return game.turn() === st.human ? T('Xeque-mate: o modelo ganhou.') : T('Xeque-mate: você ganhou!');
        if (game.in_stalemate()) return T('Empate por afogamento.');
        if (game.insufficient_material()) return T('Empate: material insuficiente.');
        if (game.in_threefold_repetition()) return T('Empate por repetição.');
        if (game.in_draw()) return T('Empate (regra dos 50 lances).');
        return '';
    }
    function pushLegal(fen0, mv) { st.log.push({ san: mv.san, uci: uciOf(mv), fen: fen0, color: mv.color, from: mv.from, to: mv.to }); st.last = { from: mv.from, to: mv.to }; st.illegal = []; }
    function rightsAfter(rights, grid) {   // so mantem o roque se o rei e a torre ainda estao nas casas de origem
        const ok = { K: grid[7][4] === 'K' && grid[7][7] === 'R', Q: grid[7][4] === 'K' && grid[7][0] === 'R', k: grid[0][4] === 'k' && grid[0][7] === 'r', q: grid[0][4] === 'k' && grid[0][0] === 'r' };
        return [...(rights === '-' ? '' : rights)].filter(c => ok[c]).join('') || '-';
    }
    function forceMove(from, to, promo) {   // lance ILEGAL do modelo: edita o tabuleiro direto (a peca vai para la, sem checar regra)
        const piece = game.get(from); if (!piece || piece.color !== game.turn()) return null;
        const fen0 = game.fen(), parts = fen0.split(' '), grid = parts[0].split('/').map(r => { const row = []; for (const ch of r) { if (/\d/.test(ch)) for (let k = 0; k < +ch; k++) row.push(''); else row.push(ch); } return row; });
        const fx = FILES.indexOf(from[0]), fr = 8 - +from[1], tx = FILES.indexOf(to[0]), tr_ = 8 - +to[1]; const captured = grid[tr_][tx]; let ch = grid[fr][fx]; grid[fr][fx] = '';
        if (piece.type === 'p' && (to[1] === '8' || to[1] === '1')) ch = piece.color === 'w' ? (promo || 'q').toUpperCase() : (promo || 'q').toLowerCase();
        grid[tr_][tx] = ch; const placement = grid.map(r => { let o = '', n = 0; r.forEach(c => { if (!c) n++; else { if (n) { o += n; n = 0; } o += c; } }); return o + (n || ''); }).join('/');
        const next = piece.color === 'w' ? 'b' : 'w', full = +parts[5] + (piece.color === 'b' ? 1 : 0), newFen = `${placement} ${next} ${rightsAfter(parts[2], grid)} - 0 ${full}`;
        st.log.push({ san: from + to + (promo || '') + '⚠', uci: from + to + (promo || ''), fen: fen0, color: piece.color, from, to, illegal: true });
        st.last = { from, to }; st.illegal = [from, to];
        if (captured && captured.toLowerCase() === 'k') { st.log.pop(); return null; }
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
            if (st.sel === name || st.psel === name) d.classList.add('sel'); if (st.pre && (st.pre.from === name || st.pre.to === name)) d.classList.add('pre'); if (last && (last.from === name || last.to === name)) d.classList.add('last'); if (st.illegal.includes(name) && !rv && rv !== 0) d.classList.add('ill'); if (kingSq === name) d.classList.add('chk'); if (st.marks.includes(name)) d.classList.add('mark');
            if (st.targets.includes(name)) { d.classList.add('tgt'); if (p) d.classList.add('cap'); }
            if (p) d.appendChild(pieceEl(p));
            if (col === 0) d.appendChild(mk('span', 'chess-co r', String(r + 1))); if (row === 7) d.appendChild(mk('span', 'chess-co f', FILES[f]));
            if (lastCls && last && last.to === name && (st.opts.rank || rv !== null)) { const bd = mk('span', 'chess-badge', CLS[lastCls.key].sym); bd.style.background = CLS[lastCls.key].c; bd.title = T(CLS[lastCls.key].n) + ' (' + CLS[lastCls.key].en + ')'; d.appendChild(bd); }
            board.insertBefore(d, board.querySelector('.chess-arrows'));
        }
        drawArrows();
        const over = game.game_over() ? result() : st.over; st.over = over || st.over;
        const turnTxt = game.turn() === st.human ? T('Sua vez.') + (game.in_check() ? ' ' + T('Você está em xeque!') : '') : (st.thinking ? T('O modelo está pensando…') : T('Vez do modelo.'));
        let line = st.busy || (st.rk > 0 && rv === null ? T('Analisando o lance…') : '') || (rv !== null && rv !== undefined ? '' : (st.over || turnTxt)) + (st.note ? ' ' + st.note : '');
        if (rv !== null && rv !== undefined) { const A = st.an[rv < st.log.length ? st.log[rv].fen : game.fen()]; line = (rv === 0 ? T('Posição inicial.') : T('Depois do lance') + ' ' + rv + ' (' + st.log[rv - 1].san + ')') + (lastCls ? ' · ' + T(CLS[lastCls.key].n) : '') + (A && A.lines[0] ? ' · ' + T('Melhor') + ': ' + sanOf(g, A.best) + ' (' + evalTxt(A.lines[0]) + ')' : ''); }
        else if (st.opts.rank && lastCls && !st.busy && !st.rk) line += ' · ' + T('Último lance') + ': ' + T(CLS[lastCls.key].n);
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
        ov.querySelector('.chess-sum').style.visibility = st.summary ? 'visible' : 'hidden'; ov.querySelector('.chess-sum').textContent = st.summary || ' ';
        ov.querySelector('.chess-nav').style.visibility = rv !== null && rv !== undefined ? 'visible' : 'hidden';
    }
    const BOARDS = { green: ['Verde', '#ebecd0', '#779556'], brown: ['Marrom', '#f0d9b5', '#b58863'], blue: ['Azul', '#dee3e6', '#8ca2ad'], gray: ['Cinza', '#e8e8e8', '#9aa0a6'], purple: ['Roxo', '#e6dff0', '#8877b3'], wood: ['Madeira', '#ecd9b4', '#ae8a68'], night: ['Noite', '#8d99ae', '#2b2d42'] };
    const SET_NAMES = { cardinal: 'Cardinal', caliente: 'Caliente', california: 'California', chessnut: 'Chessnut', fresca: 'Fresca', gioco: 'Gioco', icpieces: 'IC Pieces', kosal: 'Kosal', maestro: 'Maestro', merida: 'Mérida', rhosgfx: 'RhosGFX', staunty: 'Staunty', tatiana: 'Tatiana', cburnett: 'Clássico (Lichess)' };
    const LOOK_KEY = 'lume_chess_look'; let look = (() => { try { return Object.assign({ set: 'cardinal', board: 'green' }, JSON.parse(localStorage.getItem(LOOK_KEY) || '{}')); } catch (e) { return { set: 'cardinal', board: 'green' }; } })();
    const saveLook = () => { try { localStorage.setItem(LOOK_KEY, JSON.stringify(look)); } catch (e) { /* sem armazenamento */ } };
    function applyBoard() { const b = BOARDS[look.board] || BOARDS.green, bd = ov && ov.querySelector('.chess-board'); if (bd) { bd.style.setProperty('--cl', b[1]); bd.style.setProperty('--cd', b[2]); } }
    function pieceEl(p) { const set = (window.CHESS_SETS && (window.CHESS_SETS[look.set] || window.CHESS_SETS.cburnett)) || window.CHESS_PIECES, src = set && set[p.color + p.type.toUpperCase()]; if (!src) return mk('span', 'chess-pc ' + p.color, GLYPH[p.type]); const im = document.createElement('img'); im.className = 'chess-pc'; im.src = src; im.alt = ''; im.draggable = false; return im; }
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
    function parseSpawn(text) { const m = /\+\s*([qrbnp])\s*@\s*([a-h][1-8])/i.exec(String(text || '')); return m ? { type: m[1].toLowerCase(), sq: m[2] } : null; }
    function spawnPiece(type, sq) {   // lance ILEGAL: cria uma peca do modelo numa casa (nao vale rei nem peao na ultima fileira)
        const color = game.turn(), cur = game.get(sq); if ((cur && (cur.color === color || cur.type === 'k')) || (type === 'p' && (sq[1] === '1' || sq[1] === '8'))) return null;
        const fen0 = game.fen(), parts = fen0.split(' '), grid = parts[0].split('/').map(r => { const row = []; for (const ch of r) { if (/\d/.test(ch)) for (let k = 0; k < +ch; k++) row.push(''); else row.push(ch); } return row; });
        const x = FILES.indexOf(sq[0]), y = 8 - +sq[1], captured = grid[y][x]; grid[y][x] = color === 'w' ? type.toUpperCase() : type;
        const placement = grid.map(r => { let o = '', n = 0; r.forEach(c => { if (!c) n++; else { if (n) { o += n; n = 0; } o += c; } }); return o + (n || ''); }).join('/');
        const next = color === 'w' ? 'b' : 'w', full = +parts[5] + (color === 'b' ? 1 : 0), newFen = `${placement} ${next} ${rightsAfter(parts[2], grid)} - 0 ${full}`;
        st.log.push({ san: '+' + type.toUpperCase() + '@' + sq + '⚠', uci: '+' + type + '@' + sq, fen: fen0, color, from: sq, to: sq, illegal: true });
        st.last = { from: sq, to: sq }; st.illegal = [sq];

        if (!game.load(newFen)) { st.log.pop(); return null; } return { ok: true };
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
        const sys = free ? 'Você joga xadrez de verdade e quer ganhar. Em cada vez, responda SOMENTE com o seu lance em coordenadas (exemplos: e2e4, g1f3, e7e8q). Nada de explicação, nada de outro texto.' + (st.opts.noSpawn ? '' : ' Em vez de mover, você também pode CRIAR uma peça sua do nada numa casa, escrevendo +peça@casa (exemplo: +Q@d5 cria uma dama sua em d5).')
            : 'Você joga xadrez de verdade e quer ganhar. Em cada vez, responda SOMENTE com um lance da lista de lances legais, exatamente como está escrito (notação SAN, por exemplo: Nf3, exd5, O-O, e8=Q). Nada de explicação, nada de outro texto.';
        const ask = extra => ([{ role: 'system', content: sys }, { role: 'user', content: `Posição (FEN): ${fen0}\nLances até agora: ${movesText() || '(nenhum, é o primeiro lance)'}\nVocê joga de ${color}.${free ? '' : '\nLances legais: ' + legal.join(', ')}\nResponda só com o seu lance.${extra || ''}` }]);
        let chosen = null, forced = null, spawn = null, err = false, extra = '', ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 180000);
        try {
            for (let i = 0; i < 3 && !chosen && !forced && !spawn; i++) {
                const text = await askModel(ask(extra), ctl.signal); if (my !== st.token) return;
                if (/^\s*\[Erro/.test(text)) { st.note = text.trim().slice(0, 220); err = true; break; }
                chosen = parseMove(text, legal);
                if (!chosen && free) { const sp = parseSpawn(text); if (sp) { if (st.opts.noSpawn) { extra = '\nCriar peças do nada está BLOQUEADO. Mova uma peça que já está no tabuleiro.'; continue; } const cur = game.get(sp.sq); if ((cur && (cur.color === game.turn() || cur.type === 'k')) || (sp.type === 'p' && (sp.sq[1] === '1' || sp.sq[1] === '8'))) { extra = '\nEssa casa não serve para criar a peça. Escolha outra.'; continue; } spawn = sp; break; } }
                if (!chosen && free) { const c = parseCoord(text), p = c && game.get(c.from); if (c && p && p.color === game.turn()) { const lg = game.moves({ verbose: true }).find(m => m.from === c.from && m.to === c.to && (!m.promotion || m.promotion === (c.promo || 'q'))), tg = game.get(c.to); if (lg) chosen = lg.san; else if (tg && tg.type === 'k') { extra = '\nO rei não pode ser capturado: a partida só acaba por xeque-mate. Escolha outro lance.'; continue; } else forced = c; } }
                if (!chosen && !forced && !spawn) extra = free ? `\nA sua resposta anterior ("${String(text).trim().slice(0, 40)}") não tinha um lance em coordenadas (ex.: e2e4) com uma peça sua na casa de origem. Tente de novo.` : `\nA sua resposta anterior ("${String(text).trim().slice(0, 40)}") não era um lance legal. Escolha exatamente um da lista: ${legal.join(', ')}`;
            }
        } catch (e) { if (my !== st.token) return; st.note = T('Não consegui falar com o modelo.'); err = true; }
        clearTimeout(to); if (my !== st.token) return;
        st.thinking = false;
        if (!chosen && !forced && !spawn && !err) { chosen = legal[Math.floor(Math.random() * legal.length)]; st.note = T('(o modelo não respondeu um lance válido; joguei um lance qualquer por ele)'); }
        if (spawn) { const r = spawnPiece(spawn.type, spawn.sq); st.note = r ? T('⚠ O modelo CRIOU uma peça do nada.') : T('Lance ilegal sem efeito.'); if (!r) { const rnd = legal[Math.floor(Math.random() * legal.length)]; const mv = game.move(rnd); pushLegal(fen0, mv); } }
        else if (forced) { const r = forceMove(forced.from, forced.to, forced.promo); st.note = T('⚠ O modelo jogou um lance ILEGAL.'); if (!r) { st.note = T('Lance ilegal sem efeito.'); const rnd = legal[Math.floor(Math.random() * legal.length)]; const mv = game.move(rnd); pushLegal(fen0, mv); } }
        else if (chosen) { const mv = game.move(chosen); pushLegal(fen0, mv); }
        st.arrows = []; st.marks = []; render(); afterMove(); runPremove();
    }
    function runPremove() {   // jogada adiantada: executa assim que o modelo responde, se ainda for legal
        const p = st.pre; st.pre = null; st.psel = null; if (!p || game.game_over() || st.over || game.turn() !== st.human) { render(); return; }
        const mv = game.moves({ verbose: true }).find(m => m.from === p.from && m.to === p.to); if (!mv) { render(); return; }
        tryMove(p.from, p.to, mv.promotion ? 'q' : undefined);
    }
    function afterMove() { if (st.opts.rank && !st.over) rankNow(); }
    async function rankNow() {   // ranking ao vivo: analisa a posicao nova e classifica o ultimo lance
        const S = st, my = S.token, n = S.log.length, fenAfter = game.fen(); if (!n) return;
        const fenBefore = S.log[n - 1].fen; S.rk = (S.rk || 0) + 1; render();
        try { await analyze(fenBefore); await analyze(fenAfter); if (my === S.token) { const c = classify(n - 1); if (c) S.cls[n - 1] = c; } }
        catch (e) { if (my === S.token) { S.note = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 80); S.opts.rank = false; const cb = ov && ov.querySelector('#chess-rank'); if (cb) cb.checked = false; } }
        finally { S.rk = Math.max(0, S.rk - 1); if (st === S) render(); }
    }
    function tryMove(from, to, promo) {
        const mv = game.moves({ verbose: true }).find(m => m.from === from && m.to === to && (!m.promotion || m.promotion === (promo || 'q')));
        if (!mv) return false;
        if (mv.promotion && !promo) { askPromo(from, to); return true; }
        const fen0 = game.fen(), done = game.move({ from, to, promotion: promo || undefined }); pushLegal(fen0, done); st.sel = null; st.targets = []; st.note = ''; render();
        if (!game.game_over()) { aiMove(); } afterMove(); return true;
    }
    function askPromo(from, to) {
        const box = mk('div', 'chess-promo'); ['q', 'r', 'b', 'n'].forEach(p => { const b = mk('button', ''); b.appendChild(pieceEl({ color: st.human, type: p })); b.style.color = st.human === 'w' ? '#fff' : '#151515'; b.style.textShadow = st.human === 'w' ? '0 0 2px #000, 0 0 3px #000' : 'none'; b.onclick = e => { e.stopPropagation(); box.remove(); tryMove(from, to, p); }; box.appendChild(b); });
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
        } catch (e) { if (my !== st.token) return; st.busy = ''; st.note = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 80); render(); return; }
        st.cls = {}; for (let i = 0; i < st.log.length; i++) { const c = classify(i); if (c) st.cls[i] = c; }
        const cnt = { w: {}, b: {} }, acc = { w: [], b: [] }; st.log.forEach((e, i) => { const c = st.cls[i]; if (!c) return; cnt[e.color][c.key] = (cnt[e.color][c.key] || 0) + 1; acc[e.color].push(Math.max(0, 100 - c.loss * 1.2)); });
        const fmt = col => Object.keys(CLS).filter(k => cnt[col][k]).map(k => T(CLS[k].n) + ' ' + cnt[col][k]).join(' · ') || '—', avg = a => a.length ? Math.round(a.reduce((s, x) => s + x, 0) / a.length) + '%' : '—';
        const hw = st.human === 'w'; st.summary = T('Você') + ' (' + (hw ? T('brancas') : T('pretas')) + '): ' + avg(acc[st.human]) + ' — ' + fmt(st.human) + '\n' + T('Modelo') + ': ' + avg(acc[hw ? 'b' : 'w']) + ' — ' + fmt(hw ? 'b' : 'w');
        st.busy = ''; st.review = 0; render();
    }
    function pgnText() {   // PGN padrao; lances ilegais do modelo nao existem no PGN, entao viram comentario e a FEN final vai no cabecalho
        const d = new Date(), pad = n => String(n).padStart(2, '0'), me = st.human === 'w', mdl = st.model.label || st.model.id, over = st.over || '';
        let res = '*'; if (game.in_checkmate()) res = game.turn() === 'w' ? '0-1' : '1-0'; else if (game.in_draw() || game.in_stalemate()) res = '1/2-1/2'; else if (/desistiu|modelo ganhou/i.test(over)) res = me ? '0-1' : '1-0'; else if (/você capturou|você ganhou/i.test(over)) res = me ? '1-0' : '0-1';
        const hasIll = st.log.some(e => e.illegal), H = { Event: 'Lume: Xadrez contra um modelo', Site: 'Lume', Date: d.getFullYear() + '.' + pad(d.getMonth() + 1) + '.' + pad(d.getDate()), Round: '1', White: me ? 'Voce' : mdl, Black: me ? mdl : 'Voce', Result: res };
        if (hasIll) { H.SetUp = '1'; H.FEN = game.fen(); H.Variant = 'Lume (lances ilegais)'; }
        let mt = '', prevIll = false;
        st.log.forEach((e, i) => { const w = i % 2 === 0, no = Math.floor(i / 2) + 1; mt += (w ? no + '. ' : (prevIll || i === 0 ? no + '... ' : '')) + (e.illegal ? '{lance ILEGAL ' + e.san.replace('⚠', '') + '} ' : e.san + ' '); prevIll = !!e.illegal; });
        return Object.keys(H).map(k => '[' + k + ' "' + String(H[k]).replace(/"/g, "'") + '"]').join('\n') + '\n\n' + mt.trim() + ' ' + res + '\n';
    }
    function exportPgn() {
        if (!game || !st.log.length) { st.note = T('Jogue pelo menos um lance para exportar.'); render(); return; }
        const txt = pgnText(); let msg = '';
        try { if (navigator.clipboard) navigator.clipboard.writeText(txt); msg = T('PGN copiado.'); } catch (e) { /* sem area de transferencia */ }
        try { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([txt], { type: 'application/x-chess-pgn' })); a.download = 'lume-partida.pgn'; document.body.appendChild(a); a.click(); setTimeout(() => { a.remove(); URL.revokeObjectURL(a.href); }, 500); msg += ' ' + T('Arquivo lume-partida.pgn baixado.'); } catch (e) { /* ok */ }
        st.note = msg.trim(); render();
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
        const act = s => {
            if (st.review === null || st.review === undefined) {
                if (st.thinking && !game.game_over() && !st.over) {   // vez do modelo: clique monta uma jogada adiantada
                    const p = game.get(s);
                    if (st.psel && s !== st.psel) { st.pre = { from: st.psel, to: s }; st.psel = null; }
                    else if (p && p.color === st.human && s !== st.psel) { st.psel = s; st.pre = null; }
                    else { st.psel = null; st.pre = null; }
                    render(); return;
                }
                if (!st.thinking && !game.game_over() && !st.over && game.turn() !== st.human) { aiMove(); return; }   // o modelo nao jogou (erro): clicar tenta de novo
            }
            if (st.thinking) return;
            if (st.arrows.length || st.marks.length) { st.arrows = []; st.marks = []; }
            if (st.review !== null && st.review !== undefined) { render(); return; }
            if (game.game_over() || st.over || game.turn() !== st.human) { render(); return; }
            if (st.sel && st.targets.includes(s)) { tryMove(st.sel, s); return; }
            const selP = st.sel && game.get(st.sel), clk = game.get(s);
            if (selP && selP.type === 'k' && clk && clk.type === 'r' && clk.color === selP.color) { const dest = (s[0] > st.sel[0] ? 'g' : 'c') + st.sel[1]; if (st.targets.includes(dest)) { tryMove(st.sel, dest); return; } }   // clicar na propria torre = roque
            const p = game.get(s); if (p && p.color === st.human) { st.sel = s; st.targets = game.moves({ square: s, verbose: true }).map(m => m.to); } else { st.sel = null; st.targets = []; }
            render();
        };
        let drag = null, noClick = 0;
        board.addEventListener('click', e => { if (lpress || Date.now() < noClick) return; const s = sqAt(e); if (s) act(s); });
        board.addEventListener('pointerdown', e => {
            if (e.pointerType === 'touch' || e.button !== 0 || !st || (st.review !== null && st.review !== undefined)) return;
            const s = sqAt(e), p = s && game.get(s); if (!p || p.color !== st.human || game.game_over() || st.over) return;
            drag = { from: s, x: e.clientX, y: e.clientY, ghost: null, moved: false, src: p };
        });
        window.addEventListener('pointermove', e => {
            if (!drag) return;
            if (!drag.moved) { if (Math.hypot(e.clientX - drag.x, e.clientY - drag.y) < 6) return; drag.moved = true; act(drag.from); if (st.sel !== drag.from && st.psel !== drag.from) { drag = null; return; }
                const g = pieceEl(drag.src); g.style.cssText = 'position:fixed;z-index:7000;pointer-events:none;width:' + (board.clientWidth / 8) + 'px;height:' + (board.clientWidth / 8) + 'px;transform:translate(-50%,-50%)'; document.body.appendChild(g); drag.ghost = g; const sq = board.querySelector('.chess-sq[data-sq="' + drag.from + '"] .chess-pc'); if (sq) sq.style.opacity = '.35'; }
            drag.ghost.style.left = e.clientX + 'px'; drag.ghost.style.top = e.clientY + 'px';
        });
        window.addEventListener('pointerup', e => {
            if (!drag) return; const d = drag; drag = null; if (!d.moved) return;
            if (d.ghost) d.ghost.remove(); noClick = Date.now() + 80;
            const r = board.getBoundingClientRect(); let to = null;
            if (e.clientX >= r.left && e.clientX < r.right && e.clientY >= r.top && e.clientY < r.bottom) { const c = Math.floor((e.clientX - r.left) / r.width * 8), rw = Math.floor((e.clientY - r.top) / r.height * 8), f = st.flip ? 7 - c : c, rk = st.flip ? rw : 7 - rw; to = FILES[f] + (rk + 1); }
            if (to && to !== d.from) act(to); else { st.sel = null; st.targets = []; st.psel = null; render(); }
        });
    }

    function open() {
        if (ov) return; if (typeof Chess === 'undefined') { alert('O xadrez não carregou.'); return; }
        let list = models(); if (!list.length) { alert(T('Nenhum modelo disponível agora. Configure uma chave ou ligue o Ollama.')); return; }
        ov = mk('div', 'chess-ov'); const wrap = mk('div', 'chess-wrap'); ov.appendChild(wrap);
        const bsz = Math.max(280, Math.min(560, innerWidth - 80, innerHeight - 120)); wrap.style.setProperty('--cb', bsz + 'px');
        const bw = mk('div', 'chess-bw'); wrap.appendChild(bw); const evb = mk('div', 'chess-eval'); evb.appendChild(mk('i')); evb.appendChild(mk('b')); bw.appendChild(evb);
        const board = mk('div', 'chess-board'); board.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'svg')); const svg = board.lastChild; svg.setAttribute('class', 'chess-arrows'); svg.setAttribute('viewBox', '0 0 8 8'); bw.appendChild(board);
        const side = mk('div', 'chess-side'); wrap.appendChild(side); side.appendChild(mk('h3', '', T('Xadrez contra um modelo')));
        const provOf = m => { try { return providerName(m); } catch (e) { return ''; } }, logoOf = m => { const sp = mk('span', 'cm-logo'); try { fin(m); const br = brandOf(m); if (br) sp.appendChild(brandEl(br, m)); else sp.textContent = '☁'; } catch (e) { sp.textContent = '☁'; } return sp; };
        let pick = Math.max(0, list.findIndex(m => m.id === (typeof selectedModel !== 'undefined' ? selectedModel : '')));
        // seletor igual ao do chat: familias na lista, e embaixo Parametros e Provedor (reusa as funcoes do index.html)
        const cw = mk('div', 'custom-select'), cb = mk('div', 'select-trigger'), box = mk('div', 'select-options'); cw.append(cb, box);
        const paintBtn = () => { cb.textContent = ''; const m = list[pick]; cb.append(logoOf(m), mk('span', 'model-text shrinkable', m.label || m.id), mk('div', 'select-arrow')); };
        const families = () => { const map = new Map(); list.forEach(m => { fin(m); if (!map.has(m.grp)) map.set(m.grp, []); map.get(m.grp).push(m); }); map.forEach(ms => ms.sort((x, y) => verKey(x.ver) - verKey(y.ver) || sizeNum(x) - sizeNum(y) || provOrd(x) - provOrd(y) || (x.plabel || '').localeCompare(y.plabel || ''))); return new Map([...map.entries()].sort((x, y) => x[1][0].base.toLowerCase().localeCompare(y[1][0].base.toLowerCase(), 'pt', { numeric: true }))); };
        let term = '';
        const choose = m => { pick = list.indexOf(m); paintBtn(); fillList(); if (st && !st.log.length) { st.token = Math.random(); newGame({ model: list[pick], color: colorVal }); } };
        const fillList = () => {
            box.textContent = ''; const cur = list[pick], fams = families();
            const srch = document.createElement('input'); srch.type = 'text'; srch.placeholder = T('Buscar modelo…'); srch.autocomplete = 'off'; srch.value = term; srch.style.cssText = 'margin:8px;width:calc(100% - 16px);box-sizing:border-box'; srch.oninput = () => { term = srch.value; const pos = srch.selectionStart; fillList(); const n = box.querySelector('input'); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }; box.appendChild(srch);
            const lst = mk('div', 'mo-list'); box.appendChild(lst); let i = 0;
            fams.forEach((sizes, fam) => {
                if (term && !(famTitle(sizes) + ' ' + sizes.map(providerOf).join(' ')).toLowerCase().includes(term.trim().toLowerCase())) return;
                const rec = sizes.find(m => m.rec) || sizes[0], el = mk('div', 'select-option k-' + famKind(sizes) + (fam === fin(cur).grp ? ' selected' : '')); el.style.setProperty('--i', i++);
                const label = mk('span', 'mo-label'); famLabelNodes(rec, famTitle(sizes)).forEach(n => label.appendChild(n)); el.appendChild(label);
                const pv = provLogos(sizes); if (pv) el.appendChild(pv);
                el.onclick = () => { if (fam === fin(cur).grp) return; const p0 = sizes.find(m => m.rec) || sizes.find(m => !m.heavy) || sizes[0]; choose(bestVariant(sizes.filter(x => x.pk === p0.pk))); };
                lst.appendChild(el);
            });
            if (!lst.firstChild) lst.appendChild(mk('div', 'select-option', T('Nenhum modelo encontrado')));
            const sizes = fams.get(fin(cur).grp) || [];
            if (sizes.length) {
                const row = mk('div', 'size-row'), keys = []; sizes.forEach(m => { let k = keys.find(x => x.pk === m.pk); if (!k) keys.push(k = { pk: m.pk, items: [] }); k.items.push(m); });
                const variants = (keys.find(k => k.pk === cur.pk) || { items: [cur] }).items;
                row.append(mk('span', 'size-label', T('Parâmetros')), miniSelect(keys.map(k => { const rep = k.pk === cur.pk ? cur : bestVariant(k.items), kinds = new Set(k.items.map(kindOf)); return { value: rep.id, label: rep.klabel + (rep.heavy ? ' ⚠' : ''), color: kinds.has('local') ? 'var(--k-local)' : kinds.has('cloud') ? 'var(--k-cloud)' : 'var(--k-paid)' }; }), cur.id, v => choose(list.find(m => m.id === v) || cur), T('Parâmetros')));
                row.appendChild(miniSelect(variants.map(m => ({ value: m.id, label: providerName(m) + provInfo(m), title: m.warn || '', color: m.pol ? 'var(--k-paid)' : isLocalM(m) ? 'var(--k-local)' : 'var(--k-cloud)' })), cur.id, v => choose(list.find(m => m.id === v) || cur), T('Provedor')));
                box.appendChild(row);
            }
        };
        const providerOf = m => { try { return providerName(m); } catch (e) { return ''; } };
        cb.onclick = () => { const on = !cw.classList.contains('open'); if (on) { const id = list[pick].id; list = models(); pick = Math.max(0, list.findIndex(m => m.id === id)); term = ''; fillList(); } cw.classList.toggle('open', on); if (on) { const cur = box.querySelector('.select-option.selected'); if (cur) cur.scrollIntoView({ block: 'center' }); } };
        ov.addEventListener('mousedown', e => { if (!cw.contains(e.target)) cw.classList.remove('open'); }); paintBtn(); side.appendChild(cw);
        let colorVal = 'w'; const seg = mk('div', 'chess-seg'); [['w', 'Brancas'], ['b', 'Pretas'], ['random', 'Aleatório']].forEach(([v, l]) => { const b = mk('button', v === colorVal ? 'on' : '', T(l)); b.type = 'button'; b.onclick = () => { colorVal = v; seg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); if (st && !st.log.length) { st.token = Math.random(); newGame({ model: list[pick], color: colorVal }); } }; seg.appendChild(b); }); side.appendChild(seg);
        const opt = (id, label, key) => { const l = mk('label', 'chess-tog'), c = document.createElement('input'); c.type = 'checkbox'; c.id = id; c.onchange = () => { st.opts[key] = c.checked; if (key === 'rank') { if (c.checked) rankBackfill(); render(); } }; c.checked = st ? !!st.opts[key] : key === 'noSpawn'; l.append(mk('span', '', T(label)), c, mk('span', 'sw')); side.appendChild(l); return c; };
        opt('chess-ill', 'Permitir lances ilegais do modelo', 'illegal'); opt('chess-nospawn', 'Bloquear peças criadas do nada pelo modelo (só vale com lances ilegais)', 'noSpawn'); opt('chess-rank', 'Ranking dos lances (Brilhante, Melhor, Erro…)', 'rank');
        const lk = mk('div', 'chess-row'); const mkSel = (opts, val, fn) => { const x = document.createElement('select'); x.className = 'chess-lk'; opts.forEach(([v, l]) => x.add(new Option(T(l), v))); x.value = val; x.onchange = () => fn(x.value); lk.appendChild(x); };
        mkSel(Object.entries(SET_NAMES).map(([k, n]) => [k, T('Peças') + ': ' + T(n)]), look.set, v => { look.set = v; saveLook(); render(); });
        mkSel(Object.entries(BOARDS).map(([k, b]) => [k, T('Tabuleiro') + ': ' + T(b[0])]), look.board, v => { look.board = v; saveLook(); applyBoard(); }); side.appendChild(lk);
        const row = mk('div', 'chess-row'); side.appendChild(row);
        const btn = (txt, fn) => { const b = mk('button', 'btn btn-secondary', T(txt)); b.type = 'button'; b.onclick = fn; row.appendChild(b); return b; };
        const start = btn('Novo jogo', () => { if (st) st.token = Math.random(); newGame({ model: list[pick], color: colorVal }); }); start.classList.replace('btn-secondary', 'btn-primary');
        btn('Desfazer', undo); btn('Virar', () => { st.flip = !st.flip; render(); });
        btn('Desistir', () => { if (game && !game.game_over() && !st.over) { st.token = Math.random(); st.thinking = false; st.over = T('Você desistiu.'); st.pre = null; st.psel = null; render(); } });
        btn('Analisar partida', analyzeGame); btn('Exportar PGN', exportPgn);
        const xb = mk('button', 'chess-x', '✕'); xb.type = 'button'; xb.title = T('Fechar'); xb.setAttribute('aria-label', T('Fechar')); ov.appendChild(xb);
        xb.onclick = () => { if (st) st.token = Math.random(); if (st && st.rid) { try { fetch(API + '/api/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rid: st.rid }) }); } catch (e) { /* ok */ } } const o = ov; ov = null; o.classList.add('out'); setTimeout(() => o.remove(), 190); };
        const navRow = mk('div', 'chess-row chess-nav'); [['⏮', 'start'], ['◀', -1], ['▶', 1], ['⏭', 'end']].forEach(([t, d]) => { const b = mk('button', 'btn btn-secondary', t); b.type = 'button'; b.onclick = () => nav(d); navRow.appendChild(b); }); const ex = mk('button', 'btn btn-secondary', T('Sair da análise')); ex.type = 'button'; ex.onclick = () => { st.review = null; render(); }; navRow.appendChild(ex); side.appendChild(navRow);
        side.appendChild(mk('div', 'chess-status', '')); side.appendChild(mk('div', 'chess-moves', '')); const sum = mk('div', 'chess-sum', ''); sum.style.whiteSpace = 'pre-line'; side.appendChild(sum);
        side.appendChild(mk('div', 'chess-hint', T('Botão direito: segure e arraste para desenhar uma seta (Shift vermelha, Ctrl azul, Alt amarela); clique direito numa casa marca a casa; clique esquerdo limpa. No celular: segure o dedo numa casa e arraste.')));
        applyBoard(); wire(board); document.body.appendChild(ov);
        newGame({ model: list[pick], color: 'w' });
    }
    async function rankBackfill() { for (let i = 0; i < st.log.length; i++) { if (st.cls[i]) continue; const my = st.token; try { await analyze(st.log[i].fen); await analyze(i + 1 < st.log.length ? st.log[i + 1].fen : game.fen()); if (my !== st.token) return; const c = classify(i); if (c) st.cls[i] = c; render(); } catch (e) { st.note = T('Motor de análise indisponível: ') + String(e.message || e).slice(0, 80); st.opts.rank = false; render(); return; } } }
    let setsP = null;
    const loadSets = () => window.CHESS_SETS ? Promise.resolve() : (setsP = setsP || new Promise(res => { const sc = document.createElement('script'); sc.src = 'libs/chess-sets.js'; sc.onload = sc.onerror = () => res(); document.head.appendChild(sc); }));
    window.openChess = () => { loadSets().then(open); };
    window.__chess = { get game() { return game; }, get st() { return st; }, parseMove, parseCoord, classify, analyze, wpct, forceMove, pgnText };
})();
