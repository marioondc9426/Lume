/* Painel de provedores (Configuracoes > Chaves de API > "Painel de provedores"): numa tela so, quem esta com chave, quantos modelos aparecem,
   quantos estao fora do ar, o saldo (quando o provedor informa) e um botao para testar. Usa o kit LumeUI. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const U = () => window.LumeUI;
    const css = document.createElement('style');
    css.textContent = `
        .pv-list { display: flex; flex-direction: column; gap: 8px; }
        .pv-row { display: grid; grid-template-columns: 34px minmax(0, 1.2fr) minmax(0, 1.6fr) auto; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 14px; background: rgba(128,128,128,.10); }
        .pv-logo { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; } .pv-logo .mo-provs { margin: 0; } .pv-logo .pv { height: 22px; max-width: 28px; }
        .pv-logo .pv-mono { background: var(--text-main); -webkit-mask: var(--m) center / contain no-repeat; mask: var(--m) center / contain no-repeat; }
        .pv-name { font-weight: 600; font-size: .95em; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .pv-sub { font-size: .76em; color: var(--text-muted); font-weight: 400; }
        .pv-chips { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-width: 0; }
        .pv-chip { padding: 2px 9px; border-radius: 999px; font-size: .74em; background: rgba(128,128,128,.2); white-space: nowrap; } .pv-chip.ok { background: rgba(63,185,80,.22); color: #3fb950; } .pv-chip.bad { background: rgba(229,72,77,.22); color: #e5484d; } .pv-chip.warn { background: rgba(240,180,41,.22); color: #d9a21b; }
        .pv-act { display: flex; gap: 6px; } .pv-act .btn { margin: 0; padding: 5px 11px; font-size: .8em; }
        .pv-sum { font-size: .85em; color: var(--text-muted); padding: 2px 4px 8px; }
        @media (max-width: 720px) { .pv-row { grid-template-columns: 34px minmax(0, 1fr); } .pv-chips, .pv-act { grid-column: 1 / -1; } }
    `;
    document.head.appendChild(css);

    const fmt = n => (n == null ? '' : Number(n).toLocaleString(typeof curLang === 'function' && curLang() === 'en' ? 'en-US' : 'pt-BR'));
    async function getJson(path, opts) { try { return await (await fetch(API + path, opts)).json(); } catch (e) { return {}; } }

    function logoInto(box, k, name) {   // o logo vem da mesma tabela do seletor de modelos (PROV_LOGOS)
        const L = (typeof PROV_LOGOS !== 'undefined' && PROV_LOGOS[k]) || null; let e;
        if (!L) { box.textContent = name[0]; return; }
        if (L.letter) { e = document.createElement('span'); e.textContent = L.letter; e.style.cssText = 'display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:50%;background:#2f8bff;color:#fff;font:700 13px Arial,sans-serif'; }
        else if (L.mono) { e = document.createElement('span'); e.className = 'pv pv-mono'; e.style.cssText = 'display:inline-block;height:22px;aspect-ratio:' + (L.ratio || 1); e.style.setProperty('--m', 'url("icons/' + L.img + '")'); }
        else { e = document.createElement('img'); e.src = 'icons/' + L.img; e.alt = name; e.style.cssText = 'height:24px;max-width:28px;object-fit:contain'; e.onerror = () => { box.textContent = name[0]; }; }
        box.appendChild(e);
    }

    window.openProviders = async function () {
        if (document.getElementById('pv-modal')) return;
        const u = U(), w = u.modal({ title: 'Provedores', id: 'pv-modal', width: 860 });
        const sum = u.el('div', 'pv-sum', T('Carregando...')), list = u.el('div', 'pv-list'); w.body.append(sum, list);
        const [cs, ov, vd, tk] = await Promise.all([getJson('/api/config_status'), getJson('/api/providers_overview'), getJson('/api/voidai_credits'), getJson('/api/tokenreply_usage')]);
        const xs = (cs && cs.x_saved) || {};
        // provedores: [chave do logo/modelos, nome, chave salva?, codigo do provedor extra (se for)]
        const rows = [['ollama', 'Ollama (no seu PC)', null, null], ['ollama-cloud', 'Ollama (nuvem)', null, null], ['groq', 'Groq', cs.groq_key_saved, null], ['openrouter', 'OpenRouter', cs.openrouter_key_saved, null], ['cloudflare', 'Cloudflare', cs.cloudflare_saved, null],
            ['pollinations', 'Pollinations', cs.pollinations_saved, null], ['tomdacat', 'tomdacat', cs.tomdacat_saved, null], ['vercel', 'Vercel', cs.vercel_saved, null], ['llm7', 'LLM7', cs.llm7_saved, null]]
            .concat(Object.entries(XP).map(([code, [k, name]]) => [k, name, xs[code], code]));
        const byProv = {}; MODELS.forEach(m => { let k; try { k = provKey(m); } catch (e) { return; } if (!k || !isAvail(m)) return; (byProv[k] = byProv[k] || []).push(m); });
        let keys = 0, total = 0, down = 0; list.textContent = '';
        rows.forEach(([k, name, saved, code]) => {
            const ms = byProv[k] || [], o = code ? (ov[code] || {}) : {}, hasKey = saved == null ? null : !!saved;
            if (hasKey === false && !ms.length) { /* sem chave e sem modelos: mostra mesmo assim, apagadinho */ }
            const row = u.el('div', 'pv-row'), logo = u.el('div', 'pv-logo');
            logoInto(logo, k, name);
            const nm = u.el('div', 'pv-name', name); nm.appendChild(u.el('div', 'pv-sub', code ? T('provedor extra') : (k.startsWith('ollama') ? T('local / nuvem do Ollama') : T('provedor'))));
            const chips = u.el('div', 'pv-chips');
            if (hasKey !== null) chips.appendChild(u.el('span', 'pv-chip ' + (hasKey ? 'ok' : ''), hasKey ? T('chave salva') : T('sem chave'))); if (hasKey) keys++;
            chips.appendChild(u.el('span', 'pv-chip', ms.length + ' ' + T('modelos'))); total += ms.length;
            if (o.failing && o.failing.length) { const c = u.el('span', 'pv-chip bad', o.failing.length + ' ' + T('fora do ar')); c.title = o.failing.join('\n'); chips.appendChild(c); down += o.failing.length; }
            if (code && o.show_all) chips.appendChild(u.el('span', 'pv-chip', T('mostra todos')));
            if (code && o.limit) { const c = u.el('span', 'pv-chip ' + (o.used_today >= o.limit ? 'bad' : o.used_today >= o.limit * 0.8 ? 'warn' : 'ok'), '📊 ' + (o.used_today || 0) + ' / ' + o.limit + ' ' + T('hoje')); c.title = T('Pedidos que o Lume mandou hoje. O painel do provedor pode mostrar mais se você usar a chave em outro lugar.'); chips.appendChild(c); }
            if (code === 'vd' && vd && vd.credits != null) chips.appendChild(u.el('span', 'pv-chip warn', '💳 ' + fmt(vd.credits) + (vd.limit ? ' / ' + fmt(vd.limit) : '')));
            if (code === 'tk' && tk && tk.available != null) chips.appendChild(u.el('span', 'pv-chip warn', '💵 US$ ' + Number(tk.available).toFixed(3) + ' / ' + Number(tk.granted).toFixed(2)));
            const res = u.el('span', 'pv-chip'); res.style.display = 'none'; chips.appendChild(res);
            const act = u.el('div', 'pv-act');
            if (code && hasKey) u.button(act, 'Testar', async () => {
                res.style.display = ''; res.className = 'pv-chip'; res.textContent = '...';
                const r = await getJson('/api/provider_ping', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prov: code }) });
                if (r.ok === true) { res.className = 'pv-chip ok'; res.textContent = '✓ ' + (r.ms || 0) + ' ms'; } else if (r.ok === null) { res.className = 'pv-chip warn'; res.textContent = T('limite de pedidos'); } else { res.className = 'pv-chip bad'; res.textContent = '✕ ' + String(r.err || r.error || '').slice(0, 60); }
                res.title = r.model || '';
            });
            if (hasKey === false || (code && !hasKey)) u.button(act, 'Colocar chave', () => { w.close(); if (typeof openSettings === 'function') openSettings(); setTimeout(() => { if (typeof showSettingsSection === 'function') showSettingsSection('chaves'); }, 120); });
            row.append(logo, nm, chips, act); if (hasKey === false) row.style.opacity = '.62'; list.appendChild(row);
        });
        sum.textContent = T('{k} provedores com chave · {m} modelos na lista · {d} fora do ar').replace('{k}', keys).replace('{m}', total).replace('{d}', down);
    };
})();
