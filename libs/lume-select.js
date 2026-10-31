/* Barra ao selecionar texto numa mensagem do chat: Copiar so o trecho, Pesquisar no navegador, Traduzir, Citar, Explicar e Ler em voz alta.
   Aparece em cima do trecho selecionado (mouse ou toque) e some ao clicar fora, rolar ou apertar Esc. Usa openExternal(), showInfo(), lumeSpeak() e o campo #prompt do index.html. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const css = document.createElement('style');
    css.textContent = `
        #sel-bar { position: fixed; z-index: 9000; display: none; gap: 2px; padding: 4px; border-radius: 12px; background: var(--bg-input, #222); border: 1px solid var(--border-color, #444); box-shadow: 0 6px 22px rgba(0,0,0,.35); max-width: calc(100vw - 16px); flex-wrap: wrap; animation: selbar-in .12s ease-out; }
        #sel-bar.on { display: flex; }
        #sel-bar button { border: 0; background: transparent; color: var(--text-main, #eee); font: inherit; font-size: .82em; padding: 5px 9px; border-radius: 8px; cursor: pointer; white-space: nowrap; }
        #sel-bar button:hover { background: rgba(128,128,128,.25); }
        @keyframes selbar-in { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }
    `;
    document.head.appendChild(css);

    const bar = document.createElement('div'); bar.id = 'sel-bar'; document.body.appendChild(bar);
    bar.addEventListener('mousedown', e => e.preventDefault());   // clicar na barra nao tira a selecao
    let text = '', mouseDown = false, timer = 0;

    const info = (m, ms) => { if (typeof showInfo === 'function') showInfo(m, ms || 1800); };
    const hide = () => { bar.classList.remove('on'); text = ''; };
    async function copy(t) {
        try { await navigator.clipboard.writeText(t); } catch (e) {
            const ta = document.createElement('textarea'); ta.value = t; ta.style.cssText = 'position:fixed;opacity:0'; document.body.appendChild(ta); ta.select();
            try { document.execCommand('copy'); } catch (e2) { /* sem area de transferencia */ } ta.remove();
        }
    }
    const toPrompt = (t, focusEnd = true) => {
        const p = document.getElementById('prompt'); if (!p) return;
        p.value = (p.value ? p.value.replace(/\s*$/, '') + '\n\n' : '') + t; p.dispatchEvent(new Event('input', { bubbles: true }));
        p.focus(); if (focusEnd) p.setSelectionRange(p.value.length, p.value.length);
    };
    const q = t => encodeURIComponent(t.replace(/\s+/g, ' ').trim().slice(0, 300));
    const open = u => { if (typeof openExternal === 'function') openExternal(u); else window.open(u, '_blank', 'noopener'); };
    const lang = () => (typeof curLang === 'function' && curLang() === 'en' ? 'en' : 'pt');

    const ACTIONS = [
        ['Copiar', t => copy(t).then(() => info(T('Copiado!')))],
        ['Pesquisar', t => open('https://www.google.com/search?q=' + q(t))],
        ['Traduzir', t => open('https://translate.google.com/?sl=auto&tl=' + lang() + '&op=translate&text=' + q(t))],
        ['Citar', t => toPrompt(t.split('\n').map(l => '> ' + l).join('\n') + '\n\n')],
        ['Explicar', t => toPrompt((lang() === 'en' ? 'Explain this: "' : 'Explique isto: "') + t.replace(/\s+/g, ' ').trim() + '"')],
    ];
    ACTIONS.forEach(([name, fn]) => {
        const b = document.createElement('button'); b.type = 'button'; b.textContent = T(name); b.dataset.act = name;
        b.onclick = () => { const t = text; hide(); if (t) { fn(t); try { getSelection().removeAllRanges(); } catch (e) { /* ok */ } } }; bar.appendChild(b);
    });
    const speakBtn = document.createElement('button'); speakBtn.type = 'button'; speakBtn.textContent = T('Ler em voz alta'); speakBtn.dataset.act = 'Ler em voz alta'; speakBtn.style.display = 'none';
    speakBtn.onclick = () => { const t = text; hide(); if (t && window.lumeSpeak) window.lumeSpeak(t, null); }; bar.appendChild(speakBtn);

    function selectedText() {
        const s = getSelection(); if (!s || s.isCollapsed || !s.rangeCount) return null;
        const r = s.getRangeAt(0), node = r.commonAncestorContainer, el = node.nodeType === 1 ? node : node.parentElement;
        if (!el || !el.closest || !el.closest('.msg')) return null;
        if (el.closest('textarea, input, #sel-bar')) return null;
        const t = (String(s) || r.toString()).replace(/ /g, ' ').trim(); return t ? { t, r } : null;   // r.toString() quando a janela esta sem foco e o navegador devolve vazio
    }
    function show() {
        const sel = selectedText(); if (!sel) { hide(); return; }
        text = sel.t; speakBtn.style.display = window.lumeSpeak ? '' : 'none';
        const rc = sel.r.getBoundingClientRect(); bar.classList.add('on');
        const w = bar.offsetWidth, h = bar.offsetHeight;
        let x = rc.left + rc.width / 2 - w / 2, y = rc.top - h - 8;
        if (y < 8) y = rc.bottom + 8;   // sem espaco em cima: vai para baixo do trecho
        bar.style.left = Math.max(8, Math.min(innerWidth - w - 8, x)) + 'px'; bar.style.top = Math.max(8, Math.min(innerHeight - h - 8, y)) + 'px';
    }
    const later = () => { clearTimeout(timer); timer = setTimeout(() => { if (!mouseDown) show(); }, 220); };
    document.addEventListener('mousedown', e => { mouseDown = true; if (!e.target.closest('#sel-bar')) hide(); });
    document.addEventListener('mouseup', () => { mouseDown = false; later(); });
    document.addEventListener('selectionchange', later);   // toque (celular): a selecao muda sem mouse
    document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
    document.addEventListener('scroll', hide, true);
    window.addEventListener('resize', hide);
    window.lumeSelectActions = ACTIONS.map(a => a[0]);
})();
