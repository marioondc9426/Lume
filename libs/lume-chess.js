/* Xadrez do Lume: jogue contra qualquer modelo. Regras e lances legais vem do chess.js; o modelo recebe a posicao e a lista de lances legais e responde com um deles.
   Botao direito: segure e arraste para desenhar uma seta (Shift = vermelha, Ctrl = azul, Alt = amarela); clique direito numa casa marca a casa; clique esquerdo limpa. No celular: segure o dedo numa casa e arraste. */
(() => {
    'use strict';
    const GLYPH = { k: '♚︎', q: '♛︎', r: '♜︎', b: '♝︎', n: '♞︎', p: '♟︎' };
    const FILES = 'abcdefgh', T = s => (typeof tr === 'function' ? tr(s) : s);
    let game = null, st = null, ov = null;

    const css = document.createElement('style');
    css.textContent = `
        .chess-ov { position: fixed; inset: 0; z-index: 6500; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.6); padding: 12px; overflow: auto; }
        .chess-wrap { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; justify-content: center; max-width: 100%; background: var(--bg-main); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 20px; padding: 16px; box-shadow: 0 20px 60px rgba(0,0,0,.55); }
        .chess-board { position: relative; width: var(--cb, 520px); height: var(--cb, 520px); display: grid; grid-template-columns: repeat(8, 1fr); grid-template-rows: repeat(8, 1fr); border-radius: 8px; overflow: hidden; user-select: none; -webkit-user-select: none; touch-action: none; }
        .chess-sq { position: relative; display: flex; align-items: center; justify-content: center; font-size: calc(var(--cb, 520px) / 8 * 0.78); line-height: 1; cursor: pointer; }
        .chess-sq.l { background: #ecd9b4; } .chess-sq.d { background: #ae8a68; }
        .chess-sq.sel { box-shadow: inset 0 0 0 4px rgba(255, 214, 10, .85); } .chess-sq.last { background-image: linear-gradient(rgba(255, 238, 90, .45), rgba(255, 238, 90, .45)); }
        .chess-sq.chk { background-image: radial-gradient(circle, rgba(255, 40, 40, .9) 0%, rgba(255, 40, 40, 0) 70%); }
        .chess-sq.mark { box-shadow: inset 0 0 0 100px rgba(235, 64, 52, .5); }
        .chess-sq.tgt::after { content: ''; position: absolute; width: 28%; height: 28%; border-radius: 50%; background: rgba(20, 20, 20, .28); }
        .chess-sq.tgt.cap::after { width: 86%; height: 86%; background: none; border: 5px solid rgba(20, 20, 20, .28); }
        .chess-pc { z-index: 1; pointer-events: none; } .chess-pc.w { color: #fff; text-shadow: 0 0 2px #000, 0 0 2px #000, 0 0 3px #000, 0 1px 3px rgba(0,0,0,.6); } .chess-pc.b { color: #151515; text-shadow: 0 0 1px #fff, 0 0 2px rgba(255,255,255,.5); }
        .chess-co { position: absolute; font: 600 10px system-ui, sans-serif; opacity: .65; pointer-events: none; color: #333; } .chess-co.r { top: 2px; left: 3px; } .chess-co.f { bottom: 1px; right: 3px; }
        .chess-arrows { position: absolute; inset: 0; pointer-events: none; z-index: 3; }
        .chess-side { display: flex; flex-direction: column; gap: 10px; width: min(300px, 100%); }
        .chess-side h3 { margin: 0; } .chess-side select { width: 100%; } .chess-row { display: flex; flex-wrap: wrap; gap: 6px; } .chess-row .btn { margin: 0; padding: 8px 12px; flex: 1 1 auto; }
        .chess-status { padding: 10px 12px; border-radius: 12px; background: rgba(128,128,128,.14); font-size: .92em; min-height: 2.6em; }
        .chess-moves { max-height: 170px; overflow-y: auto; font-size: .88em; line-height: 1.7; padding: 8px 10px; border-radius: 12px; background: rgba(128,128,128,.08); }
        .chess-hint { font-size: .76em; color: var(--text-muted); line-height: 1.4; }
        .chess-promo { position: absolute; inset: 0; z-index: 5; display: flex; align-items: center; justify-content: center; gap: 8px; background: rgba(0,0,0,.55); }
        .chess-promo button { font-size: 2.4em; width: 1.5em; height: 1.5em; border-radius: 12px; border: 0; background: #ecd9b4; cursor: pointer; }`;
    document.head.appendChild(css);

    const sqName = (f, r) => FILES[f] + (r + 1);
    const sqXY = sq => ({ f: FILES.indexOf(sq[0]), r: +sq[1] - 1 });
    const mk = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };

    function models() { return (typeof MODELS !== 'undefined' ? MODELS : []).filter(m => { try { return m.tabs.includes('chat') && isAvail(m); } catch (e) { return false; } }); }

    function newGame(o) {
        const human = o.color === 'random' ? (Math.random() < 0.5 ? 'w' : 'b') : o.color;
        game = new Chess(); st = { human, model: o.model, flip: human === 'b', sel: null, targets: [], last: null, arrows: [], marks: [], thinking: false, over: '', note: '', rid: null, token: Math.random() };
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

    function render() {
        if (!ov) return;
        const board = ov.querySelector('.chess-board'), b = game.board(), kingSq = (() => { if (!game.in_check()) return null; for (let r = 0; r < 8; r++) for (let f = 0; f < 8; f++) { const p = b[7 - r][f]; if (p && p.type === 'k' && p.color === game.turn()) return sqName(f, r); } return null; })();
        board.querySelectorAll('.chess-sq').forEach(e => e.remove());
        for (let row = 0; row < 8; row++) for (let col = 0; col < 8; col++) {
            const f = st.flip ? 7 - col : col, r = st.flip ? row : 7 - row, name = sqName(f, r), p = b[7 - r][f], d = mk('div', 'chess-sq ' + ((f + r) % 2 === 0 ? 'd' : 'l')); d.dataset.sq = name;
            if (st.sel === name) d.classList.add('sel'); if (st.last && (st.last.from === name || st.last.to === name)) d.classList.add('last'); if (kingSq === name) d.classList.add('chk'); if (st.marks.includes(name)) d.classList.add('mark');
            if (st.targets.includes(name)) { d.classList.add('tgt'); if (p) d.classList.add('cap'); }
            if (p) { const g = mk('span', 'chess-pc ' + p.color, GLYPH[p.type]); d.appendChild(g); }
            if (col === 0) d.appendChild(mk('span', 'chess-co r', String(r + 1))); if (row === 7) d.appendChild(mk('span', 'chess-co f', FILES[f]));
            board.insertBefore(d, board.querySelector('.chess-arrows'));
        }
        drawArrows();
        const over = game.game_over() ? result() : st.over; st.over = over || st.over;
        const turnTxt = game.turn() === st.human ? T('Sua vez.') + (game.in_check() ? ' ' + T('Você está em xeque!') : '') : (st.thinking ? T('O modelo está pensando…') : T('Vez do modelo.'));
        ov.querySelector('.chess-status').textContent = (st.over || turnTxt) + (st.note ? ' ' + st.note : '');
        const hist = game.history(), mv = ov.querySelector('.chess-moves'); mv.textContent = '';
        for (let i = 0; i < hist.length; i += 2) mv.appendChild(document.createTextNode((i / 2 + 1) + '. ' + hist[i] + (hist[i + 1] ? ' ' + hist[i + 1] : '') + '   '));
        mv.scrollTop = mv.scrollHeight;
    }

    function drawArrows() {
        const svg = ov.querySelector('.chess-arrows'); svg.innerHTML = '';
        const c = sq => { const { f, r } = sqXY(sq); return { x: (st.flip ? 7 - f : f) + 0.5, y: (st.flip ? r : 7 - r) + 0.5 }; };
        st.arrows.forEach(a => {
            const A = c(a.from), B = c(a.to), dx = B.x - A.x, dy = B.y - A.y, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len, hw = 0.2, hl = 0.34, sx = A.x + ux * 0.28, sy = A.y + uy * 0.28, ex = B.x - ux * hl, ey = B.y - uy * hl;
            const ln = document.createElementNS('http://www.w3.org/2000/svg', 'line'); ln.setAttribute('x1', sx); ln.setAttribute('y1', sy); ln.setAttribute('x2', ex); ln.setAttribute('y2', ey); ln.setAttribute('stroke', a.color); ln.setAttribute('stroke-width', '0.17'); ln.setAttribute('stroke-linecap', 'round'); ln.setAttribute('opacity', '0.85');
            const hd = document.createElementNS('http://www.w3.org/2000/svg', 'polygon'); hd.setAttribute('points', `${B.x - ux * 0.08},${B.y - uy * 0.08} ${ex - uy * hw},${ey + ux * hw} ${ex + uy * hw},${ey - ux * hw}`); hd.setAttribute('fill', a.color); hd.setAttribute('opacity', '0.85');
            svg.append(ln, hd);
        });
    }

    function parseMove(text, legal) {   // acha na resposta um lance da lista de lances legais
        const t = String(text || '').replace(/0-0-0/g, 'O-O-O').replace(/0-0/g, 'O-O').replace(/[`*_]/g, ' ');
        const toks = t.split(/[\s,;:()\[\]"'—]+/).map(x => x.replace(/^[.\d]+\.+/, '').replace(/[.!?]+$/, '')).filter(Boolean);
        const set = new Set(legal), strip = s => s.replace(/[+#]/g, '');
        for (const x of toks) if (set.has(x)) return x;
        for (const x of toks) { const m = legal.find(l => strip(l) === strip(x)); if (m) return m; }
        return null;
    }

    async function askModel(messages, signal) {
        const m = st.model, rid = 'chess' + Date.now().toString(36);
        st.rid = rid;
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
        if (!game || game.game_over() || game.turn() === st.human) return;
        const my = st.token; st.thinking = true; st.note = ''; render();
        const color = game.turn() === 'w' ? 'brancas' : 'pretas', legal = game.moves();
        const sys = 'Você joga xadrez de verdade e quer ganhar. Em cada vez, responda SOMENTE com um lance da lista de lances legais, exatamente como está escrito (notação SAN, por exemplo: Nf3, exd5, O-O, e8=Q). Nada de explicação, nada de outro texto.';
        const ask = (extra) => ([{ role: 'system', content: sys }, { role: 'user', content: `Posição (FEN): ${game.fen()}\nLances até agora: ${game.history().join(' ') || '(nenhum, é o primeiro lance)'}\nVocê joga de ${color}.\nLances legais: ${legal.join(', ')}\nResponda só com o seu lance.${extra || ''}` }]);
        let chosen = null, extra = '', ctl = new AbortController(); const to = setTimeout(() => ctl.abort(), 180000);
        try {
            for (let i = 0; i < 3 && !chosen; i++) {
                const text = await askModel(ask(extra), ctl.signal); if (my !== st.token) return;
                if (/^\s*\[Erro/.test(text)) { st.note = text.trim().slice(0, 220); break; }
                chosen = parseMove(text, legal); if (!chosen) extra = `\nA sua resposta anterior ("${String(text).trim().slice(0, 40)}") não era um lance legal. Escolha exatamente um da lista: ${legal.join(', ')}`;
            }
        } catch (e) { if (my !== st.token) return; st.note = T('Não consegui falar com o modelo.'); }
        clearTimeout(to); if (my !== st.token) return;
        st.thinking = false;
        if (!chosen && !st.note) { chosen = legal[Math.floor(Math.random() * legal.length)]; st.note = T('(o modelo não respondeu um lance válido; joguei um lance qualquer por ele)'); }
        if (chosen) { const mv = game.move(chosen); st.last = { from: mv.from, to: mv.to }; st.arrows = []; st.marks = []; }
        render();
    }

    function tryMove(from, to, promo) {
        const mv = game.moves({ verbose: true }).find(m => m.from === from && m.to === to && (!m.promotion || m.promotion === (promo || 'q')));
        if (!mv) return false;
        if (mv.promotion && !promo) { askPromo(from, to); return true; }
        const done = game.move({ from, to, promotion: promo || undefined }); st.last = { from: done.from, to: done.to }; st.sel = null; st.targets = []; st.note = ''; render();
        if (!game.game_over()) aiMove(); return true;
    }
    function askPromo(from, to) {
        const box = mk('div', 'chess-promo'); ['q', 'r', 'b', 'n'].forEach(p => { const b = mk('button', '', GLYPH[p]); b.style.color = st.human === 'w' ? '#fff' : '#151515'; b.style.textShadow = st.human === 'w' ? '0 0 2px #000, 0 0 3px #000' : 'none'; b.onclick = e => { e.stopPropagation(); box.remove(); tryMove(from, to, p); }; box.appendChild(b); });
        ov.querySelector('.chess-board').appendChild(box);
    }

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
        // celular: segurar o dedo numa casa e arrastar desenha a seta
        board.addEventListener('pointerdown', e => { if (e.pointerType !== 'touch') return; const s = sqAt(e); press = setTimeout(() => { press = null; lpress = s; }, 380); });
        board.addEventListener('pointerup', e => { if (e.pointerType !== 'touch') return; if (press) { clearTimeout(press); press = null; } if (lpress) { const to = sqAt(e), from = lpress; lpress = null; if (to && to !== from) { st.arrows.push({ from, to, color: '#15781B' }); render(); } e.preventDefault(); } });
        board.addEventListener('click', e => {
            if (lpress) return; const s = sqAt(e); if (!s || st.thinking) return;
            if (st.arrows.length || st.marks.length) { st.arrows = []; st.marks = []; }
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
        const bsz = Math.max(280, Math.min(560, innerWidth - 56, innerHeight - 120)); wrap.style.setProperty('--cb', bsz + 'px');
        const board = mk('div', 'chess-board'); board.appendChild(document.createElementNS('http://www.w3.org/2000/svg', 'svg')); const svg = board.lastChild; svg.setAttribute('class', 'chess-arrows'); svg.setAttribute('viewBox', '0 0 8 8'); wrap.appendChild(board);
        const side = mk('div', 'chess-side'); wrap.appendChild(side); side.appendChild(mk('h3', '', T('Xadrez contra um modelo')));
        const sel = document.createElement('select'); list.forEach((m, i) => { const o = document.createElement('option'); o.value = i; o.textContent = m.label || m.id; sel.appendChild(o); });
        const cur = list.findIndex(m => m.id === (typeof selectedModel !== 'undefined' ? selectedModel : '')); if (cur >= 0) sel.value = cur; side.appendChild(sel);
        const col = document.createElement('select'); [['w', 'Jogar de brancas'], ['b', 'Jogar de pretas'], ['random', 'Cor aleatória']].forEach(([v, l]) => { const o = document.createElement('option'); o.value = v; o.textContent = T(l); col.appendChild(o); }); side.appendChild(col);
        const row = mk('div', 'chess-row'); side.appendChild(row);
        const btn = (txt, fn) => { const b = mk('button', 'btn btn-secondary', T(txt)); b.type = 'button'; b.onclick = fn; row.appendChild(b); return b; };
        const start = btn('Novo jogo', () => { if (st) st.token = Math.random(); newGame({ model: list[+sel.value], color: col.value }); }); start.classList.replace('btn-secondary', 'btn-primary');
        btn('Desfazer', () => { if (!game || st.thinking) return; game.undo(); if (game.turn() !== st.human) game.undo(); st.over = ''; st.sel = null; st.targets = []; st.last = null; st.arrows = []; render(); });
        btn('Virar', () => { st.flip = !st.flip; render(); });
        btn('Desistir', () => { if (game && !game.game_over() && !st.over) { st.token = Math.random(); st.thinking = false; st.over = T('Você desistiu.'); render(); } });
        btn('Fechar', () => { if (st) st.token = Math.random(); if (st && st.rid) { try { fetch(API + '/api/stop', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rid: st.rid }) }); } catch (e) { /* ok */ } } ov.remove(); ov = null; });
        side.appendChild(mk('div', 'chess-status', '')); side.appendChild(mk('div', 'chess-moves', ''));
        side.appendChild(mk('div', 'chess-hint', T('Botão direito: segure e arraste para desenhar uma seta (Shift vermelha, Ctrl azul, Alt amarela); clique direito numa casa marca a casa; clique esquerdo limpa. No celular: segure o dedo numa casa e arraste.')));
        wire(board); document.body.appendChild(ov);
        newGame({ model: list[+sel.value], color: 'w' });
    }
    window.openChess = open;
    window.__chess = { get game() { return game; }, get st() { return st; }, parseMove };
})();
