/* Jogos com um modelo (botao "Jogos" na lateral; o xadrez continua no botao dele): jogo da velha, forca e 20 perguntas.
   Os jogos usam o lumeAsk (nao mexem nas suas conversas) e o kit LumeUI. O modelo e escolhido no topo de cada jogo.
   Para adicionar outro jogo: coloque um item em GAMES com { id, name, desc, start(host, ask) } e pronto. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const css = document.createElement('style');
    css.textContent = `
        .gm-hub { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 10px; }
        .gm-card { padding: 14px; border-radius: 16px; background: rgba(128,128,128,.12); cursor: pointer; display: flex; flex-direction: column; gap: 4px; transition: background .15s, transform .15s; } .gm-card:hover { background: rgba(128,128,128,.22); transform: translateY(-2px); } .gm-card b { font-size: 1.02em; } .gm-card span { font-size: .8em; color: var(--text-muted); }
        .gm-bar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; } .gm-bar select { flex: 1 1 220px; min-width: 0; }
        .gm-status { padding: 9px 12px; border-radius: 12px; background: rgba(128,128,128,.12); font-size: .92em; min-height: 1.4em; }
        .ttt { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; width: min(300px, 100%); margin: 6px auto; } .ttt button { aspect-ratio: 1; font-size: 2.2em; font-weight: 700; border-radius: 14px; border: 0; cursor: pointer; background: rgba(128,128,128,.16); color: var(--text-main); } .ttt button:hover:not(:disabled) { background: rgba(128,128,128,.28); } .ttt button.x { color: #4d8bff; } .ttt button.o { color: #ff7a59; } .ttt button.win { background: rgba(63,185,80,.3); }
        .hg-word { font-size: 1.9em; letter-spacing: .28em; text-align: center; font-weight: 700; padding: 8px 0; word-break: break-all; } .hg-keys { display: flex; flex-wrap: wrap; gap: 5px; justify-content: center; } .hg-keys button { width: 34px; height: 36px; border-radius: 9px; border: 0; cursor: pointer; background: rgba(128,128,128,.18); color: var(--text-main); font-weight: 600; } .hg-keys button:disabled { opacity: .35; cursor: default; } .hg-keys button.hit { background: rgba(63,185,80,.35); } .hg-keys button.miss { background: rgba(229,72,77,.3); }
        .hg-hang { text-align: center; font-size: 1.1em; letter-spacing: .1em; color: var(--text-muted); }
        .tq-log { display: flex; flex-direction: column; gap: 6px; max-height: 38vh; overflow-y: auto; } .tq-log div { padding: 7px 11px; border-radius: 12px; font-size: .9em; max-width: 90%; } .tq-log .me { align-self: flex-end; background: var(--accent, #4d6bfe); color: #fff; } .tq-log .ai { align-self: flex-start; background: rgba(128,128,128,.16); }
        .tq-in { display: flex; gap: 6px; } .tq-in input { flex: 1; }
    `;
    document.head.appendChild(css);
    const el = (t, c, x) => window.LumeUI.el(t, c, x);

    // ---- escolha do modelo (o mesmo select em todos os jogos)
    function modelBar(host) {
        const u = window.LumeUI, list = (window.lumeModels ? lumeModels() : []).filter(m => !m.phone);
        const bar = el('div', 'gm-bar'); host.appendChild(bar);
        const label = m => { let p = ''; try { p = providerName(m); } catch (e) { /* sem provedor */ } return (m.label || m.id) + (p ? ' · ' + p : ''); };
        const sel = u.select(list.map(m => [m.id, label(m)]), '', () => {}); const cur = typeof selectedModel !== 'undefined' ? list.find(m => m.id === selectedModel) : null; sel.value = (cur || list[0] || {}).id || ''; bar.appendChild(sel);
        return { bar, sel, model: () => lumeModelById(sel.value) };
    }
    const ask = (model, system, user) => lumeAsk({ model, system, user, timeoutMs: 60000 });

    // ---- jogo da velha: voce e X, o modelo e O (responde com o numero da casa)
    const LINES = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]];
    const winner = b => { for (const [a, c, d] of LINES) if (b[a] && b[a] === b[c] && b[a] === b[d]) return [b[a], [a, c, d]]; return null; };
    function startTTT(host) {
        const mb = modelBar(host); let board = Array(9).fill(''), over = false, busy = false;
        const status = el('div', 'gm-status', ''), grid = el('div', 'ttt'); host.append(status, grid); const btns = [];
        for (let i = 0; i < 9; i++) { const b = el('button'); b.type = 'button'; b.onclick = () => play(i); grid.appendChild(b); btns.push(b); }
        const draw = (win) => btns.forEach((b, i) => { b.textContent = board[i]; b.className = board[i].toLowerCase() + (win && win[1].includes(i) ? ' win' : ''); b.disabled = !!board[i] || over || busy; });
        const end = () => { const w = winner(board); if (w) { over = true; status.textContent = w[0] === 'X' ? T('Você ganhou! 🎉') : T('O modelo ganhou.'); draw(w); return true; } if (board.every(Boolean)) { over = true; status.textContent = T('Deu velha (empate).'); draw(); return true; } return false; };
        async function play(i) {
            if (over || busy || board[i]) return; board[i] = 'X'; if (end()) return; busy = true; status.textContent = T('O modelo está pensando…'); draw();
            const free = board.map((v, k) => v ? null : k + 1).filter(Boolean); let pick = null;
            try { for (let t = 0; t < 2 && !pick; t++) { const r = await ask(mb.model(), 'Você joga jogo da velha como O contra X. As casas são numeradas de 1 a 9 (linha por linha, de cima para baixo). Responda SOMENTE com o número de uma casa livre. Nada mais.', 'Tabuleiro (X, O ou . para livre): ' + board.map(v => v || '.').join('') + '\nCasas livres: ' + free.join(', ')); const n = parseInt((r.match(/[1-9]/) || [])[0], 10); if (free.includes(n)) pick = n; } } catch (e) { status.textContent = T('Erro do modelo: ') + String(e.message || e).slice(0, 100) + ' — ' + T('joguei por ele.'); }
            if (!pick) pick = free[Math.floor(Math.random() * free.length)];
            board[pick - 1] = 'O'; busy = false; if (!end()) { status.textContent = T('Sua vez (você é o X).'); draw(); }
        }
        u_button(host, 'Novo jogo', () => { board = Array(9).fill(''); over = false; busy = false; status.textContent = T('Sua vez (você é o X).'); draw(); });
        status.textContent = T('Sua vez (você é o X).'); draw();
    }
    const u_button = (host, t, fn) => window.LumeUI.button(host, t, fn);

    // ---- forca: o modelo escolhe a palavra (guardada aqui, sem ele "mudar de ideia")
    const WORDS = [['abacaxi', 'fruta'], ['elefante', 'animal'], ['guitarra', 'instrumento'], ['computador', 'objeto'], ['montanha', 'lugar'], ['borboleta', 'inseto'], ['biblioteca', 'lugar'], ['chocolate', 'comida']];
    function startHangman(host) {
        const mb = modelBar(host); const status = el('div', 'gm-status', ''), hang = el('div', 'hg-hang', ''), word = el('div', 'hg-word', ''), keys = el('div', 'hg-keys'); host.append(status, hang, word, keys);
        let secret = '', hint = '', guessed = new Set(), wrong = 0, over = false; const MAX = 6, FACE = ['😀', '😐', '😟', '😨', '😰', '😵', '💀'];
        const norm = s => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase();
        const draw = () => {
            word.textContent = [...secret].map(ch => (guessed.has(norm(ch)) || over ? ch.toUpperCase() : '_')).join(' '); hang.textContent = FACE[wrong] + '  ' + T('erros') + ': ' + wrong + '/' + MAX;
            keys.textContent = ''; 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').forEach(L => { const b = el('button', guessed.has(L) ? (norm(secret).includes(L) ? 'hit' : 'miss') : '', L); b.type = 'button'; b.disabled = guessed.has(L) || over || !secret; b.onclick = () => guess(L); keys.appendChild(b); });
        };
        function guess(L) { guessed.add(L); if (!norm(secret).includes(L)) wrong++; if ([...norm(secret)].every(c => guessed.has(c))) { over = true; status.textContent = T('Você acertou! 🎉'); } else if (wrong >= MAX) { over = true; status.textContent = T('Perdeu! A palavra era: ') + secret.toUpperCase(); } draw(); }
        async function fresh() {
            over = false; guessed = new Set(); wrong = 0; secret = ''; status.textContent = T('O modelo está escolhendo uma palavra…'); draw();
            try { const r = await ask(mb.model(), 'Você vai ser o mestre de um jogo da forca em português. Escolha UMA palavra comum, de 5 a 10 letras, sem hífen e sem espaço. Responda SOMENTE com JSON: {"palavra":"...","dica":"categoria em poucas palavras"}', 'Escolha uma palavra aleatória e diferente.'); const j = JSON.parse((r.match(/\{[\s\S]*\}/) || ['{}'])[0]); if (/^[a-zA-ZÀ-ÿ]{4,12}$/.test(j.palavra || '')) { secret = j.palavra; hint = String(j.dica || '').slice(0, 40); } } catch (e) { /* usa a lista */ }
            if (!secret) { const w = WORDS[Math.floor(Math.random() * WORDS.length)]; secret = w[0]; hint = w[1]; }
            status.textContent = T('Dica: ') + hint + '. ' + T('Escolha as letras.'); draw();
        }
        u_button(host, 'Nova palavra', fresh); fresh();
    }

    // ---- 20 perguntas: o modelo pensa em algo (segredo guardado aqui); voce pergunta, ele responde Sim/Nao/Talvez
    function startTwenty(host) {
        const mb = modelBar(host); const status = el('div', 'gm-status', ''), log = el('div', 'tq-log'), inp = el('div', 'tq-in'); const input = el('input'); input.type = 'text'; input.placeholder = T('Pergunte (sim ou não) ou arrisque: "é um cachorro?"'); const go = u_button(inp, 'Enviar', () => send()); inp.insertBefore(input, go); host.append(status, log, inp);
        let secret = '', n = 0, over = false, busy = false;
        const add = (cls, t) => { log.appendChild(el('div', cls, t)); log.scrollTop = log.scrollHeight; };
        async function fresh() {
            over = false; n = 0; log.textContent = ''; secret = ''; busy = true; status.textContent = T('O modelo está pensando em algo…');
            try { const r = await ask(mb.model(), 'Você é o mestre do jogo "20 perguntas". Pense em UMA coisa conhecida (animal, objeto, lugar ou pessoa famosa). Responda SOMENTE com JSON: {"segredo":"...","categoria":"animal|objeto|lugar|pessoa"}', 'Pense em algo diferente.'); const j = JSON.parse((r.match(/\{[\s\S]*\}/) || ['{}'])[0]); if (j.segredo) secret = String(j.segredo).slice(0, 40); status.textContent = T('Pensei em algo! Categoria: ') + (j.categoria || '?') + '. ' + T('Você tem 20 perguntas.'); } catch (e) { status.textContent = T('Erro do modelo: ') + String(e.message || e).slice(0, 100); }
            busy = false;
        }
        async function send() {
            const q = input.value.trim(); if (!q || over || busy || !secret) return; input.value = ''; add('me', q); busy = true; n++;
            try { const r = await ask(mb.model(), 'Você é o mestre do jogo "20 perguntas". O segredo é: "' + secret + '". Responda SOMENTE com uma destas palavras: SIM, NÃO, TALVEZ, ou ACERTOU (se o jogador disse exatamente o segredo, ou um sinônimo óbvio). Nunca revele o segredo.', q);
                const a = r.toUpperCase().replace(/Ã/g, 'A'); if (/ACERTOU/.test(a)) { over = true; add('ai', T('Acertou! Era: ') + secret + ' 🎉'); status.textContent = T('Você venceu em ') + n + T(' perguntas!'); } else { add('ai', /^SIM/.test(a) ? T('Sim') : /^NAO/.test(a) ? T('Não') : /TALVEZ/.test(a) ? T('Talvez') : r.slice(0, 60)); if (n >= 20) { over = true; add('ai', T('Acabaram as perguntas! Era: ') + secret); status.textContent = T('Fim de jogo.'); } else status.textContent = T('Pergunta ') + n + '/20'; } } catch (e) { add('ai', T('Erro: ') + String(e.message || e).slice(0, 80)); }
            busy = false;
        }
        input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
        u_button(host, 'Novo jogo', fresh); fresh();
    }

    const GAMES = [
        { id: 'ttt', name: 'Jogo da velha', desc: 'Você é o X; o modelo joga de O.', start: startTTT },
        { id: 'hangman', name: 'Forca', desc: 'O modelo escolhe a palavra e uma dica.', start: startHangman },
        { id: 'twenty', name: '20 perguntas', desc: 'O modelo pensa em algo; você descobre.', start: startTwenty },
    ];
    window.LUME_GAMES = GAMES;
    window.openGames = function (only) {
        if (document.getElementById('gm-modal')) return;
        const u = window.LumeUI, w = u.modal({ title: 'Jogos', id: 'gm-modal', width: 560 });
        if (!(window.lumeModels && lumeModels().length)) { w.body.appendChild(el('div', 'lu-hint', T('Preciso de um modelo disponível. Configure uma chave ou ligue o Ollama.'))); return; }
        const hub = () => { w.body.textContent = ''; const g = el('div', 'gm-hub'); w.body.appendChild(g);
            GAMES.forEach(x => { const c = el('div', 'gm-card'); c.append(el('b', '', T(x.name)), el('span', '', T(x.desc))); c.onclick = () => open(x); g.appendChild(c); });
            const c = el('div', 'gm-card'); c.append(el('b', '', T('Xadrez')), el('span', '', T('Contra qualquer modelo, com análise e peças.'))); c.onclick = () => { w.close(); window.openChess && window.openChess(); }; g.appendChild(c); };
        const open = x => { w.body.textContent = ''; const back = u.button(w.body, '← Jogos', hub); const host = el('div'); host.style.cssText = 'display:flex;flex-direction:column;gap:10px'; w.body.appendChild(host); x.start(host); };
        const g = GAMES.find(x => x.id === only); if (g) open(g); else hub();
    };
})();
