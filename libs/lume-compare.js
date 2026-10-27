/* Comparar modelos: a mesma pergunta para 2 ou 3 modelos ao mesmo tempo, lado a lado, com o tempo de cada um.
   Botao "Comparar modelos" na lateral. Usa o kit LumeUI e o lumeAsk (nao mexe nas suas conversas). */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const css = document.createElement('style');
    css.textContent = `
        .cp-pick { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; } .cp-pick select { width: 100%; }
        .cp-cols { display: grid; grid-template-columns: repeat(var(--n, 2), minmax(0, 1fr)); gap: 10px; flex: 1 1 auto; min-height: 120px; }
        .cp-col { display: flex; flex-direction: column; min-width: 0; border-radius: 14px; background: rgba(128,128,128,.10); overflow: hidden; }
        .cp-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 9px 12px; font-size: .85em; font-weight: 600; border-bottom: 1px solid var(--border-color); } .cp-head span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .cp-time { font-weight: 400; color: var(--text-muted); font-size: .9em; flex: none; } .cp-time.ok { color: #3fb950; } .cp-time.bad { color: #e5484d; }
        .cp-text { padding: 10px 12px; font-size: .9em; line-height: 1.5; white-space: pre-wrap; overflow-y: auto; max-height: 46vh; flex: 1; word-break: break-word; }
        .cp-foot { padding: 6px 10px 10px; display: flex; gap: 6px; } .cp-foot .btn { margin: 0; padding: 4px 11px; font-size: .8em; }
        .cp-q { width: 100%; box-sizing: border-box; min-height: 70px; resize: vertical; }
        @media (max-width: 760px) { .cp-pick, .cp-cols { grid-template-columns: minmax(0, 1fr); } }
    `;
    document.head.appendChild(css);

    window.openCompare = function () {
        if (document.getElementById('cp-modal')) return;
        let ctl = null;   // o pedido em andamento: fecha a janela, cancela
        const u = window.LumeUI, w = u.modal({ title: 'Comparar modelos', id: 'cp-modal', width: 1100, onClose: () => { if (ctl) ctl.abort(); } });
        const models = (window.lumeModels ? lumeModels() : []).filter(m => !m.phone);
        if (models.length < 2) { w.body.appendChild(u.el('div', 'lu-hint', T('Preciso de pelo menos 2 modelos disponíveis. Configure uma chave ou ligue o Ollama.'))); return; }
        const label = m => { let p = ''; try { p = providerName(m); } catch (e) { /* sem provedor */ } return (m.label || m.id) + (p ? ' · ' + p : ''); };
        const cur = (typeof selectedModel !== 'undefined' ? models.findIndex(m => m.id === selectedModel) : -1);
        const sels = [0, 1, 2].map(i => { const s = u.select([['', i === 2 ? '(nenhum)' : '(escolha)']].concat(models.map(m => [m.id, label(m)])), '', () => {}); s.value = i === 0 && cur >= 0 ? models[cur].id : i === 1 ? (models[cur === 0 ? 1 : 0].id) : ''; return s; });
        const pick = u.el('div', 'cp-pick'); sels.forEach(s => pick.appendChild(s)); w.body.appendChild(pick);
        const q = u.el('textarea', 'cp-q'); q.placeholder = T('Escreva a pergunta que todos vão responder…'); w.body.appendChild(q);
        const cols = u.el('div', 'cp-cols'); w.body.appendChild(cols);
        const run = async () => {
            const text = q.value.trim(); if (!text) { q.focus(); return; }
            const chosen = sels.map(s => s.value).filter(Boolean).filter((v, i, a) => a.indexOf(v) === i).map(id => lumeModelById(id)).filter(Boolean);
            if (chosen.length < 2) { if (typeof showInfo === 'function') showInfo(T('Escolha pelo menos 2 modelos diferentes.'), 4000); return; }
            if (ctl) ctl.abort(); ctl = new AbortController(); cols.textContent = ''; cols.style.setProperty('--n', chosen.length);
            chosen.forEach(m => {
                const col = u.el('div', 'cp-col'), head = u.el('div', 'cp-head'), nm = u.el('span', '', label(m)), tm = u.el('span', 'cp-time', '…'); head.append(nm, tm);
                const body = u.el('div', 'cp-text', ''), foot = u.el('div', 'cp-foot'); u.button(foot, 'Copiar', () => { try { navigator.clipboard.writeText(body.textContent); } catch (e) { /* sem area de transferencia */ } }); col.append(head, body, foot); cols.appendChild(col);
                const t0 = performance.now(), tick = setInterval(() => { tm.textContent = ((performance.now() - t0) / 1000).toFixed(1) + ' s'; }, 200);
                lumeAsk({ model: m, user: text, system: '', signal: ctl.signal, onText: t => { body.textContent = t; } })
                    .then(t => { clearInterval(tick); const s = (performance.now() - t0) / 1000, words = (t.match(/\S+/g) || []).length; body.textContent = t; tm.className = 'cp-time ok'; tm.textContent = s.toFixed(1) + ' s · ' + words + ' ' + T('palavras'); })
                    .catch(e => { clearInterval(tick); tm.className = 'cp-time bad'; tm.textContent = T('erro'); if (!body.textContent) body.textContent = String(e.message || e); });
            });
        };
        u.button(w.foot, 'Comparar', run, 'primary');
        q.addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } });
        setTimeout(() => q.focus(), 50);
    };
})();
