/* Editor de tabuleiro do xadrez (usado pelo xadrez contra um modelo e pelo duelo): monte QUALQUER posicao e comece a partida dali.
   Escolha uma peca na paleta e clique (ou arraste, ou segure e pinte) nas casas; botao direito apaga. "Encher as casas vazias" poe a peca escolhida em todas as casas livres
   (o tabuleiro so tem 64 casas, entao 900 peoes nao cabem: o maximo e encher tudo). Regras que ficam: um rei de cada cor, nenhum peao na primeira/ultima fileira e o lado que
   NAO joga nao pode estar em xeque. Usa o chess.js (libs/chess.min.js) so para conferir; as imagens vem de libs/chess-pieces.js.
     lumeBoardEditor.open({ fen: '...', onApply: fen => ... })                                                                                        */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s), mk = (t, c, x) => window.LumeUI.el(t, c, x);
    const START = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR', FILES = 'abcdefgh', ORDER = ['K', 'Q', 'R', 'B', 'N', 'P'], GL = { k: '♚', q: '♛', r: '♜', b: '♝', n: '♞', p: '♟' };
    const css = document.createElement('style');
    css.textContent = `
        .be-wrap { display: grid; grid-template-columns: minmax(0, 1fr) minmax(250px, 300px); gap: 16px; align-items: start; } @media (max-width: 760px) { .be-wrap { grid-template-columns: minmax(0, 1fr); } }
        .be-board { display: grid; grid-template-columns: repeat(8, 1fr); grid-template-rows: repeat(8, 1fr); width: min(520px, 100%, calc(100vh - 250px)); min-width: 240px; aspect-ratio: 1; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 6px 24px rgba(0,0,0,.35); user-select: none; -webkit-user-select: none; touch-action: none; }
        .be-sq { position: relative; display: flex; align-items: center; justify-content: center; aspect-ratio: 1; min-width: 0; min-height: 0; cursor: pointer; } .be-sq.l { background: #eeeed2; } .be-sq.d { background: #769656; } .be-sq:hover { box-shadow: inset 0 0 0 3px rgba(255, 214, 10, .8); }
        .be-sq img { width: 92%; height: 92%; object-fit: contain; pointer-events: none; } .be-sq span.gl { font-size: 3.2vmin; pointer-events: none; }
        .be-pal { display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px; } .be-pal button { aspect-ratio: 1; border-radius: 10px; border: 1px solid var(--border-color); background: rgba(128,128,128,.12); cursor: pointer; padding: 2px; display: flex; align-items: center; justify-content: center; } .be-pal button img { width: 100%; height: 100%; object-fit: contain; } .be-pal button.on { outline: 2px solid var(--accent); background: rgba(128,128,128,.28); }
        .be-side { display: flex; flex-direction: column; gap: 10px; min-width: 0; } .be-row { display: flex; flex-wrap: wrap; gap: 6px; } .be-row .btn { margin: 0; padding: 7px 10px; font-size: .85em; flex: 1 1 auto; }
        .be-msg { font-size: .84em; padding: 8px 10px; border-radius: 10px; background: rgba(128,128,128,.12); line-height: 1.4; } .be-msg.bad { color: #e5484d; } .be-msg.ok { color: #3fb950; }
        .be-fen { width: 100%; box-sizing: border-box; font: .78em Consolas, monospace; padding: 7px 9px; border-radius: 10px; border: 1px solid var(--border-color); background: var(--bg-input, rgba(128,128,128,.12)); color: var(--text-main); }
    `;
    document.head.appendChild(css);
    const img = k => (window.CHESS_PIECES || {})[k];
    const pieceEl = ch => { if (!ch) return null; const key = (ch === ch.toUpperCase() ? 'w' : 'b') + ch.toUpperCase(), src = img(key); if (src) { const i = document.createElement('img'); i.src = src; i.alt = key; return i; } return mk('span', 'gl', GL[ch.toLowerCase()]); };
    function parse(fen) {   // FEN -> {grid[8][8] (linha 0 = fileira 8), turn}
        const f = String(fen || START).trim().split(/\s+/), grid = f[0].split('/').map(r => { const row = []; for (const c of r) { if (/\d/.test(c)) for (let k = 0; k < +c; k++) row.push(''); else row.push(c); } while (row.length < 8) row.push(''); return row.slice(0, 8); });
        while (grid.length < 8) grid.push(Array(8).fill('')); return { grid: grid.slice(0, 8), turn: f[1] === 'b' ? 'b' : 'w' };
    }
    function toFen(grid, turn) {
        const place = grid.map(r => { let o = '', n = 0; r.forEach(c => { if (!c) n++; else { if (n) { o += n; n = 0; } o += c; } }); return o + (n || ''); }).join('/');
        const ok = { K: grid[7][4] === 'K' && grid[7][7] === 'R', Q: grid[7][4] === 'K' && grid[7][0] === 'R', k: grid[0][4] === 'k' && grid[0][7] === 'r', q: grid[0][4] === 'k' && grid[0][0] === 'r' };   // so mantem o roque se o rei e a torre estao em casa
        return place + ' ' + turn + ' ' + (Object.keys(ok).filter(k => ok[k]).join('') || '-') + ' - 0 1';
    }
    function problems(grid, turn) {
        const all = grid.flat(), out = [], cnt = c => all.filter(x => x === c).length;
        if (cnt('K') !== 1) out.push(cnt('K') === 0 ? 'Falta o rei branco.' : 'So pode haver 1 rei branco.'); if (cnt('k') !== 1) out.push(cnt('k') === 0 ? 'Falta o rei preto.' : 'So pode haver 1 rei preto.');
        if ([...grid[0], ...grid[7]].some(c => c === 'P' || c === 'p')) out.push('Peao na primeira ou na ultima fileira nao pode.');
        if (!out.length) { try { const g = new Chess(), other = toFen(grid, turn === 'w' ? 'b' : 'w'); if (g.load(other) && g.in_check()) out.push('O rei de quem NAO joga esta em xeque (nao e uma posicao possivel).'); } catch (e) { /* o chess.js decide na hora de jogar */ } }
        return out;
    }
    function open(o) {
        if (document.getElementById('be-modal')) return; const u = window.LumeUI, w = u.modal({ title: 'Editar tabuleiro', id: 'be-modal', width: 880, sticky: true });
        let { grid, turn } = parse(o.fen), sel = 'wP', down = false, erase = false;
        const wrap = mk('div', 'be-wrap'), board = mk('div', 'be-board'), side = mk('div', 'be-side'), pal = mk('div', 'be-pal'), msg = mk('div', 'be-msg'), fenBox = document.createElement('input'); fenBox.className = 'be-fen'; fenBox.spellcheck = false;
        wrap.append(board, side); w.body.appendChild(wrap);
        const palBtns = {}; ['w', 'b'].forEach(c => ORDER.forEach(p => { const b = mk('button'); b.type = 'button'; b.title = T({ K: 'Rei', Q: 'Dama', R: 'Torre', B: 'Bispo', N: 'Cavalo', P: 'Peão' }[p]) + ' ' + T(c === 'w' ? 'branco' : 'preto'); const e = pieceEl(c === 'w' ? p : p.toLowerCase()); b.appendChild(e); b.onclick = () => { sel = c + p; paintPal(); }; pal.appendChild(b); palBtns[c + p] = b; }));
        const er = mk('button', 'btn btn-secondary', T('Borracha')); er.type = 'button'; er.onclick = () => { sel = 'erase'; paintPal(); };
        function paintPal() { Object.entries(palBtns).forEach(([k, b]) => b.classList.toggle('on', k === sel)); er.classList.toggle('on', sel === 'erase'); er.style.outline = sel === 'erase' ? '2px solid var(--accent)' : ''; }
        const chOf = k => (k[0] === 'w' ? k[1] : k[1].toLowerCase());
        function draw() {
            board.textContent = ''; grid.forEach((row, r) => row.forEach((ch, f) => { const sq = mk('div', 'be-sq ' + ((r + f) % 2 === 0 ? 'l' : 'd')); sq.dataset.r = r; sq.dataset.f = f; const e = pieceEl(ch); if (e) sq.appendChild(e); board.appendChild(sq); }));
            const pb = problems(grid, turn), cntW = grid.flat().filter(c => c && c === c.toUpperCase()).length, cntB = grid.flat().filter(c => c && c !== c.toUpperCase()).length;
            msg.className = 'be-msg ' + (pb.length ? 'bad' : 'ok'); msg.textContent = pb.length ? pb.map(T).join(' ') : '✓ ' + T('Posição válida') + ' · ' + cntW + ' ' + T('brancas') + ', ' + cntB + ' ' + T('pretas'); applyBtn.disabled = !!pb.length; fenBox.value = toFen(grid, turn);
        }
        const put = sq => { const r = +sq.dataset.r, f = +sq.dataset.f, want = erase || sel === 'erase' ? '' : chOf(sel); if (grid[r][f] === want) return; grid[r][f] = want; draw(); };
        board.addEventListener('pointerdown', e => { const sq = e.target.closest('.be-sq'); if (!sq) return; e.preventDefault(); erase = e.button === 2; down = true; put(sq); });
        board.addEventListener('pointerover', e => { if (!down) return; const sq = e.target.closest('.be-sq'); if (sq) put(sq); });
        board.addEventListener('contextmenu', e => e.preventDefault()); const up = () => { down = false; erase = false; }; addEventListener('pointerup', up); new MutationObserver((m, ob) => { if (!document.getElementById('be-modal')) { removeEventListener('pointerup', up); ob.disconnect(); } }).observe(document.body, { childList: true });
        side.append(mk('div', 'lu-hint', T('Escolha uma peça e clique ou arraste sobre as casas. Botão direito apaga.')), pal);
        const tools = mk('div', 'be-row'); const tb = (txt, fn) => { const b = mk('button', 'btn btn-secondary', T(txt)); b.type = 'button'; b.onclick = fn; tools.appendChild(b); return b; };
        tools.appendChild(er);
        tb('Encher as casas vazias', () => { if (sel === 'erase') return; grid = grid.map(r => r.map(c => c || chOf(sel))); draw(); });
        tb('Limpar', () => { grid = Array.from({ length: 8 }, () => Array(8).fill('')); draw(); }); tb('Posição inicial', () => { grid = parse(START + ' w').grid; turn = 'w'; draw(); setTurn(); });
        tb('Só os reis', () => { grid = Array.from({ length: 8 }, () => Array(8).fill('')); grid[7][4] = 'K'; grid[0][4] = 'k'; draw(); });
        side.appendChild(tools);
        const turnRow = u.seg(side, [['w', 'Brancas jogam'], ['b', 'Pretas jogam']], turn, v => { turn = v; draw(); }); const setTurn = () => turnRow.querySelectorAll('button').forEach(b => b.classList.toggle('on', (b.textContent === T('Brancas jogam')) === (turn === 'w')));
        side.append(msg, mk('div', 'lu-hint', 'FEN:'), fenBox);
        fenBox.onchange = () => { try { const p = parse(fenBox.value); grid = p.grid; turn = p.turn; draw(); setTurn(); } catch (e) { /* FEN invalida: volta ao que estava */ draw(); } };
        const applyBtn = u.button(w.foot, 'Usar esta posição', () => { if (problems(grid, turn).length) return; const fen = toFen(grid, turn); w.close(); if (o.onApply) o.onApply(fen); }, 'primary'); u.button(w.foot, 'Cancelar', () => w.close());
        paintPal(); draw();
    }
    window.lumeBoardEditor = { open, toFen, parse, problems };
})();
