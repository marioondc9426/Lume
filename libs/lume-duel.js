/* Duelo de xadrez (em Jogos): VOCE ASSISTE. Cada lado pode ser um modelo (qualquer um do seletor) ou o Stockfish (nivel 0 a 20), entao da para ver modelo contra modelo,
   Stockfish contra modelo, ou Stockfish contra Stockfish. Um lance por vez, com pausa, velocidade ajustavel e o PGN no fim.
   Modelo contra modelo (decidido, sem empate) conta como voto no seu ranking pessoal (libs/lume-scores.js).
   Usa o chess.js (libs/chess.min.js), o Stockfish (libs/stockfish) e o lumeAsk; nao mexe nas suas conversas. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const css = document.createElement('style');
    css.textContent = `
        .dl-wrap { display: flex; flex-direction: column; gap: 10px; } .dl-sides { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; } @media (max-width: 640px) { .dl-sides { grid-template-columns: 1fr; } }
        .dl-side { padding: 10px; border-radius: 14px; background: rgba(128,128,128,.10); display: flex; flex-direction: column; gap: 8px; } .dl-side h4 { margin: 0; font-size: .9em; } .dl-side .lu-seg { margin: 0; }
        .dl-lvl { display: flex; align-items: center; gap: 10px; font-size: .85em; } .dl-lvl input { flex: 1; }
        .dl-board { display: grid; grid-template-columns: repeat(8, 1fr); grid-template-rows: repeat(8, 1fr); width: min(400px, 100%); aspect-ratio: 1; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 24px rgba(0,0,0,.35); }
        .dl-sq { aspect-ratio: 1; min-width: 0; min-height: 0; position: relative; display: flex; align-items: center; justify-content: center; } .dl-sq.l { background: #eeeed2; } .dl-sq.d { background: #769656; } .dl-sq.mv::after { content: ''; position: absolute; inset: 0; background: rgba(255, 221, 0, .38); } .dl-sq img { width: 92%; height: 92%; position: relative; z-index: 1; }
        .dl-bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: center; } .dl-bar .btn { margin: 0; } .dl-bar select { width: auto; }
        .dl-moves { font-size: .82em; line-height: 1.6; max-height: 90px; overflow-y: auto; padding: 8px 12px; border-radius: 12px; background: rgba(128,128,128,.10); color: var(--text-muted); }
    `;
    document.head.appendChild(css);
    const el = (t, c, x) => window.LumeUI.el(t, c, x);
    const files = 'abcdefgh';

    // ---- Stockfish (um motor so para o duelo; fecha com a janela)
    function xhrText(url) { return new Promise((res, rej) => { const x = new XMLHttpRequest(); x.open('GET', url); x.onload = () => ((x.status === 200 || x.status === 0) && x.responseText ? res(x.responseText) : rej(new Error('HTTP ' + x.status))); x.onerror = () => rej(new Error('rede')); x.send(); }); }
    async function startEngine() {
        let w; if (/^https?:/.test(location.protocol)) { try { w = new Worker('libs/stockfish/stockfish.js'); } catch (e) { w = null; } }
        if (!w) w = new Worker(URL.createObjectURL(new Blob([await xhrText('libs/stockfish/stockfish.asm.js')], { type: 'text/javascript' })));   // iPhone: motor em JS puro
        let on = null; w.onmessage = e => { if (on) on(typeof e.data === 'string' ? e.data : String(e.data)); };
        const wait = (cmd, re, ms) => new Promise((res, rej) => { const t = setTimeout(() => { on = null; rej(new Error('o Stockfish nao respondeu')); }, ms || 20000); on = l => { const m = re.exec(l); if (m) { clearTimeout(t); on = null; res(m); } }; w.postMessage(cmd); });
        await wait('uci', /uciok/); await wait('isready', /readyok/);
        return {
            async best(fen, level, ms) { w.postMessage('setoption name Skill Level value ' + Math.max(0, Math.min(20, level))); w.postMessage('position fen ' + fen); const m = await wait('go movetime ' + ms, /^bestmove (\S+)/, ms + 15000); return m[1]; },
            stop() { try { w.terminate(); } catch (e) { /* ok */ } },
        };
    }

    function startDuel(host) {
        const u = window.LumeUI, kit = window.lumeGamesKit; let game = null, running = false, token = 0, engine = null, log = [], last = null, delay = 700;
        const side = { w: { kind: 'model', level: 8, pick: null }, b: { kind: 'engine', level: 5, pick: null } };
        const sides = el('div', 'dl-sides'), board = el('div', 'dl-board'), status = el('div', 'gm-status', ''), bar = el('div', 'dl-bar'), moves = el('div', 'dl-moves', '');
        const wrap = el('div', 'dl-wrap'); wrap.append(sides, status, board, bar, moves); host.appendChild(wrap);
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
                if (p) { const img = document.createElement('img'); img.alt = p.type; img.src = (window.CHESS_PIECES || {})[p.color + p.type.toUpperCase()] || ''; sq.appendChild(img); } board.appendChild(sq);
            }
            let o = ''; log.forEach((m, i) => { if (i % 2 === 0) o += (i / 2 + 1) + '. '; o += m + ' '; }); moves.textContent = o.trim() || T('(sem lances ainda)'); moves.scrollTop = moves.scrollHeight;
        }
        const parseModel = (text, legal) => {   // aceita SAN (Nf3) ou coordenadas (g1f3)
            const t = String(text || '').replace(/[*`]/g, ' '); for (const m of legal) { const re = new RegExp('(^|[\\s,.;:()])' + m.san.replace(/[+#]/g, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '[+#]?($|[\\s,.;:!?)])'); if (re.test(t)) return m; }
            const c = /([a-h][1-8])\s*[-x:]?\s*([a-h][1-8])\s*=?\s*([qrbn])?/i.exec(t.toLowerCase()); if (c) return legal.find(m => m.from === c[1] && m.to === c[2] && (!m.promotion || m.promotion === (c[3] || 'q'))) || null; return null;
        };
        async function pickMove(c, my) {
            const legal = game.moves({ verbose: true }), s = side[c];
            if (s.kind === 'engine') { const bm = await engine.best(game.fen(), s.level, 120 + s.level * 40); if (my !== token) return null; const m = legal.find(x => x.from === bm.slice(0, 2) && x.to === bm.slice(2, 4) && (!x.promotion || x.promotion === (bm[4] || 'q'))); return { m: m || legal[0], note: m ? '' : 'lance do motor não reconhecido' }; }
            const mdl = s.pick && s.pick.get(); if (!mdl) return { m: legal[Math.floor(Math.random() * legal.length)], note: 'sem modelo escolhido' };
            const sys = 'Você joga xadrez de verdade e quer ganhar. Responda SOMENTE com o seu lance, em notação SAN da lista de lances legais (ex.: Nf3, exd5, O-O, e8=Q). Nada de explicação.';
            for (let i = 0; i < 2; i++) {
                let r; try { r = await lumeAsk({ model: mdl, system: sys, user: 'Posição (FEN): ' + game.fen() + '\nLances até agora: ' + (log.join(' ') || '(nenhum)') + '\nVocê joga de ' + (c === 'w' ? 'brancas' : 'pretas') + '.\nLances legais: ' + legal.map(x => x.san).join(', ') + '\nResponda só com o seu lance.' + (i ? '\nA resposta anterior não era um lance legal da lista.' : ''), timeoutMs: 60000 }); } catch (e) { if (my !== token) return null; return { m: legal[Math.floor(Math.random() * legal.length)], note: 'o modelo falhou (' + String(e.message || e).slice(0, 60) + '); lance sorteado' }; }
                if (my !== token) return null; const m = parseModel(r, legal); if (m) return { m, note: '' };
            }
            return { m: legal[Math.floor(Math.random() * legal.length)], note: 'o modelo não deu um lance válido; lance sorteado' };
        }
        const resultText = () => game.in_checkmate() ? (game.turn() === 'w' ? 'Pretas' : 'Brancas') + ' ' + T('ganharam por xeque-mate') : game.in_stalemate() ? T('Empate: afogamento') : game.insufficient_material() ? T('Empate: material insuficiente') : game.in_threefold_repetition() ? T('Empate: repetição') : game.in_draw() ? T('Empate (50 lances)') : '';
        async function loop(my) {
            while (running && my === token) {
                if (game.game_over() || log.length >= 200) break;
                const c = game.turn(); status.textContent = who(c) + ' ' + T('está pensando…') + ' (' + (c === 'w' ? T('Brancas') : T('Pretas')) + ')';
                let res; try { res = await pickMove(c, my); } catch (e) { status.textContent = T('Erro: ') + String(e.message || e).slice(0, 100); running = false; break; }
                if (!res || my !== token) return;
                const mv = game.move(res.m.san); log.push(mv.san); last = { from: mv.from, to: mv.to }; draw(); status.textContent = who(c) + ': ' + mv.san + (res.note ? ' — ' + T(res.note) : '');
                await new Promise(r => setTimeout(r, delay)); while (running && my === token && paused) await new Promise(r => setTimeout(r, 200));
            }
            if (my !== token) return; running = false; syncBtns();
            if (game.game_over() || log.length >= 200) {
                const rt = resultText() || T('Parou no limite de 200 lances (empate).'); status.textContent = T('Fim: ') + rt + '.';
                if (game.in_checkmate() && side.w.kind === 'model' && side.b.kind === 'model' && window.lumeScores) { const win = game.turn() === 'w' ? side.b.pick.get() : side.w.pick.get(), lose = game.turn() === 'w' ? side.w.pick.get() : side.b.pick.get(); if (win && lose && win.id !== lose.id) { lumeScores.vote(win.id, [lose.id], false); status.textContent += ' ' + T('(contou no seu ranking)'); } }
            }
        }
        let paused = false; const bPlay = u.button(bar, 'Começar', () => begin()), bPause = u.button(bar, 'Pausar', () => { paused = !paused; bPause.textContent = T(paused ? 'Continuar' : 'Pausar'); }), bCopy = u.button(bar, 'Copiar PGN', () => { const h = '[White "' + who('w') + '"]\n[Black "' + who('b') + '"]\n[Result "' + (game.in_checkmate() ? (game.turn() === 'w' ? '0-1' : '1-0') : game.game_over() ? '1/2-1/2' : '*') + '"]\n\n'; let o = ''; log.forEach((m, i) => { if (i % 2 === 0) o += (i / 2 + 1) + '. '; o += m + ' '; }); try { navigator.clipboard.writeText(h + o.trim()); status.textContent = T('PGN copiado.'); } catch (e) { /* sem area de transferencia */ } });
        const spd = u.select([['1400', 'Devagar'], ['700', 'Normal'], ['200', 'Rápido']], '700', v => { delay = +v; }); bar.appendChild(spd);
        function syncBtns() { bPlay.textContent = T(running ? 'Reiniciar' : 'Começar'); bPause.style.display = running ? '' : 'none'; bCopy.style.display = log.length ? '' : 'none'; }
        async function begin() {
            token++; const my = token; running = false; paused = false; bPause.textContent = T('Pausar'); game = new Chess(); log = []; last = null; draw();
            const needEngine = side.w.kind === 'engine' || side.b.kind === 'engine';
            if (needEngine && !engine) { status.textContent = T('Ligando o Stockfish…'); try { engine = await startEngine(); } catch (e) { status.textContent = T('Não consegui ligar o Stockfish: ') + String(e.message || e).slice(0, 80); return; } }
            if (my !== token) return; running = true; syncBtns(); loop(my);
        }
        game = new Chess(); draw(); syncBtns(); status.textContent = T('Escolha quem joga de cada lado e aperte Começar.');
        // limpa ao fechar a janela de jogos / voltar ao menu: o host sai do documento
        const mo = new MutationObserver(() => { if (!host.isConnected) { token++; running = false; if (engine) engine.stop(); mo.disconnect(); } }); mo.observe(document.body, { childList: true, subtree: true });
    }
    if (window.LUME_GAMES) window.LUME_GAMES.push({ id: 'duel', name: 'Duelo de xadrez', desc: 'Você assiste: modelo contra modelo, ou contra o Stockfish.', start: startDuel });
})();
