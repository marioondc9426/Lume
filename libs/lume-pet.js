/* Mascote do Lume: uma bolinha com olhos que segue o cursor, pisca, dorme, fica pensando enquanto a IA responde e comemora quando ela termina.
   Customizavel (nome, cor, estilo Bolha ou LED de pontinhos, olhos, tamanho, balao); a escolha fica em localStorage ('lume_pet'). Arraste para mudar de lugar; clique para ele reagir. */
(() => {
    'use strict';
    const KEY = 'lume_pet', T = s => (typeof tr === 'function' ? tr(s) : s);
    const DEF = { on: false, avatar: true, name: 'Lume', color: '#2f8bff', style: 'orb', eyes: 'oval', size: 64, bubble: true, x: null, y: null };
    const load = () => { try { return Object.assign({}, DEF, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) { return Object.assign({}, DEF); } };
    const save = () => { try { localStorage.setItem(KEY, JSON.stringify(cfg)); } catch (e) { /* sem armazenamento */ } };
    let cfg = load(), root = null, body = null, cv = null, bub = null, mood = 'idle', look = { x: 0, y: 0 }, blink = false, lastMove = Date.now(), bubTimer = 0, moodTimer = 0, wasBusy = false;

    const hex = c => { const m = /^#?([0-9a-f]{6})$/i.exec(c || ''); const n = parseInt(m ? m[1] : 'ee5a8a', 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
    const mix = (c, t, k) => { const a = hex(c); return 'rgb(' + a.map((v, i) => Math.round(v + (t[i] - v) * k)).join(',') + ')'; };
    const rgba = (c, a) => 'rgba(' + hex(c).join(',') + ',' + a + ')';

    const css = document.createElement('style');
    css.textContent = `
        #lume-pet { position: fixed; z-index: 4400; touch-action: none; user-select: none; -webkit-user-select: none; cursor: grab; transition: opacity .3s; }
        #lume-pet.drag { cursor: grabbing; } #lume-pet.hide { display: none; }
        #lume-pet .lp-body { position: relative; width: 100%; height: 100%; border-radius: 50%; animation: lpBob 3.4s ease-in-out infinite; }
        #lume-pet.thinking .lp-body { animation: lpThink 1.1s ease-in-out infinite; } #lume-pet.happy .lp-body { animation: lpJump .55s ease; } #lume-pet.sleep .lp-body { animation: lpSleep 4s ease-in-out infinite; }
        #lume-pet.orb .lp-body { box-shadow: 0 0 0 3px rgba(255,255,255,.22), 0 6px 18px rgba(0,0,0,.45), 0 0 22px var(--lp-glow); }
        #lume-pet .lp-eye { position: absolute; top: 36%; width: 15%; height: 26%; background: #fff; border-radius: 50%; transition: transform .12s ease-out, height .08s, border-radius .2s; box-shadow: 0 0 6px rgba(255,255,255,.7); }
        #lume-pet .lp-eye.l { left: 30%; } #lume-pet .lp-eye.r { right: 30%; }
        #lume-pet.eyes-round .lp-eye { width: 20%; height: 20%; top: 40%; } #lume-pet.eyes-dot .lp-eye { width: 9%; height: 9%; top: 46%; } #lume-pet.eyes-wide .lp-eye { width: 19%; height: 32%; top: 32%; border-radius: 45%; }
        #lume-pet .lp-eye.blink { height: 4% !important; top: 48% !important; border-radius: 4px; }
        #lume-pet.happy .lp-eye, #lume-pet.sleep .lp-eye { height: 8%; top: 46%; background: transparent; border-top: 3px solid #fff; border-radius: 50% 50% 0 0; box-shadow: none; }
        #lume-pet.sleep .lp-eye { border-top: 0; border-bottom: 3px solid #fff; border-radius: 0 0 50% 50%; top: 44%; }
        #lume-pet canvas { width: 100%; height: 100%; display: block; animation: lpBob 3.4s ease-in-out infinite; } #lume-pet.thinking canvas { animation: lpThink 1.1s ease-in-out infinite; } #lume-pet.happy canvas { animation: lpJump .55s ease; }
        #lume-pet .lp-bub { position: absolute; bottom: calc(100% + 8px); right: 0; max-width: 220px; white-space: nowrap; padding: 6px 12px; border-radius: 14px; background: var(--bg-input, #2a2a2e); color: var(--text-main, #eee); border: 1px solid var(--border-color, #444); font-size: 12.5px; box-shadow: 0 6px 18px rgba(0,0,0,.4); opacity: 0; transform: translateY(6px) scale(.96); transition: opacity .2s, transform .2s; pointer-events: none; }
        #lume-pet .lp-bub.on { opacity: 1; transform: none; }
        @keyframes lpBob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } } @keyframes lpThink { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.07); } } @keyframes lpSleep { 0%, 100% { transform: scale(1); } 50% { transform: scale(.96); } }
        @keyframes lpJump { 0% { transform: translateY(0) scale(1); } 30% { transform: translateY(-18px) scale(.95, 1.06); } 60% { transform: translateY(0) scale(1.08, .92); } 100% { transform: translateY(0) scale(1); } }
        @media (prefers-reduced-motion: reduce) { #lume-pet .lp-body, #lume-pet canvas { animation: none !important; } }
        body.pet-av .msg.ai { padding-left: 52px; } body.pet-av .msg.ai > .lp-av { position: absolute; left: 10px; top: 14px; }
        .lp-av { width: 30px; height: 30px; border-radius: 50%; flex: none; position: relative; --lp-lx: 0; --lp-ly: 0; box-shadow: 0 0 0 2px rgba(255,255,255,.22), 0 0 12px var(--lp-glow, rgba(238,90,138,.5)); }
        .lp-av.led { background-image: radial-gradient(circle, var(--lp-c) 0 38%, transparent 42%); background-size: 3.4px 3.4px; box-shadow: none; -webkit-mask-image: radial-gradient(circle, #000 55%, transparent 74%); mask-image: radial-gradient(circle, #000 55%, transparent 74%); }
        .lp-av i { position: absolute; top: 36%; width: 15%; height: 26%; background: #fff; border-radius: 50%; box-shadow: 0 0 5px rgba(255,255,255,.7); transform: translate(calc(var(--lp-lx) * 2.2px), calc(var(--lp-ly) * 2px)); transition: transform .14s ease-out, height .08s; } .lp-av i.l { left: 30%; } .lp-av i.r { right: 30%; }
        .lp-av.eyes-round i { width: 20%; height: 20%; top: 40%; } .lp-av.eyes-dot i { width: 9%; height: 9%; top: 46%; } .lp-av.eyes-wide i { width: 19%; height: 32%; top: 32%; border-radius: 45%; }
        .lp-av.blink i { height: 4% !important; top: 48% !important; border-radius: 3px; } .lp-av.thinking { animation: lpThink 1.1s ease-in-out infinite; }
        #lp-modal { position: fixed; inset: 0; z-index: 6600; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,.5); padding: 12px; }
        #lp-modal .lp-card { width: min(380px, 100%); max-height: 100%; overflow: auto; background: var(--bg-main); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 18px; padding: 16px; display: flex; flex-direction: column; gap: 10px; box-shadow: 0 20px 60px rgba(0,0,0,.55); }
        #lp-modal h3 { margin: 0; } #lp-modal .lp-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: .9em; } #lp-modal .lp-row > :last-child { flex: 0 1 190px; min-width: 0; }
        #lp-modal input[type=text], #lp-modal select { width: 100%; } #lp-modal input[type=color] { width: 44px; height: 30px; padding: 0; border: 1px solid var(--border-color); border-radius: 8px; background: none; }
        #lp-modal .lp-sw { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; } #lp-modal .lp-sw button { width: 22px; height: 22px; border-radius: 50%; border: 2px solid rgba(255,255,255,.25); cursor: pointer; padding: 0; }
        #lp-modal .lp-btns { display: flex; gap: 8px; justify-content: flex-end; } #lp-modal .lp-btns .btn { margin: 0; }
    `;
    document.head.appendChild(css);

    const phrases = () => [T('Oi!'), T('Bora conversar?'), T('Estou de olho 👀'), T('Pode perguntar!'), T('Hmm, e se a gente jogasse xadrez?'), T('Eu sou só um mascote, mas torço por você.')];
    function say(text, ms) { if (!cfg.bubble || !bub) return; bub.textContent = text; bub.classList.add('on'); clearTimeout(bubTimer); bubTimer = setTimeout(() => bub && bub.classList.remove('on'), ms || 2200); }
    function setMood(m, ms) { clearTimeout(moodTimer); mood = m; paint(); if (ms) moodTimer = setTimeout(() => { mood = 'idle'; paint(); }, ms); }

    function build() {
        if (root) root.remove();
        root = document.createElement('div'); root.id = 'lume-pet'; root.title = cfg.name;
        bub = document.createElement('div'); bub.className = 'lp-bub'; root.appendChild(bub);
        if (cfg.style === 'led') { cv = document.createElement('canvas'); root.appendChild(cv); body = null; }
        else { body = document.createElement('div'); body.className = 'lp-body'; ['l', 'r'].forEach(s => { const e = document.createElement('i'); e.className = 'lp-eye ' + s; body.appendChild(e); }); root.appendChild(body); cv = null; }
        document.body.appendChild(root); place(); paint(); wire();
    }
    function place() {
        const s = cfg.size; root.style.width = root.style.height = s + 'px';
        if (cfg.x == null) { root.style.right = '18px'; root.style.bottom = '96px'; root.style.left = root.style.top = 'auto'; }
        else { const x = Math.min(Math.max(0, cfg.x), innerWidth - s), y = Math.min(Math.max(0, cfg.y), innerHeight - s); root.style.left = x + 'px'; root.style.top = y + 'px'; root.style.right = root.style.bottom = 'auto'; }
        if (root.style.left !== 'auto' && cfg.x != null) bub.style.right = 'auto', bub.style.left = '0'; else bub.style.right = '0', bub.style.left = 'auto';
    }
    function paint() {
        if (!root) return;
        root.className = [cfg.style, mood, 'eyes-' + cfg.eyes].join(' ') + (cfg.on ? '' : ' hide');
        root.style.setProperty('--lp-glow', rgba(cfg.color, .55));
        if (body) {
            body.style.background = 'radial-gradient(circle at 34% 26%, ' + mix(cfg.color, [255, 255, 255], .55) + ' 0%, ' + cfg.color + ' 48%, ' + mix(cfg.color, [0, 0, 0], .42) + ' 100%)';
            const eyes = body.querySelectorAll('.lp-eye'), t = mood === 'thinking' ? { x: -.7, y: -1 } : look;
            eyes.forEach(e => { e.style.transform = 'translate(' + (t.x * root.clientWidth * .07).toFixed(1) + 'px,' + (t.y * root.clientHeight * .06).toFixed(1) + 'px)'; e.classList.toggle('blink', blink && mood === 'idle'); });
        } else drawLed();
    }
    function drawLed() {   // LED de pontinhos: 13x13, bordas esmaecidas e olhos brancos
        const N = 13, px = Math.max(60, cfg.size) * (window.devicePixelRatio || 1); cv.width = cv.height = px; const g = cv.getContext('2d'); g.clearRect(0, 0, px, px);
        const cell = px / N, c = (N - 1) / 2, R = 6.2, t = mood === 'thinking' ? { x: -1, y: -1 } : { x: Math.round(look.x), y: Math.round(look.y) };
        const eyeCols = [[4, 5], [8, 9]], rows = mood === 'happy' ? [5] : (blink && mood === 'idle') || mood === 'sleep' ? [6] : [4, 5, 6];
        const isEye = (i, j) => eyeCols.some(cs => cs.some(cx => cx + t.x === i)) && rows.some(r => r + t.y === j);
        for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
            const d = Math.hypot(i - c, j - c); if (d > R + .6) continue; const a = Math.max(.12, Math.min(1, (R + .7 - d) / 2.4));
            const eye = isEye(i, j), inner = eyeCols.some(cs => cs[0] + t.x === i) && eye;
            g.fillStyle = eye ? (inner ? '#fff' : 'rgba(225,235,255,.9)') : rgba(cfg.color, a); g.beginPath(); g.arc((i + .5) * cell, (j + .5) * cell, cell * (eye ? .42 : .36), 0, 6.2832); g.fill();
        }
    }
    function wire() {
        let drag = null;
        root.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, ox: root.getBoundingClientRect().left, oy: root.getBoundingClientRect().top, moved: false }; try { root.setPointerCapture(e.pointerId); } catch (x) { /* ok */ } });
        root.addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!drag.moved && Math.hypot(dx, dy) < 5) return; drag.moved = true; root.classList.add('drag'); cfg.x = drag.ox + dx; cfg.y = drag.oy + dy; place(); });
        root.addEventListener('pointerup', () => { if (!drag) return; const d = drag; drag = null; root.classList.remove('drag'); if (d.moved) { save(); return; } const p = phrases(); say(p[Math.floor(Math.random() * p.length)]); setMood('happy', 600); });
    }
    addEventListener('pointermove', e => {
        lastMove = Date.now(); if (!root || !cfg.on) return; if (mood === 'sleep') setMood('idle');
        const r = root.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2), d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 160);
        const nx = +(dx / d * k).toFixed(2), ny = +(dy / d * k).toFixed(2); if (nx !== look.x || ny !== look.y) { look = { x: nx, y: ny }; if (mood === 'idle') paint(); }
    }, { passive: true });
    addEventListener('resize', () => { if (root) place(); });
    setInterval(() => {   // piscar, dormir e reagir ao que a IA esta fazendo
        if (!root || !cfg.on) return;
        let b = false; try { b = typeof busy !== 'undefined' && !!busy; } catch (e) { b = false; }
        if (b && !wasBusy) { wasBusy = true; setMood('thinking'); say(T('Pensando…'), 1800); }
        else if (!b && wasBusy) { wasBusy = false; setMood('happy', 1600); say(T('Pronto!'), 1800); }
        else if (!b && mood === 'idle' && Date.now() - lastMove > 90000) { setMood('sleep'); }
    }, 300);
    (function blinker() { setTimeout(() => { if (root && cfg.on && mood === 'idle') { blink = true; paint(); setTimeout(() => { blink = false; paint(); }, 140); } blinker(); }, 2500 + Math.random() * 3500); })();

    // ---- avatar ao lado de cada resposta da IA (a bolinha dos chats do Kimi): mesma cor/estilo/olhos do mascote
    const avs = new Set(); let typing = false, avObs = null;
    function styleAv(a) {
        a.className = 'lp-av ' + cfg.style + ' eyes-' + cfg.eyes + (a.dataset.th === '1' ? ' thinking' : '');
        a.style.setProperty('--lp-c', cfg.color); a.style.setProperty('--lp-glow', rgba(cfg.color, .55));
        if (cfg.style !== 'led') a.style.background = 'radial-gradient(circle at 34% 26%, ' + mix(cfg.color, [255, 255, 255], .55) + ' 0%, ' + cfg.color + ' 48%, ' + mix(cfg.color, [0, 0, 0], .42) + ' 100%)'; else a.style.background = '';
    }
    function addAv(msg) {
        if (msg.querySelector(':scope > .lp-av')) return; const a = document.createElement('span'); a.title = cfg.name; ['l', 'r'].forEach(c => { const e = document.createElement('i'); e.className = c; a.appendChild(e); }); styleAv(a); msg.insertBefore(a, msg.firstChild); avs.add(a);
    }
    function scanAv() { const chat = document.getElementById('chat'); if (!chat) return; document.body.classList.toggle('pet-av', !!cfg.avatar); if (!cfg.avatar) return; chat.querySelectorAll('.msg.ai').forEach(addAv); }
    function refreshAv() { avs.forEach(a => { if (!a.isConnected) avs.delete(a); else if (cfg.avatar) styleAv(a); else a.remove(); }); document.body.classList.toggle('pet-av', !!cfg.avatar); scanAv(); }
    function lookAv(x, y) { document.body.style.setProperty('--lp-lx', x); document.body.style.setProperty('--lp-ly', y); avs.forEach(a => { a.style.setProperty('--lp-lx', x); a.style.setProperty('--lp-ly', y); }); }
    function initAv() {
        const chat = document.getElementById('chat'), inp = document.getElementById('prompt'); if (!chat) return;
        avObs = new MutationObserver(() => scanAv()); avObs.observe(chat, { childList: true }); scanAv();
        if (inp) { const upd = () => { typing = document.activeElement === inp && inp.value.length > 0; if (typing) lookAv(0, 1.1); }; inp.addEventListener('input', upd); inp.addEventListener('focus', upd); inp.addEventListener('blur', () => { typing = false; }); }
        addEventListener('pointermove', e => {   // olha para o cursor (a menos que a pessoa esteja digitando: ai olha para baixo, para a mensagem)
            if (typing) return; const last = [...avs].filter(a => a.isConnected).pop(); if (!last) return; const r = last.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2), d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 200);
            lookAv(+(dx / d * k).toFixed(2), +(dy / d * k).toFixed(2));
        }, { passive: true });
        setInterval(() => {   // piscar e "pensando" no ultimo avatar enquanto a IA responde
            const list = [...avs].filter(a => a.isConnected), last = list[list.length - 1]; let b = false; try { b = typeof busy !== 'undefined' && !!busy; } catch (e) { b = false; }
            list.forEach(a => { const th = a === last && b ? '1' : '0'; if (a.dataset.th !== th) { a.dataset.th = th; a.classList.toggle('thinking', th === '1'); } });
            if (list.length && Math.random() < 0.12) { const a = list[Math.floor(Math.random() * list.length)]; a.classList.add('blink'); setTimeout(() => a.classList.remove('blink'), 140); }
        }, 700);
    }
    function openSettings() {
        if (document.getElementById('lp-modal')) return;
        const m = document.createElement('div'); m.id = 'lp-modal'; const card = document.createElement('div'); card.className = 'lp-card'; m.appendChild(card);
        const row = (label, el) => { const r = document.createElement('div'); r.className = 'lp-row'; const l = document.createElement('span'); l.textContent = T(label); r.append(l, el); card.appendChild(r); return r; };
        const apply = rebuild => { save(); if (rebuild) build(); else { place(); paint(); } refreshAv(); };
        card.appendChild(Object.assign(document.createElement('h3'), { textContent: T('Mascote') }));
        const av = document.createElement('input'); av.type = 'checkbox'; av.checked = cfg.avatar; av.onchange = () => { cfg.avatar = av.checked; apply(); }; row('Ao lado das respostas da IA', av);
        const on = document.createElement('input'); on.type = 'checkbox'; on.checked = cfg.on; on.onchange = () => { cfg.on = on.checked; apply(); }; row('Flutuando na tela', on);
        const nm = document.createElement('input'); nm.type = 'text'; nm.maxLength = 20; nm.value = cfg.name; nm.onchange = () => { cfg.name = nm.value.trim() || 'Lume'; if (root) root.title = cfg.name; save(); say(T('Oi, eu sou {n}!').replace('{n}', cfg.name)); }; row('Nome', nm);
        const sw = document.createElement('div'); sw.className = 'lp-sw'; ['#ee5a8a', '#2f8bff', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#14b8a6', '#9ca3af'].forEach(c => { const b = document.createElement('button'); b.type = 'button'; b.style.background = c; b.onclick = () => { cfg.color = c; col.value = c; apply(); }; sw.appendChild(b); });
        const col = document.createElement('input'); col.type = 'color'; col.value = cfg.color; col.oninput = () => { cfg.color = col.value; apply(); }; const cw = document.createElement('div'); cw.style.cssText = 'display:flex;flex-direction:column;gap:8px;align-items:flex-end'; cw.append(sw, col); row('Cor', cw);
        const sel = (opts, val, fn) => { const s = document.createElement('select'); opts.forEach(([v, l]) => s.add(new Option(T(l), v))); s.value = val; s.onchange = () => fn(s.value); return s; };
        row('Estilo', sel([['orb', 'Bolha brilhante'], ['led', 'LED de pontinhos']], cfg.style, v => { cfg.style = v; apply(true); }));
        row('Olhos (bolha)', sel([['oval', 'Ovais'], ['round', 'Redondos'], ['wide', 'Grandes'], ['dot', 'Pontinhos']], cfg.eyes, v => { cfg.eyes = v; apply(); }));
        const sz = document.createElement('input'); sz.type = 'range'; sz.min = 40; sz.max = 140; sz.value = cfg.size; sz.oninput = () => { cfg.size = +sz.value; apply(); }; row('Tamanho', sz);
        const bb = document.createElement('input'); bb.type = 'checkbox'; bb.checked = cfg.bubble; bb.onchange = () => { cfg.bubble = bb.checked; save(); }; row('Balões de fala', bb);
        const btns = document.createElement('div'); btns.className = 'lp-btns';
        const reset = document.createElement('button'); reset.type = 'button'; reset.className = 'btn btn-secondary'; reset.textContent = T('Restaurar'); reset.onclick = () => { cfg = Object.assign({}, DEF); save(); build(); m.remove(); };
        const pos = document.createElement('button'); pos.type = 'button'; pos.className = 'btn btn-secondary'; pos.textContent = T('Voltar ao canto'); pos.onclick = () => { cfg.x = cfg.y = null; apply(); };
        const ok = document.createElement('button'); ok.type = 'button'; ok.className = 'btn btn-primary'; ok.textContent = T('Fechar'); ok.onclick = () => m.remove();
        btns.append(reset, pos, ok); card.appendChild(btns); m.addEventListener('mousedown', e => { if (e.target === m) m.remove(); }); document.body.appendChild(m);
    }
    window.lumePet = { openSettings, get config() { return cfg; }, say, setMood };
    const start = () => { build(); initAv(); if (cfg.on) setTimeout(() => say(T('Oi, eu sou {n}!').replace('{n}', cfg.name), 2600), 1800); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
