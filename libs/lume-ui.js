/* Lume UI kit: o jeito unico de montar janelas e opcoes fora da tela principal (xadrez, mascote, novos paineis).
   Para adicionar algo, nao escreva CSS novo: use estes blocos e o visual sai igual ao resto.

     const w = LumeUI.modal({ title: 'Meu painel' });            // janela com X no canto (fecha no X, no Esc ou clicando fora)
     const s = LumeUI.section(w.body, 'Aparência', { open: true }); // grupo que abre e fecha
     LumeUI.toggle(s, 'Ligar isso', true, v => ...);               // interruptor
     LumeUI.row(s, 'Cor', LumeUI.color('#2f8bff', v => ...));      // rotulo + controle
     LumeUI.row(s, 'Estilo', LumeUI.select([['a', 'A'], ['b', 'B']], 'a', v => ...));
     LumeUI.row(s, 'Tamanho', LumeUI.range(20, 80, 40, v => ...));
     LumeUI.seg(w.body, [['w', 'Brancas'], ['b', 'Pretas']], 'w', v => ...);
     LumeUI.button(w.foot, 'Salvar', fn, 'primary');

   Textos passam por tr() (traducao) quando existir. Cores vem das variaveis do tema (--bg-main, --accent...). */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
    const css = el('style');
    css.textContent = `
        .lu-ov { position: fixed; inset: 0; z-index: 6600; display: flex; align-items: center; justify-content: center; padding: 12px; background: rgba(0,0,0,.55); animation: luFade .2s ease both; }
        .lu-card { position: relative; width: min(var(--lu-w, 440px), 100%); max-height: 100%; display: flex; flex-direction: column; background: var(--bg-main); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 20px; box-shadow: 0 20px 60px rgba(0,0,0,.55); animation: luPop .28s cubic-bezier(.2,.85,.25,1.05) both; }
        .lu-head { display: flex; align-items: center; gap: 10px; padding: 16px 56px 8px 18px; } .lu-head h3 { margin: 0; font-size: 1.05em; }
        .lu-x { position: absolute; top: 12px; right: 12px; width: 32px; height: 32px; border-radius: 50%; border: 0; background: rgba(128,128,128,.18); color: var(--text-main); font-size: 15px; line-height: 1; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background .15s; } .lu-x:hover { background: rgba(220,50,50,.85); color: #fff; }
        .lu-body { flex: 1 1 auto; min-height: 0; overflow-y: auto; padding: 6px 18px 16px; display: flex; flex-direction: column; gap: 10px; }
        .lu-foot { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; padding: 0 18px 16px; } .lu-foot:empty { display: none; }
        .lu-body.lu-cols { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-items: start; } @media (max-width: 720px) { .lu-body.lu-cols { grid-template-columns: minmax(0, 1fr); } }
        .lu-head .lu-aside { margin-left: auto; flex: none; }
        .lu-sec { border-radius: 14px; background: rgba(128,128,128,.08); flex: none; } .lu-sec > summary { cursor: pointer; list-style: none; padding: 11px 14px; font-size: .74em; letter-spacing: .1em; text-transform: uppercase; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; } .lu-sec > summary::-webkit-details-marker { display: none; }
        .lu-sec > summary::after { content: '▾'; transition: transform .2s; } .lu-sec[open] > summary::after { transform: rotate(180deg); } .lu-sec > div { padding: 0 14px 12px; display: flex; flex-direction: column; gap: 10px; }
        .lu-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: .9em; flex: none; } .lu-row > span:first-child { flex: 1 1 auto; } .lu-row > :last-child { flex: 0 1 190px; min-width: 0; } .lu-row .lu-hint { flex-basis: 100%; }
        .lu-hint { font-size: .76em; color: var(--text-muted); line-height: 1.4; }
        .lu-card input[type=text], .lu-card select { width: 100%; box-sizing: border-box; }
        .lu-card input[type=color] { width: 44px; height: 30px; padding: 0; border: 1px solid var(--border-color); border-radius: 8px; background: none; cursor: pointer; }
        .lu-card input[type=range] { width: 100%; accent-color: var(--accent); }
        .lu-sw { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; } .lu-sw button { width: 22px; height: 22px; border-radius: 50%; border: 2px solid rgba(255,255,255,.25); cursor: pointer; padding: 0; }
        .lu-tog { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 12px; border-radius: 12px; background: rgba(128,128,128,.10); font-size: .88em; cursor: pointer; flex: none; }
        .lu-tog input { position: absolute; opacity: 0; pointer-events: none; } .lu-tog .sw { position: relative; flex: none; width: 38px; height: 22px; border-radius: 999px; background: rgba(128,128,128,.45); transition: background .2s; } .lu-tog .sw::after { content: ''; position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; transition: transform .2s cubic-bezier(.3,.9,.3,1.2); }
        .lu-tog input:checked + .sw { background: var(--accent); } .lu-tog input:checked + .sw::after { transform: translateX(16px); } .lu-tog input:focus-visible + .sw { outline: 2px solid var(--accent); outline-offset: 2px; }
        .lu-seg { display: flex; padding: 3px; border-radius: 12px; background: rgba(128,128,128,.14); gap: 2px; flex: none; } .lu-seg button { flex: 1; border: 0; background: transparent; color: var(--text-muted); padding: 8px 6px; border-radius: 9px; cursor: pointer; font-size: .86em; transition: background .2s, color .2s; } .lu-seg button.on { background: var(--bg-main); color: var(--text-main); box-shadow: 0 1px 4px rgba(0,0,0,.3); }
        .lu-btn { margin: 0; }
        @keyframes luFade { from { opacity: 0; } to { opacity: 1; } } @keyframes luPop { from { opacity: 0; transform: translateY(14px) scale(.97); } to { opacity: 1; transform: none; } }
        @media (prefers-reduced-motion: reduce) { .lu-ov, .lu-card { animation: none !important; } }
    `;
    document.head.appendChild(css);

    const UI = {
        el, T,
        modal(o) {
            o = o || {}; const ov = el('div', 'lu-ov'), card = el('div', 'lu-card'), head = el('div', 'lu-head'), body = el('div', 'lu-body'), foot = el('div', 'lu-foot');
            if (o.width) card.style.setProperty('--lu-w', o.width + 'px'); if (o.id) ov.id = o.id; if (o.cols) body.classList.add('lu-cols');
            if (o.title) head.appendChild(el('h3', '', T(o.title)));
            const x = el('button', 'lu-x', '✕'); x.type = 'button'; x.title = T('Fechar'); x.setAttribute('aria-label', T('Fechar'));
            let closed = false, esc;
            const close = () => { if (closed) return; closed = true; document.removeEventListener('keydown', esc); ov.remove(); if (o.onClose) o.onClose(); };
            esc = e => { if (e.key === 'Escape') close(); };
            x.onclick = close; ov.addEventListener('mousedown', e => { if (e.target === ov) close(); }); document.addEventListener('keydown', esc);
            card.append(head, x, body, foot); ov.appendChild(card); document.body.appendChild(ov);
            return { ov, card, head, body, foot, close, aside(node) { node.classList.add('lu-aside'); head.appendChild(node); return node; } };
        },
        section(parent, title, o) { const d = el('details', 'lu-sec'); if (o && o.open) d.open = true; d.appendChild(el('summary', '', T(title))); const b = el('div'); d.appendChild(b); parent.appendChild(d); return b; },
        row(parent, label, control, hint) { const r = el('div', 'lu-row'); r.append(el('span', '', T(label)), control); if (hint) r.appendChild(el('span', 'lu-hint', T(hint))); parent.appendChild(r); return r; },
        toggle(parent, label, checked, fn, id) { const l = el('label', 'lu-tog'), c = document.createElement('input'); c.type = 'checkbox'; if (id) c.id = id; c.checked = !!checked; c.onchange = () => fn && fn(c.checked); l.append(el('span', '', T(label)), c, el('span', 'sw')); if (parent) parent.appendChild(l); return c; },
        select(opts, val, fn) { const s = el('select'); opts.forEach(([v, l]) => s.add(new Option(T(l), v))); s.value = val; s.onchange = () => fn && fn(s.value); return s; },
        range(min, max, val, fn) { const r = el('input'); r.type = 'range'; r.min = min; r.max = max; r.value = val; r.oninput = () => fn && fn(+r.value); return r; },
        text(val, fn, max) { const t = el('input'); t.type = 'text'; if (max) t.maxLength = max; t.value = val || ''; t.onchange = () => fn && fn(t.value.trim()); return t; },
        color(val, fn, swatches) {
            const c = el('input'); c.type = 'color'; c.value = val; c.oninput = () => fn && fn(c.value); if (!swatches) return c;
            const w = el('div', 'lu-sw'); swatches.forEach(h => { const b = el('button'); b.type = 'button'; b.style.background = h; b.title = h; b.onclick = () => { c.value = h; fn && fn(h); }; w.appendChild(b); }); w.appendChild(c); return w;
        },
        seg(parent, opts, val, fn) { const s = el('div', 'lu-seg'); opts.forEach(([v, l]) => { const b = el('button', v === val ? 'on' : '', T(l)); b.type = 'button'; b.onclick = () => { s.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); fn && fn(v); }; s.appendChild(b); }); if (parent) parent.appendChild(s); return s; },
        button(parent, text, fn, kind) { const b = el('button', 'btn lu-btn btn-' + (kind || 'secondary'), T(text)); b.type = 'button'; b.onclick = fn; if (parent) parent.appendChild(b); return b; },
    };
    window.LumeUI = UI;
})();
