/* Seletor de modelo igual ao do chat (familias na lista, e embaixo Parametros e Provedor), para usar em qualquer painel: xadrez, jogos...
     const p = lumeModelPicker({ models: () => lumeModels(), value: idAtual, onPick: m => {...} });   // devolve null se nao houver modelo
     host.appendChild(p.el); p.get() -> modelo escolhido.
   Reusa as funcoes do index.html (fin, brandEl, famLabelNodes, miniSelect, provLogos...). */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const mk = (t, c, x) => { const e = document.createElement(t); if (c) e.className = c; if (x != null) e.textContent = x; return e; };
    const css = document.createElement('style');
    css.textContent = `
        .lmp { position: relative; height: auto; display: block; } .lmp .select-trigger { height: 42px; box-sizing: border-box; }
        .lmp .select-options { position: absolute; top: calc(100% + 6px); bottom: auto; left: 0; right: 0; width: auto; min-width: 0; margin: 0; max-height: min(460px, 62vh); overflow-y: auto; z-index: 30; box-shadow: 0 14px 40px rgba(0,0,0,.5); }
        .lmp .select-options .mo-list { max-height: 240px; }
        .lmp .cm-logo { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; flex: none; } .lmp .cm-logo > * { max-height: 20px; max-width: 22px; height: 20px; display: inline-block; object-fit: contain; }
    `;
    document.head.appendChild(css);
    window.lumeModelPicker = function (o) {
        let list = o.models(); if (!list.length) return null;
        const provOf = m => { try { return providerName(m); } catch (e) { return ''; } }, logoOf = m => { const sp = mk('span', 'cm-logo'); try { fin(m); const br = brandOf(m); if (br) sp.appendChild(brandEl(br, m)); else sp.textContent = '☁'; } catch (e) { sp.textContent = '☁'; } return sp; };
        let pick = Math.max(0, list.findIndex(m => m.id === o.value));
        // seletor igual ao do chat: familias na lista, e embaixo Parametros e Provedor (reusa as funcoes do index.html)
        const cw = mk('div', 'custom-select lmp'), cb = mk('div', 'select-trigger'), box = mk('div', 'select-options'); cw.append(cb, box);
        const paintBtn = () => { cb.textContent = ''; const m = list[pick]; cb.append(logoOf(m), mk('span', 'model-text shrinkable', m.label || m.id), mk('div', 'select-arrow')); };
        const families = () => { const map = new Map(); list.forEach(m => { fin(m); if (!map.has(m.grp)) map.set(m.grp, []); map.get(m.grp).push(m); }); map.forEach(ms => ms.sort((x, y) => verKey(x.ver) - verKey(y.ver) || sizeNum(x) - sizeNum(y) || provOrd(x) - provOrd(y) || (x.plabel || '').localeCompare(y.plabel || ''))); return new Map([...map.entries()].sort((x, y) => x[1][0].base.toLowerCase().localeCompare(y[1][0].base.toLowerCase(), 'pt', { numeric: true }))); };
        let term = '';
        const choose = m => { pick = list.indexOf(m); paintBtn(); fillList(); if (o.onPick) o.onPick(m); };
        const fillList = () => {
            box.textContent = ''; const cur = list[pick], fams = families();
            const srch = document.createElement('input'); srch.type = 'text'; srch.placeholder = T('Buscar modelo…'); srch.autocomplete = 'off'; srch.value = term; srch.style.cssText = 'margin:8px;width:calc(100% - 16px);box-sizing:border-box'; srch.oninput = () => { term = srch.value; const pos = srch.selectionStart; fillList(); const n = box.querySelector('input'); if (n) { n.focus(); n.setSelectionRange(pos, pos); } }; box.appendChild(srch);
            const lst = mk('div', 'mo-list'); box.appendChild(lst); let i = 0;
            fams.forEach((sizes, fam) => {
                if (term && !(famTitle(sizes) + ' ' + sizes.map(providerOf).join(' ')).toLowerCase().includes(term.trim().toLowerCase())) return;
                const rec = sizes.find(m => m.rec) || sizes[0], el = mk('div', 'select-option k-' + famKind(sizes) + (fam === fin(cur).grp ? ' selected' : '')); el.style.setProperty('--i', i++);
                const label = mk('span', 'mo-label'); famLabelNodes(rec, famTitle(sizes)).forEach(n => label.appendChild(n)); el.appendChild(label);
                const pv = provLogos(sizes); if (pv) el.appendChild(pv);
                el.onclick = () => { if (fam === fin(cur).grp) return; const p0 = sizes.find(m => m.rec) || sizes.find(m => !m.heavy) || sizes[0]; choose(bestVariant(sizes.filter(x => x.pk === p0.pk))); };
                lst.appendChild(el);
            });
            if (!lst.firstChild) lst.appendChild(mk('div', 'select-option', T('Nenhum modelo encontrado')));
            const sizes = fams.get(fin(cur).grp) || [];
            if (sizes.length) {
                const row = mk('div', 'size-row'), keys = []; sizes.forEach(m => { let k = keys.find(x => x.pk === m.pk); if (!k) keys.push(k = { pk: m.pk, items: [] }); k.items.push(m); });
                const variants = (keys.find(k => k.pk === cur.pk) || { items: [cur] }).items;
                row.append(mk('span', 'size-label', T('Parâmetros')), miniSelect(keys.map(k => { const rep = k.pk === cur.pk ? cur : bestVariant(k.items), kinds = new Set(k.items.map(kindOf)); return { value: rep.id, label: rep.klabel + (rep.heavy ? ' ⚠' : ''), color: kinds.has('local') ? 'var(--k-local)' : kinds.has('cloud') ? 'var(--k-cloud)' : 'var(--k-paid)' }; }), cur.id, v => choose(list.find(m => m.id === v) || cur), T('Parâmetros')));
                row.appendChild(miniSelect(variants.map(m => ({ value: m.id, label: providerName(m) + provInfo(m), title: m.warn || '', color: m.pol ? 'var(--k-paid)' : isLocalM(m) ? 'var(--k-local)' : 'var(--k-cloud)' })), cur.id, v => choose(list.find(m => m.id === v) || cur), T('Provedor')));
                box.appendChild(row);
            }
        };
        const providerOf = m => { try { return providerName(m); } catch (e) { return ''; } };
        cb.onclick = () => { const on = !cw.classList.contains('open'); if (on) { const id = list[pick].id; list = o.models(); pick = Math.max(0, list.findIndex(m => m.id === id)); term = ''; fillList(); } cw.classList.toggle('open', on); if (on) { const cur = box.querySelector('.select-option.selected'); if (cur) cur.scrollIntoView({ block: 'center' }); } };
        const away = e => { if (!cw.isConnected) document.removeEventListener('mousedown', away); else if (!cw.contains(e.target)) cw.classList.remove('open'); }; document.addEventListener('mousedown', away);
        paintBtn();
        return { el: cw, get: () => list[pick] };
    };
})();
