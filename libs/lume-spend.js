/* Gastos: quanto cada modelo custou, por semana, e quanto resta de saldo (Pollinations 🌸, TokenReply 💵, VoidAI 💳), com aviso quando o saldo esta acabando.
   Cada resposta paga vai para um caderno neste aparelho (localStorage 'lume_spend_v1'): so a data, o modelo e o valor (nunca o texto). Conta a partir de agora: o que foi gasto antes nao entra.
   Abre pelo botao "Gastos" das Estatisticas. O aviso de saldo baixo aparece como uma notificacao (no maximo uma por dia por servico).
     lumeSpend.add(modelo, pollen, creditos, usd)    chamado pelo index.html depois de cada resposta
     lumeSpend.open() / lumeSpend.checkBalances()    */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const KEY = 'lume_spend_v1', CFG = 'lume_spend_cfg', DAY = 86400000;
    const rd = (k, d) => { try { return JSON.parse(localStorage.getItem(k) || 'null') || d; } catch (e) { return d; } };
    const wr = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sem armazenamento */ } };
    const CUR = { pol: { icon: '🌸', name: 'Pollinations', unit: 'pollen', dig: 4, warn: 0.2 }, usd: { icon: '💵', name: 'TokenReply', unit: 'US$', dig: 3, warn: 0.1 }, cr: { icon: '💳', name: 'VoidAI', unit: 'créditos', dig: 0, warn: 500 } };
    let cfg = Object.assign({ on: true, warn: { pol: CUR.pol.warn, usd: CUR.usd.warn, cr: CUR.cr.warn } }, rd(CFG, {})); cfg.warn = Object.assign({ pol: CUR.pol.warn, usd: CUR.usd.warn, cr: CUR.cr.warn }, cfg.warn);
    const saveCfg = () => wr(CFG, cfg);
    const fmt = (c, v) => CUR[c].icon + ' ' + (CUR[c].dig ? v.toFixed(v < 0.01 && CUR[c].dig > 3 ? 5 : CUR[c].dig) : Math.round(v).toLocaleString('pt-BR')) + (c === 'cr' ? '' : '');

    // [ts, modelId, rotulo, pollen, creditos, usd]
    function add(m, pollen, credits, usd) {
        if (!m || !(pollen || credits || usd)) return; const a = rd(KEY, []); a.push([Date.now(), m.id, String(m.label || m.id).slice(0, 60), +(pollen || 0).toFixed(7), Math.round(credits || 0), +(usd || 0).toFixed(7)]);
        wr(KEY, a.length > 4000 ? a.slice(-4000) : a);
    }
    const weekStart = t => { const d = new Date(t); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return d.getTime(); };   // segunda-feira
    const sum = (rows, from, to) => { const o = { pol: 0, cr: 0, usd: 0, n: 0 }; rows.forEach(r => { if (r[0] >= from && r[0] < to) { o.pol += r[3]; o.cr += r[4]; o.usd += r[5]; o.n++; } }); return o; };
    const chips = (o, parent) => { let any = false; ['pol', 'usd', 'cr'].forEach(c => { if (o[c] > 0) { any = true; parent.appendChild(el('span', 'sp-chip', fmt(c, o[c]))); } }); if (!any) parent.appendChild(el('span', 'sp-none', '—')); };
    const el = (t, c, x) => window.LumeUI.el(t, c, x);

    // ---------------------------------------------------------------- saldos
    async function balances() {
        const get = async (url, fn) => { try { const r = await fetch(API + url), d = await r.json(); return r.ok && !d.error ? fn(d) : null; } catch (e) { return null; } };
        const [pol, usd, cr] = await Promise.all([get('/api/pollinations_usage', d => (d.balance != null ? { left: +d.balance } : null)), get('/api/tokenreply_usage', d => (d.available != null ? { left: +d.available, of: +d.granted } : null)), get('/api/voidai_credits', d => (d.credits != null ? { left: +d.credits, of: d.limit ? +d.limit : 0 } : null))]);
        return { pol, usd, cr };
    }
    async function checkBalances(quiet) {   // aviso de saldo baixo: uma vez por dia por servico
        if (!cfg.on || (typeof isGuest === 'function' && isGuest()) || (typeof auth !== 'undefined' && !(auth.local || auth.authed))) return; const b = await balances(), seen = rd('lume_spend_warned', {}), now = Date.now();
        ['pol', 'usd', 'cr'].forEach(c => { const x = b[c]; if (!x || x.left > cfg.warn[c]) return; if (seen[c] && now - seen[c] < DAY) return; seen[c] = now; if (typeof showInfo === 'function' && !quiet) showInfo('⚠ ' + T('Saldo baixo no ') + CUR[c].name + ': ' + fmt(c, x.left) + ' ' + (c === 'cr' ? T('créditos') : ''), 12000); });
        wr('lume_spend_warned', seen); return b;
    }

    // ---------------------------------------------------------------- janela
    function open() {
        if (document.getElementById('sp-modal')) return; const U = window.LumeUI, w = U.modal({ title: 'Gastos', id: 'sp-modal', width: 760 });
        const css = document.getElementById('sp-css') || Object.assign(document.head.appendChild(document.createElement('style')), { id: 'sp-css' });
        css.textContent = `.sp-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; } .sp-card { padding: 12px 14px; border-radius: 14px; background: rgba(128,128,128,.12); } .sp-card b { display: block; font-size: .8em; color: var(--text-muted); font-weight: 500; margin-bottom: 6px; } .sp-chip { display: inline-block; margin: 0 6px 4px 0; font-size: 1.05em; font-weight: 600; } .sp-none { color: var(--text-muted); }
            .sp-tbl { width: 100%; border-collapse: collapse; font-size: .86em; } .sp-tbl th, .sp-tbl td { padding: 7px 8px; text-align: left; border-bottom: 1px solid rgba(128,128,128,.14); } .sp-tbl th { color: var(--text-muted); font-weight: 500; } .sp-bars { display: flex; align-items: flex-end; gap: 6px; height: 90px; } .sp-bar { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; font-size: .68em; color: var(--text-muted); } .sp-bar i { display: block; width: 100%; background: var(--accent); border-radius: 5px 5px 0 0; min-height: 2px; opacity: .85; }`;
        const rows = rd(KEY, []), now = Date.now(), ws = weekStart(now);
        const cards = U.el('div', 'sp-cards'); w.body.appendChild(cards);
        [['Esta semana', ws, now + 1], ['Semana passada', ws - 7 * DAY, ws], ['Últimos 30 dias', now - 30 * DAY, now + 1]].forEach(([l, a, b]) => { const c = U.el('div', 'sp-card'); c.appendChild(U.el('b', '', T(l))); const o = sum(rows, a, b); chips(o, c); c.appendChild(U.el('div', 'lu-hint', o.n + ' ' + T('respostas pagas'))); cards.appendChild(c); });
        if (!rows.length) w.body.appendChild(U.el('div', 'lu-hint', T('Ainda não há gastos registrados. Cada resposta de um modelo pago entra aqui a partir de agora (modelos grátis e locais não gastam nada).')));
        // saldos
        let s = U.section(w.body, 'Saldo', { open: true }); const balBox = U.el('div'); s.appendChild(balBox); balBox.appendChild(U.el('div', 'lu-hint', T('Consultando os saldos…')));
        balances().then(b => {
            balBox.textContent = ''; let any = false;
            ['pol', 'usd', 'cr'].forEach(c => {
                const x = b[c]; if (!x) return; any = true; const m7 = sum(rows, now - 7 * DAY, now + 1)[c], perDay = m7 / 7, line = U.el('div', 'lu-row'); line.style.cssText = 'display:flex;gap:10px;align-items:baseline;flex-wrap:wrap';
                line.appendChild(U.el('span', '', CUR[c].icon + ' ' + CUR[c].name + ': ')); const v = U.el('b', '', fmt(c, x.left) + (x.of ? ' / ' + (c === 'usd' ? x.of.toFixed(2) : x.of.toLocaleString('pt-BR')) : '')); if (x.left <= cfg.warn[c]) v.style.color = '#e5484d'; line.appendChild(v);
                if (perDay > 0) line.appendChild(U.el('span', 'lu-hint', '≈ ' + Math.max(0, Math.floor(x.left / perDay)) + ' ' + T('dias no ritmo dos últimos 7 dias'))); balBox.appendChild(line);
            });
            if (!any) balBox.appendChild(U.el('div', 'lu-hint', T('Nenhum serviço com saldo respondeu (precisa da chave do Pollinations, TokenReply ou VoidAI).')));
        });
        U.toggle(s, 'Avisar quando o saldo estiver acabando', cfg.on, v => { cfg.on = v; saveCfg(); });
        [['pol', 'Pollinations (pollen)'], ['usd', 'TokenReply (US$)'], ['cr', 'VoidAI (créditos)']].forEach(([c, l]) => { const i = U.text(String(cfg.warn[c]), v => { const n = parseFloat(String(v).replace(',', '.')); if (n >= 0) { cfg.warn[c] = n; saveCfg(); } }, 10); i.style.width = '110px'; U.row(s, 'Avisar abaixo de — ' + l, i); });
        // semanas
        s = U.section(w.body, 'Por semana (últimas 8)', { open: true });
        const used = ['pol', 'usd', 'cr'].filter(c => rows.some(r => r[{ pol: 3, cr: 4, usd: 5 }[c]] > 0));
        used.forEach(c => {
            const idx = { pol: 3, cr: 4, usd: 5 }[c], vals = []; for (let i = 7; i >= 0; i--) vals.push(sum(rows, ws - i * 7 * DAY, ws - (i - 1) * 7 * DAY)[c]); const max = Math.max(...vals, 1e-9);
            s.appendChild(U.el('div', 'lu-hint', CUR[c].icon + ' ' + CUR[c].name)); const bars = U.el('div', 'sp-bars'); vals.forEach((v, i) => { const col = U.el('div', 'sp-bar'), b = U.el('i'); b.style.height = Math.max(2, v / max * 70) + 'px'; b.title = fmt(c, v); col.append(U.el('span', '', v ? (CUR[c].dig ? v.toFixed(CUR[c].dig > 3 ? 3 : 2) : Math.round(v)) : ''), b, U.el('span', '', i === 7 ? T('agora') : '-' + (7 - i) + 's')); bars.appendChild(col); }); s.appendChild(bars);
        });
        if (!used.length) s.appendChild(U.el('div', 'lu-hint', '—'));
        // por modelo
        s = U.section(w.body, 'Por modelo', { open: true });
        const by = {}; rows.forEach(r => { const e = by[r[1]] || (by[r[1]] = { label: r[2], d7: { pol: 0, cr: 0, usd: 0, n: 0 }, d30: { pol: 0, cr: 0, usd: 0, n: 0 }, all: { pol: 0, cr: 0, usd: 0, n: 0 } }); [[e.d7, 7], [e.d30, 30], [e.all, 1e5]].forEach(([o, d]) => { if (r[0] >= now - d * DAY) { o.pol += r[3]; o.cr += r[4]; o.usd += r[5]; o.n++; } }); });
        const list = Object.values(by).sort((a, b) => (b.d30.pol * 1000 + b.d30.usd * 100 + b.d30.cr / 1000) - (a.d30.pol * 1000 + a.d30.usd * 100 + a.d30.cr / 1000));
        if (list.length) { const t = U.el('table', 'sp-tbl'), hr = U.el('tr'); ['Modelo', '7 dias', '30 dias', 'Total', 'Respostas'].forEach(h => hr.appendChild(U.el('th', '', T(h)))); t.appendChild(U.el('thead')).appendChild(hr); const tb = U.el('tbody');
            list.slice(0, 60).forEach(e => { const tr_ = U.el('tr'); tr_.appendChild(U.el('td', '', e.label)); [e.d7, e.d30, e.all].forEach(o => { const td = U.el('td'); chips(o, td); tr_.appendChild(td); }); tr_.appendChild(U.el('td', '', String(e.all.n))); tb.appendChild(tr_); }); t.appendChild(tb); s.appendChild(t); } else s.appendChild(U.el('div', 'lu-hint', '—'));
        U.button(w.foot, 'Zerar o caderno', async () => { if (typeof ask === 'function') { const r = await ask({ title: 'Zerar os gastos?', body: 'Apaga só o caderno de gastos deste aparelho (não mexe nos saldos nem nas conversas).', buttons: ['Zerar', 'Cancelar'], danger: true }); if (r.index !== 0) return; } wr(KEY, []); w.close(); open(); });
    }
    window.lumeSpend = { add, open, checkBalances, get config() { return cfg; } };
    setTimeout(() => checkBalances(), 12000); setInterval(() => checkBalances(), 30 * 60000);   // confere ao abrir e a cada 30 min (o aviso so aparece uma vez por dia)
})();
