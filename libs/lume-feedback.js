/* Enviar feedback de dentro do Lume (PC e iPhone): bug, sugestao ou comentario, com imagem se quiser, para o servidor lume-feedback.
   Abre por Configuracoes > "Enviar feedback aqui" ou pelo comando /feedback no chat. O servidor e o do projeto lume-feedback/ (endereco em "Servidor do feedback").
   Privacidade: so vai o que voce escreve, a imagem que voce anexar e (se marcar) a versao e o sistema. Nunca chaves, config.json nem conversas. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const MAX = 1_400_000;

    function systemInfo() {
        const ua = navigator.userAgent || '', ios = !!window.__LUME_IOS || /iPhone|iPad/.test(ua);
        const so = ios ? 'iPhone (app)' : /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /Linux|X11/.test(ua) ? 'Linux' : /Mac/.test(ua) ? 'macOS' : 'navegador';
        const vt = ((document.getElementById('wl-ver') || {}).textContent || '') + ' ' + ((document.getElementById('upd-version') || {}).textContent || ''), ver = (vt.match(/\d+(?:\.\d+)+/) || [''])[0];
        return { os: so, version: ver, log: (so + ' · ' + (navigator.language || '') + ' · tela ' + innerWidth + 'x' + innerHeight).slice(0, 200) };
    }
    // a imagem e reduzida aqui mesmo (ate 1600 px, JPEG) para caber no limite do servidor
    function shrink(file) {
        return new Promise((res, rej) => {
            const img = new Image(), url = URL.createObjectURL(file);
            img.onload = () => {
                let w = img.naturalWidth, h = img.naturalHeight; const k = Math.min(1, 1600 / Math.max(w, h)); w = Math.round(w * k); h = Math.round(h * k);
                const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, 0, 0, w, h); URL.revokeObjectURL(url);
                for (const q of [0.85, 0.7, 0.55, 0.4]) { const d = c.toDataURL('image/jpeg', q), b64 = d.split(',')[1] || ''; if (b64.length * 0.75 <= MAX) return res(b64); }
                rej(new Error('imagem grande demais'));
            };
            img.onerror = () => { URL.revokeObjectURL(url); rej(new Error('nao consegui abrir a imagem')); }; img.src = url;
        });
    }

    window.openFeedback = async function () {
        if (document.getElementById('fb-modal')) return;
        const u = window.LumeUI, w = u.modal({ title: 'Enviar feedback', id: 'fb-modal', width: 520 });
        let cat = 'bug', shot = '', url = '';
        try { const cs = await (await fetch(API + '/api/config_status')).json(); url = cs.feedback_url || ''; } catch (e) { /* sem status */ }
        u.seg(w.body, [['bug', 'Bug'], ['sugestao', 'Sugestão'], ['outro', 'Outro']], 'bug', v => { cat = v; });
        const msg = u.el('textarea'); msg.placeholder = T('Conte o que aconteceu ou o que você gostaria…'); msg.style.cssText = 'width:100%;box-sizing:border-box;min-height:120px;resize:vertical'; w.body.appendChild(msg);
        const contact = u.text('', null, 120); contact.placeholder = T('Contato (opcional: e-mail ou usuário)'); w.body.appendChild(contact);
        let info = true; u.toggle(w.body, 'Incluir a versão e o sistema', true, v => { info = v; });
        const file = u.el('input'); file.type = 'file'; file.accept = 'image/*'; file.style.display = 'none'; w.body.appendChild(file);
        const row = u.el('div'); row.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap'; w.body.appendChild(row);
        const lbl = u.el('span', 'lu-hint', T('sem imagem'));
        u.button(row, 'Anexar uma imagem', () => file.click()); row.appendChild(lbl);
        file.onchange = async () => { const f = file.files && file.files[0]; if (!f) return; try { shot = await shrink(f); lbl.textContent = '✓ ' + f.name.slice(0, 30) + ' (' + Math.round(shot.length * 0.75 / 1024) + ' KB)'; } catch (e) { shot = ''; lbl.textContent = T('Não deu para usar essa imagem.'); } };
        const sec = u.section(w.body, 'Servidor do feedback', { open: !url });
        const urlIn = u.text(url, null, 200); urlIn.placeholder = 'http://endereco:8787'; u.row(sec, 'Endereço', urlIn, 'É o servidor do projeto lume-feedback (quem recebe e mostra no dashboard).');
        const keyIn = u.text('', null, 100); keyIn.placeholder = T('(só se o servidor pedir)'); u.row(sec, 'Chave de envio', keyIn);
        const status = u.el('div', 'lu-hint', ''); w.body.appendChild(status);
        const saveSrv = async () => { const body = { feedback_url: urlIn.value.trim() }; if (keyIn.value.trim()) body.feedback_key = keyIn.value.trim(); await fetch(API + '/api/save_config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); };
        const send = u.button(w.foot, 'Enviar', async () => {
            const text = msg.value.trim(); if (text.length < 3) { status.textContent = T('Escreva pelo menos algumas palavras.'); msg.focus(); return; }
            if (!/^https?:\/\//.test(urlIn.value.trim())) { sec.parentNode.open = true; status.textContent = T('Coloque o endereço do servidor de feedback.'); urlIn.focus(); return; }
            send.disabled = true; status.style.color = ''; status.textContent = T('Enviando…');
            try {
                await saveSrv(); const si = info ? systemInfo() : { os: '', version: '', log: '' };
                const r = await fetch(API + '/api/feedback_send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category: cat, message: text, contact: contact.value.trim(), os: si.os, version: si.version, log: si.log, screenshot_b64: shot || undefined }) });
                const d = await r.json(); if (!r.ok || d.error) throw new Error(d.error || ('erro ' + r.status));
                status.style.color = '#3fb950'; status.textContent = T('Enviado! Obrigado.') + (d.id ? ' (#' + d.id + ')' : ''); msg.value = ''; shot = ''; lbl.textContent = T('sem imagem');
            } catch (e) { status.style.color = '#e5484d'; status.textContent = String(e.message || e).slice(0, 160); }
            send.disabled = false;
        }, 'primary');
        setTimeout(() => msg.focus(), 60);
    };
})();
