/* Mascote do Lume: a bolinha com olhos que aparece ao lado de cada resposta da IA (e, se quiser, flutuando na tela).
   Os olhos seguem o cursor, piscam, olham para baixo (para a mensagem) quando voce digita, ficam pensando enquanto a IA responde, comemoram quando ela termina e dormem quando fica parado.
   Muito customizavel (Configuracoes > Geral > Mascote, ou clique no mascote de uma resposta): expressao, cor, cor dos olhos, formato, acessorios, brilho, tamanho...
   A escolha fica em localStorage ('lume_pet'). Arraste o flutuante para mudar de lugar; clique para ele falar. */
(() => {
    'use strict';
    const KEY = 'lume_pet', T = s => (typeof tr === 'function' ? tr(s) : s);
    const DEF = { on: false, avatar: true, name: 'Lume', color: '#2f8bff', eyeColor: '#ffffff', style: 'orb', eyes: 'oval', expr: 'neutral', shape: 'circle', acc: 'none', blush: false, glow: 60, size: 64, avSize: 30, bubble: true, follow: true, blinking: true, bob: true, react: true, x: null, y: null };
    const load = () => { try { return Object.assign({}, DEF, JSON.parse(localStorage.getItem(KEY) || '{}')); } catch (e) { return Object.assign({}, DEF); } };
    const save = () => { try { localStorage.setItem(KEY, JSON.stringify(cfg)); } catch (e) { /* sem armazenamento */ } };
    let cfg = load(), root = null, pet = null, bub = null, mood = 'idle', look = { x: 0, y: 0 }, lastMove = Date.now(), bubTimer = 0, moodTimer = 0, wasBusy = false, typing = false;
    const pets = new Set();   // todos os bonecos vivos (flutuante, avatares, previa)

    const hex = c => { const m = /^#?([0-9a-f]{6})$/i.exec(c || ''); const n = parseInt(m ? m[1] : '2f8bff', 16); return [n >> 16, (n >> 8) & 255, n & 255]; };
    const mix = (c, t, k) => { const a = hex(c); return 'rgb(' + a.map((v, i) => Math.round(v + (t[i] - v) * k)).join(',') + ')'; };
    const rgba = (c, a) => 'rgba(' + hex(c).join(',') + ',' + a + ')';

    const EXPR = [['neutral', 'Normal'], ['happy', 'Feliz'], ['wink', 'Piscando'], ['love', 'Apaixonado'], ['surprised', 'Surpreso'], ['sleepy', 'Sonolento'], ['angry', 'Bravo'], ['sad', 'Triste'], ['smug', 'Convencido'], ['dead', 'Fora de combate']];
    const ACC = {
        glasses: '<g fill="rgba(255,255,255,.14)" stroke="#15151a" stroke-width="5"><circle cx="31" cy="47" r="14"/><circle cx="69" cy="47" r="14"/></g><path d="M45 46Q50 41 55 46" fill="none" stroke="#15151a" stroke-width="5"/>',
        sunglasses: '<g fill="#101014"><rect x="12" y="35" width="35" height="22" rx="9"/><rect x="53" y="35" width="35" height="22" rx="9"/><rect x="45" y="40" width="10" height="5"/></g><path d="M20 40l10 0" stroke="rgba(255,255,255,.35)" stroke-width="3" stroke-linecap="round"/>',
        party: '<path d="M50 -26L28 13H72Z" fill="#ff5c8a"/><path d="M38 -4L62 -4" stroke="#ffd166" stroke-width="6"/><circle cx="50" cy="-28" r="6" fill="#ffd166"/>',
        crown: '<path d="M22 14L27 -14L41 2L50 -20L59 2L73 -14L78 14Z" fill="#ffd166" stroke="#c99700" stroke-width="3" stroke-linejoin="round"/>',
        headphones: '<path d="M9 56A41 44 0 0 1 91 56" fill="none" stroke="#202026" stroke-width="7"/><rect x="0" y="48" width="15" height="28" rx="7" fill="#33333b"/><rect x="85" y="48" width="15" height="28" rx="7" fill="#33333b"/>',
        bow: '<path d="M64 8L84 -6V22Z" fill="#ff5c8a"/><path d="M84 8L104 -6V22Z" fill="#ff5c8a"/><circle cx="84" cy="8" r="5" fill="#ff2e6e"/>',
        halo: '<ellipse cx="50" cy="-12" rx="22" ry="6" fill="none" stroke="#ffd166" stroke-width="5"/>',
        cat: '<path d="M14 24L18 -10L40 8Z" fill="currentColor"/><path d="M86 24L82 -10L60 8Z" fill="currentColor"/>',
        antenna: '<path d="M50 2V-18" stroke="#9aa0a6" stroke-width="4"/><circle cx="50" cy="-22" r="6" fill="#ff5c8a"/>'
    };
    const ACC_NAMES = [['none', 'Nenhum'], ['glasses', 'Óculos'], ['sunglasses', 'Óculos escuros'], ['party', 'Chapéu de festa'], ['crown', 'Coroa'], ['headphones', 'Fones'], ['bow', 'Laço'], ['halo', 'Auréola'], ['cat', 'Orelhas de gato'], ['antenna', 'Antena']];

    const css = document.createElement('style');
    css.textContent = `
        .lp-pet { position: relative; width: 100%; height: 100%; --lp-lx: 0; --lp-ly: 0; --lp-c: #2f8bff; --lp-e: #fff; --lp-s: 1; color: var(--lp-c); }
        .lp-pet.bob { animation: lpBob 3.4s ease-in-out infinite; } .lp-pet.mood-thinking { animation: lpThink 1.1s ease-in-out infinite; } .lp-pet.mood-happy { animation: lpJump .55s ease; } .lp-pet.mood-sleep { animation: lpSleep 4s ease-in-out infinite; }
        .lp-pet .lp-body { position: absolute; inset: 0; border-radius: 50%; }
        .lp-pet.shape-square .lp-body { border-radius: 30%; } .lp-pet.shape-drop .lp-body { border-radius: 50% 50% 50% 50% / 58% 58% 42% 42%; } .lp-pet.shape-ghost .lp-body { border-radius: 50% 50% 14% 14% / 62% 62% 38% 38%; } .lp-pet.shape-wide .lp-body { border-radius: 50%; transform: scaleX(1.18); }
        .lp-pet.orb .lp-body { box-shadow: 0 0 0 2px rgba(255,255,255,.22), 0 5px 14px rgba(0,0,0,.4), 0 0 calc(var(--lp-glow, 60) * .4px) var(--lp-glowc); }
        .lp-pet.led .lp-body { background-image: radial-gradient(circle, var(--lp-c) 0 38%, transparent 42%) !important; background-size: calc(100% / 13) calc(100% / 13); background-color: transparent !important; -webkit-mask-image: radial-gradient(circle, #000 55%, transparent 74%); mask-image: radial-gradient(circle, #000 55%, transparent 74%); border-radius: 50%; }
        .lp-pet .e { position: absolute; top: 36%; width: 15%; height: 26%; background: var(--lp-e); border-radius: 50%; box-shadow: 0 0 6px var(--lp-e); transform: translate(calc(var(--lp-lx) * 2.4px * var(--lp-s)), calc(var(--lp-ly) * 2.1px * var(--lp-s))); transition: transform .14s ease-out, height .1s, border-radius .2s, top .1s; }
        .lp-pet .e.l { left: 30%; } .lp-pet .e.r { right: 30%; }
        .lp-pet.eyes-round .e { width: 20%; height: 20%; top: 40%; } .lp-pet.eyes-dot .e { width: 9%; height: 9%; top: 46%; } .lp-pet.eyes-wide .e { width: 19%; height: 32%; top: 32%; border-radius: 45%; }
        .lp-pet.blink .e { height: 4% !important; top: 48% !important; border-radius: 3px !important; }
        .lp-pet .m { position: absolute; left: 50%; top: 66%; width: 22%; height: 11%; transform: translateX(-50%); border: 0 solid var(--lp-e); display: none; }
        .lp-pet .bl { position: absolute; top: 58%; width: 16%; height: 10%; border-radius: 50%; background: rgba(255,110,150,.55); display: none; } .lp-pet .bl.l { left: 12%; } .lp-pet .bl.r { right: 12%; } .lp-pet.blush .bl { display: block; }
        .lp-pet .acc { position: absolute; inset: 0; overflow: visible; pointer-events: none; } .lp-pet .acc svg { width: 100%; height: 100%; overflow: visible; display: block; }
        .lp-pet.acc-sunglasses .e { opacity: 0; }
        .lp-pet.ex-happy .e, .lp-pet.mood-happy .e { height: 9%; top: 44%; background: transparent !important; box-shadow: none; border-top: 4px solid var(--lp-e); border-radius: 50% 50% 0 0; width: 19%; }
        .lp-pet.ex-happy .m, .lp-pet.mood-happy .m { display: block; border-bottom-width: 3px; border-radius: 0 0 50% 50%; height: 12%; }
        .lp-pet.ex-wink .e.r { height: 8%; top: 46%; background: transparent !important; box-shadow: none; border-top: 3px solid var(--lp-e); border-radius: 50% 50% 0 0; }
        .lp-pet.ex-wink .m { display: block; border-bottom-width: 3px; border-radius: 0 0 50% 50%; height: 12%; }
        .lp-pet.ex-love .e { background: #ff4d79 !important; box-shadow: 0 0 6px #ff4d79; width: 19%; height: 18%; top: 38%; clip-path: polygon(50% 100%, 0 38%, 0 14%, 18% 0, 50% 18%, 82% 0, 100% 14%, 100% 38%); border-radius: 0; }
        .lp-pet.ex-love .m { display: block; border-bottom-width: 3px; border-radius: 0 0 50% 50%; height: 12%; }
        .lp-pet.ex-surprised .e { width: 19%; height: 30%; top: 32%; } .lp-pet.ex-surprised .m { display: block; width: 11%; height: 13%; border-width: 3px; border-radius: 50%; top: 66%; }
        .lp-pet.ex-sleepy .e, .lp-pet.mood-sleep .e { height: 8%; top: 46%; border-radius: 0 0 50% 50%; } .lp-pet.mood-sleep .e { background: transparent !important; box-shadow: none; border-bottom: 3px solid var(--lp-e); }
        .lp-pet.ex-angry .e { height: 20%; border-radius: 30%; } .lp-pet.ex-angry .e.l { transform: translate(calc(var(--lp-lx) * 2.4px), calc(var(--lp-ly) * 2.1px)) rotate(18deg); } .lp-pet.ex-angry .e.r { transform: translate(calc(var(--lp-lx) * 2.4px), calc(var(--lp-ly) * 2.1px)) rotate(-18deg); }
        .lp-pet.ex-angry .m { display: block; border-top-width: 3px; width: 18%; height: 0; top: 70%; }
        .lp-pet.ex-sad .e { height: 24%; } .lp-pet.ex-sad .e.l { transform: translate(calc(var(--lp-lx) * 2.4px), calc(var(--lp-ly) * 2.1px)) rotate(-12deg); } .lp-pet.ex-sad .e.r { transform: translate(calc(var(--lp-lx) * 2.4px), calc(var(--lp-ly) * 2.1px)) rotate(12deg); }
        .lp-pet.ex-sad .m { display: block; border-top-width: 3px; border-radius: 50% 50% 0 0; height: 10%; top: 68%; }
        .lp-pet.ex-smug .e { height: 14%; top: 42%; border-radius: 0 0 50% 50%; } .lp-pet.ex-smug .m { display: block; border-bottom-width: 3px; border-radius: 0 0 0 50%; width: 18%; height: 8%; transform: translateX(-30%) rotate(-8deg); }
        .lp-pet.ex-dead .e { box-shadow: none; width: 15%; height: 15%; top: 40%; border-radius: 0; background: linear-gradient(45deg, transparent 43%, var(--lp-e) 43% 57%, transparent 57%), linear-gradient(-45deg, transparent 43%, var(--lp-e) 43% 57%, transparent 57%) !important; }
        .lp-pet.ex-dead .m { display: block; border-top-width: 3px; width: 16%; height: 0; top: 70%; }
        @keyframes lpBob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-4px); } } @keyframes lpThink { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.07); } } @keyframes lpSleep { 0%, 100% { transform: scale(1); } 50% { transform: scale(.96); } }
        @keyframes lpJump { 0% { transform: translateY(0) scale(1); } 30% { transform: translateY(-18px) scale(.95, 1.06); } 60% { transform: translateY(0) scale(1.08, .92); } 100% { transform: translateY(0) scale(1); } }
        .lp-pet .m { display: none !important; }   /* sem boca */
        @media (prefers-reduced-motion: reduce) { .lp-pet { animation: none !important; } }
        #lume-pet { position: fixed; z-index: 4400; touch-action: none; user-select: none; -webkit-user-select: none; cursor: grab; } #lume-pet.drag { cursor: grabbing; } #lume-pet.hide { display: none; }
        #lume-pet .lp-bub { position: absolute; bottom: calc(100% + 8px); right: 0; max-width: 220px; white-space: nowrap; padding: 6px 12px; border-radius: 14px; background: var(--bg-input, #2a2a2e); color: var(--text-main, #eee); border: 1px solid var(--border-color, #444); font-size: 12.5px; box-shadow: 0 6px 18px rgba(0,0,0,.4); opacity: 0; transform: translateY(6px) scale(.96); transition: opacity .2s, transform .2s; pointer-events: none; } #lume-pet .lp-bub.on { opacity: 1; transform: none; }
        body.pet-av .msg.ai { padding-left: calc(var(--lp-avs, 30px) + 22px); } body.pet-av .msg.ai > .lp-av { position: absolute; left: 10px; top: 14px; width: var(--lp-avs, 30px); height: var(--lp-avs, 30px); cursor: pointer; }
        .lp-prev { flex: none; width: 84px; height: 84px; margin: 6px 14px 4px 0; }
    `;
    document.head.appendChild(css);

    // ---- um boneco: <div.lp-pet> com corpo, olhos, boca, rubor e acessorio
    function fill(el) {
        el.textContent = '';
        const body = document.createElement('div'); body.className = 'lp-body'; el.appendChild(body);
        ['l', 'r'].forEach(c => { const e = document.createElement('i'); e.className = 'e ' + c; el.appendChild(e); });
        el.appendChild(Object.assign(document.createElement('b'), { className: 'm' }));
        ['l', 'r'].forEach(c => el.appendChild(Object.assign(document.createElement('s'), { className: 'bl ' + c })));
        const a = document.createElement('div'); a.className = 'acc'; el.appendChild(a);
    }
    function paint(el, m) {
        const mm = m || el.dataset.mood || 'idle', blink = el.classList.contains('blink');
        el.className = 'lp-pet ' + cfg.style + ' shape-' + cfg.shape + ' ex-' + cfg.expr + ' eyes-' + cfg.eyes + ' acc-' + cfg.acc + (cfg.blush ? ' blush' : '') + (cfg.bob ? ' bob' : '') + (mm !== 'idle' && cfg.react ? ' mood-' + mm : '') + (blink ? ' blink' : '');
        el.style.setProperty('--lp-c', cfg.color); el.style.setProperty('--lp-e', cfg.eyeColor); el.style.setProperty('--lp-glow', cfg.glow); el.style.setProperty('--lp-glowc', rgba(cfg.color, Math.min(1, cfg.glow / 100)));
        const body = el.querySelector('.lp-body');
        if (body) body.style.background = cfg.style === 'led' ? '' : 'radial-gradient(circle at 34% 26%, ' + mix(cfg.color, [255, 255, 255], .55) + ' 0%, ' + cfg.color + ' 48%, ' + mix(cfg.color, [0, 0, 0], .42) + ' 100%)';
        const acc = el.querySelector('.acc'); if (acc) acc.innerHTML = ACC[cfg.acc] ? '<svg viewBox="0 0 100 100">' + ACC[cfg.acc] + '</svg>' : '';
        el.style.setProperty('--lp-s', Math.max(.5, Math.min(2.4, (el.clientWidth || 30) / 30)));
    }
    const point = (el, x, y) => { el.style.setProperty('--lp-lx', x); el.style.setProperty('--lp-ly', y); };
    function make(host) { const el = document.createElement('div'); el.dataset.mood = 'idle'; fill(el); host.appendChild(el); paint(el); pets.add(el); return el; }
    function repaintAll() { pets.forEach(el => { if (!el.isConnected) { pets.delete(el); return; } paint(el); }); document.body.style.setProperty('--lp-avs', cfg.avSize + 'px'); }
    function setMoodAll(m) { mood = m; pets.forEach(el => { if (el.isConnected && !el.closest('#lp-modal')) { el.dataset.mood = m; paint(el); } }); }

    // ---- flutuante
    const phrases = () => [T('Oi!'), T('Bora conversar?'), T('Estou de olho 👀'), T('Pode perguntar!'), T('Hmm, e se a gente jogasse xadrez?'), T('Eu sou só um mascote, mas torço por você.')];
    function say(text, ms) { if (!cfg.bubble || !bub || !cfg.on) return; bub.textContent = text; bub.classList.add('on'); clearTimeout(bubTimer); bubTimer = setTimeout(() => bub && bub.classList.remove('on'), ms || 2200); }
    function flash(m, ms) { clearTimeout(moodTimer); setMoodAll(m); if (ms) moodTimer = setTimeout(() => setMoodAll('idle'), ms); }
    function build() {
        if (root) { pets.delete(pet); root.remove(); }
        root = document.createElement('div'); root.id = 'lume-pet'; root.title = cfg.name;
        bub = document.createElement('div'); bub.className = 'lp-bub'; root.appendChild(bub);
        const holder = document.createElement('div'); holder.style.cssText = 'width:100%;height:100%'; root.appendChild(holder); pet = make(holder);
        document.body.appendChild(root); place(); wire();
    }
    function place() {
        const s = cfg.size; root.style.width = root.style.height = s + 'px'; root.classList.toggle('hide', !cfg.on);
        if (cfg.x == null) { root.style.right = '18px'; root.style.bottom = '96px'; root.style.left = root.style.top = 'auto'; bub.style.right = '0'; bub.style.left = 'auto'; }
        else { const x = Math.min(Math.max(0, cfg.x), innerWidth - s), y = Math.min(Math.max(0, cfg.y), innerHeight - s); root.style.left = x + 'px'; root.style.top = y + 'px'; root.style.right = root.style.bottom = 'auto'; bub.style.right = 'auto'; bub.style.left = '0'; }
        paint(pet);
    }
    function wire() {
        let drag = null;
        root.addEventListener('pointerdown', e => { const r = root.getBoundingClientRect(); drag = { x: e.clientX, y: e.clientY, ox: r.left, oy: r.top, moved: false }; try { root.setPointerCapture(e.pointerId); } catch (x) { /* ok */ } });
        root.addEventListener('pointermove', e => { if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; if (!drag.moved && Math.hypot(dx, dy) < 5) return; drag.moved = true; root.classList.add('drag'); cfg.x = drag.ox + dx; cfg.y = drag.oy + dy; place(); });
        root.addEventListener('pointerup', () => { if (!drag) return; const d = drag; drag = null; root.classList.remove('drag'); if (d.moved) { save(); return; } const p = phrases(); say(p[Math.floor(Math.random() * p.length)]); flash('happy', 600); });
    }

    // ---- avatar ao lado de cada resposta da IA
    function addAv(msg) { if (msg.querySelector(':scope > .lp-av')) return; const a = document.createElement('div'); a.className = 'lp-av'; a.title = cfg.name + ' · ' + T('clique para personalizar'); a.onclick = () => openSettings(); msg.insertBefore(a, msg.firstChild); make(a); }
    function scanAv() { const chat = document.getElementById('chat'); if (!chat) return; document.body.classList.toggle('pet-av', !!cfg.avatar); document.body.style.setProperty('--lp-avs', cfg.avSize + 'px'); if (!cfg.avatar) { chat.querySelectorAll('.msg.ai > .lp-av').forEach(a => a.remove()); return; } chat.querySelectorAll('.msg.ai').forEach(addAv); }
    function initAv() {
        const chat = document.getElementById('chat'), inp = document.getElementById('prompt'); if (!chat) return;
        new MutationObserver(scanAv).observe(chat, { childList: true }); scanAv();
        if (inp) { const upd = () => { typing = document.activeElement === inp && inp.value.length > 0; if (typing && cfg.follow) pets.forEach(el => point(el, 0, 1.1)); }; inp.addEventListener('input', upd); inp.addEventListener('focus', upd); inp.addEventListener('blur', () => { typing = false; }); }
        addEventListener('pointermove', e => {   // olha para o cursor; digitando, olha para baixo (para a mensagem)
            lastMove = Date.now(); if (mood === 'sleep') flash('idle'); if (!cfg.follow || typing) return;
            const list = [...pets].filter(el => el.isConnected && !el.closest('#lp-modal')), ref = list.filter(el => el.closest('.lp-av')).pop() || pet; if (!ref) return;
            const r = ref.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2), d = Math.hypot(dx, dy) || 1, k = Math.min(1, d / 200), x = +(dx / d * k).toFixed(2), y = +(dy / d * k).toFixed(2);
            if (x !== look.x || y !== look.y) { look = { x, y }; list.forEach(el => point(el, x, y)); }
        }, { passive: true });
        setInterval(() => {   // piscar, "pensando" no ultimo avatar enquanto a IA responde, dormir quando parado
            const avs = [...pets].filter(el => el.isConnected && el.closest('.lp-av')), last = avs[avs.length - 1]; let b = false; try { b = typeof busy !== 'undefined' && !!busy; } catch (e) { b = false; }
            avs.forEach(a => { const th = a === last && b && cfg.react ? 'thinking' : (a.dataset.mood === 'thinking' ? 'idle' : a.dataset.mood); if (a.dataset.mood !== th) { a.dataset.mood = th; paint(a); } });
            if (b && !wasBusy) { wasBusy = true; if (root && cfg.on) { pet.dataset.mood = 'thinking'; paint(pet); say(T('Pensando…'), 1800); } }
            else if (!b && wasBusy) { wasBusy = false; if (root && cfg.on) { flash('happy', 1600); say(T('Pronto!'), 1800); } }
            else if (!b && Date.now() - lastMove > 90000 && cfg.react) pets.forEach(el => { if (el.isConnected && el.dataset.mood === 'idle') { el.dataset.mood = 'sleep'; paint(el); } });
            if (cfg.blinking && pets.size && Math.random() < .35) { const list = [...pets].filter(el => el.isConnected); const a = list[Math.floor(Math.random() * list.length)]; if (a) { a.classList.add('blink'); setTimeout(() => a.classList.remove('blink'), 140); } }
        }, 700);
    }

    // ---- janela de personalizacao (com previa ao vivo)
    function openSettings() {
        if (document.getElementById('lp-modal')) return;
        const U = window.LumeUI, w = U.modal({ title: 'Mascote', id: 'lp-modal', width: 820, cols: true });
        const apply = rebuild => { save(); if (rebuild) build(); repaintAll(); if (root) place(); scanAv(); };
        const tog = (sec, label, key, fn) => U.toggle(sec, label, cfg[key], v => { cfg[key] = v; (fn || apply)(); });
        const rng = (key, min, max) => U.range(min, max, cfg[key], v => { cfg[key] = v; apply(); });
        const sel = (key, opts) => U.select(opts, cfg[key], v => { cfg[key] = v; apply(); });
        const prev = document.createElement('div'); prev.className = 'lp-prev'; w.aside(prev); const pv = make(prev); point(pv, 0, 0);
        prev.addEventListener('pointermove', e => { const r = pv.getBoundingClientRect(), dx = e.clientX - (r.left + r.width / 2), dy = e.clientY - (r.top + r.height / 2), d = Math.hypot(dx, dy) || 1; point(pv, +(dx / d).toFixed(2), +(dy / d).toFixed(2)); });
        let s = U.section(w.body, 'Onde aparece', { open: true });
        tog(s, 'Ao lado das respostas da IA', 'avatar'); tog(s, 'Flutuando na tela', 'on'); tog(s, 'Balões de fala', 'bubble', save);
        U.row(s, 'Tamanho ao lado das respostas', rng('avSize', 22, 56)); U.row(s, 'Tamanho flutuando', rng('size', 40, 140));
        s = U.section(w.body, 'Rosto', { open: true });
        U.row(s, 'Nome', U.text(cfg.name, v => { cfg.name = v || 'Lume'; if (root) root.title = cfg.name; save(); say(T('Oi, eu sou {n}!').replace('{n}', cfg.name)); }, 20));
        U.row(s, 'Expressão', sel('expr', EXPR)); U.row(s, 'Olhos', sel('eyes', [['oval', 'Ovais'], ['round', 'Redondos'], ['wide', 'Grandes'], ['dot', 'Pontinhos']]));
        U.row(s, 'Cor dos olhos', U.color(cfg.eyeColor, v => { cfg.eyeColor = v; apply(); }, ['#ffffff', '#111111', '#ffd166', '#7dd3fc', '#86efac', '#f9a8d4']));
        U.row(s, 'Acessório', sel('acc', ACC_NAMES)); tog(s, 'Bochechas rosadas', 'blush');
        s = U.section(w.body, 'Corpo', { open: true });
        U.row(s, 'Cor', U.color(cfg.color, v => { cfg.color = v; apply(); }, ['#2f8bff', '#ee5a8a', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#14b8a6', '#9ca3af', '#f5f5f5', '#222222']));
        U.row(s, 'Estilo', sel('style', [['orb', 'Bolha brilhante'], ['led', 'LED de pontinhos']]));
        U.row(s, 'Formato', sel('shape', [['circle', 'Redondo'], ['wide', 'Achatado'], ['square', 'Quadrado arredondado'], ['drop', 'Gota'], ['ghost', 'Fantasminha']]));
        U.row(s, 'Brilho (aura)', rng('glow', 0, 100));
        s = U.section(w.body, 'Comportamento', { open: true });
        tog(s, 'Olhos seguem o cursor', 'follow', save); tog(s, 'Piscar', 'blinking', save); tog(s, 'Balançar parado', 'bob'); tog(s, 'Reagir (pensar, comemorar, dormir)', 'react');
        U.button(w.foot, 'Voltar ao canto', () => { cfg.x = cfg.y = null; apply(); });
        U.button(w.foot, 'Restaurar', () => { cfg = Object.assign({}, DEF); save(); build(); repaintAll(); scanAv(); w.close(); });
    }
    window.lumePet = { openSettings, get config() { return cfg; }, say, setMood: flash };
    addEventListener('resize', () => { if (root) place(); });
    const start = () => { build(); initAv(); repaintAll(); if (cfg.on) setTimeout(() => say(T('Oi, eu sou {n}!').replace('{n}', cfg.name), 2600), 1800); };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
