/* Enviar feedback de dentro do Lume: bug, sugestao ou comentario, com imagem se quiser, para o servidor lume-feedback.
   NAO e uma tela que cobre o app: e uma JANELA SEPARADA que fica por cima (PC e Linux), para voce ir testando o app e anotando ao mesmo tempo;
   no iPhone (que nao tem janelas) vira um painel flutuante, sem fundo escurecido, que voce arrasta e minimiza.
   Abre por: Configuracoes > "Enviar feedback aqui", o comando /feedback no chat ou Ctrl+Shift+F em qualquer tela.
   Privacidade: so vai o que voce escreve, a imagem que voce anexar e (se marcar) a versao e o sistema. Nunca chaves, config.json nem conversas.
   O mesmo formulario (lumeFeedbackForm) e usado no painel flutuante e na pagina feedback.html da janela separada. */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const MAX = 1_400_000;
    const el = (t, c, x) => window.LumeUI.el(t, c, x);

    function systemInfo() {
        const ua = navigator.userAgent || '', ios = !!window.__LUME_IOS || /iPhone|iPad/.test(ua);
        const so = ios ? 'iPhone (app)' : /Windows/.test(ua) ? 'Windows' : /Android/.test(ua) ? 'Android' : /Linux|X11/.test(ua) ? 'Linux' : /Mac/.test(ua) ? 'macOS' : 'navegador';
        const vt = (window.__FB_VERSION || '') + ' ' + ((document.getElementById('wl-ver') || {}).textContent || '') + ' ' + ((document.getElementById('upd-version') || {}).textContent || '');
        return { os: so, version: (vt.match(/\d+(?:\.\d+)+/) || [''])[0], log: (so + ' · ' + (navigator.language || '') + ' · tela ' + screen.width + 'x' + screen.height).slice(0, 200) };
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

    // ---- o formulario (vai dentro de qualquer elemento)
    window.lumeFeedbackForm = async function (host) {
        const u = window.LumeUI; let cat = 'bug', shot = '', url = '';
        try { url = (await (await fetch(API + '/api/config_status')).json()).feedback_url || ''; } catch (e) { /* sem status */ }
        const box = el('div'); box.style.cssText = 'display:flex;flex-direction:column;gap:10px'; host.appendChild(box);
        u.seg(box, [['bug', 'Bug'], ['sugestao', 'Sugestão'], ['outro', 'Outro']], 'bug', v => { cat = v; });
        const msg = el('textarea'); msg.placeholder = T('Conte o que aconteceu ou o que você gostaria…'); msg.style.cssText = 'width:100%;box-sizing:border-box;min-height:110px;resize:vertical'; box.appendChild(msg);
        const contact = u.text('', null, 120); contact.placeholder = T('Contato (opcional: e-mail ou usuário)'); box.appendChild(contact);
        let info = true; u.toggle(box, 'Incluir a versão e o sistema', true, v => { info = v; });
        const file = el('input'); file.type = 'file'; file.accept = 'image/*'; file.style.display = 'none'; box.appendChild(file);
        const row = el('div'); row.style.cssText = 'display:flex;gap:8px;align-items:center;flex-wrap:wrap'; box.appendChild(row);
        const lbl = el('span', 'lu-hint', T('sem imagem')); u.button(row, 'Anexar uma imagem', () => file.click()); row.appendChild(lbl);
        file.onchange = async () => { const f = file.files && file.files[0]; if (!f) return; try { shot = await shrink(f); lbl.textContent = '✓ ' + f.name.slice(0, 26) + ' (' + Math.round(shot.length * 0.75 / 1024) + ' KB)'; } catch (e) { shot = ''; lbl.textContent = T('Não deu para usar essa imagem.'); } };
        const sec = u.section(box, 'Servidor do feedback', { open: !url });
        const urlIn = u.text(url, null, 200); urlIn.placeholder = 'http://endereco:8787'; u.row(sec, 'Endereço', urlIn, 'É o servidor do projeto lume-feedback (quem recebe e mostra no dashboard).');
        const keyIn = u.text('', null, 100); keyIn.placeholder = T('(só se o servidor pedir)'); u.row(sec, 'Chave de envio', keyIn);
        const status = el('div', 'lu-hint', ''); box.appendChild(status);
        const saveSrv = async () => { const body = { feedback_url: urlIn.value.trim() }; if (keyIn.value.trim()) body.feedback_key = keyIn.value.trim(); await fetch(API + '/api/save_config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); };
        const send = u.button(box, 'Enviar', async () => {
            const text = msg.value.trim(); if (text.length < 3) { status.textContent = T('Escreva pelo menos algumas palavras.'); msg.focus(); return; }
            if (!/^https?:\/\//.test(urlIn.value.trim())) { sec.parentNode.open = true; status.textContent = T('Coloque o endereço do servidor de feedback.'); urlIn.focus(); return; }
            send.disabled = true; status.style.color = ''; status.textContent = T('Enviando…');
            try {
                await saveSrv(); const si = info ? systemInfo() : { os: '', version: '', log: '' };
                const r = await fetch(API + '/api/feedback_send', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category: cat, message: text, contact: contact.value.trim(), os: si.os, version: si.version, log: si.log, screenshot_b64: shot || undefined }) });
                const d = await r.json(); if (!r.ok || d.error) throw new Error(d.error || ('erro ' + r.status));
                status.style.color = '#3fb950'; status.textContent = T('Enviado! Obrigado.') + (d.id ? ' (#' + d.id + ')' : ''); msg.value = ''; shot = ''; lbl.textContent = T('sem imagem'); file.value = '';
            } catch (e) { status.style.color = '#e5484d'; status.textContent = String(e.message || e).slice(0, 160); }
            send.disabled = false; setTimeout(() => msg.focus(), 50);
        }, 'primary');
        send.style.alignSelf = 'flex-end'; setTimeout(() => msg.focus(), 60);
    };

    // ---- painel flutuante (iPhone e quando nao da para abrir uma janela): sem fundo, arrasta, minimiza, nao bloqueia o app
    function openPanel() {
        if (document.getElementById('fb-float')) { const p = document.getElementById('fb-float'); p.style.display = ''; return; }
        const p = el('div'); p.id = 'fb-float';
        p.style.cssText = 'position:fixed;right:14px;bottom:14px;width:min(380px,calc(100vw - 20px));max-height:84vh;z-index:7000;display:flex;flex-direction:column;background:var(--bg-main);color:var(--text-main);border:1px solid var(--border-color);border-radius:16px;box-shadow:0 14px 50px rgba(0,0,0,.45);overflow:hidden';
        const head = el('div'); head.style.cssText = 'display:flex;align-items:center;gap:6px;padding:9px 12px;cursor:grab;user-select:none;-webkit-user-select:none;touch-action:none;border-bottom:1px solid var(--border-color);font-weight:600;font-size:.92em'; head.appendChild(el('span', '', T('Enviar feedback'))); head.firstChild.style.flex = '1';
        const body = el('div'); body.style.cssText = 'padding:12px;overflow-y:auto';
        const btn = (txt, title, fn) => { const b = el('button', 'lu-x', txt); b.type = 'button'; b.title = T(title); b.style.cssText = 'position:static;width:26px;height:26px;font-size:13px'; b.onclick = fn; head.appendChild(b); return b; };
        btn('–', 'Minimizar', () => { body.style.display = body.style.display === 'none' ? '' : 'none'; });
        btn('✕', 'Fechar', () => p.remove());
        p.append(head, body); document.body.appendChild(p); window.lumeFeedbackForm(body);
        let dx = 0, dy = 0, drag = false;   // arrastar pelo cabecalho
        head.addEventListener('pointerdown', e => { if (e.target.closest('button')) return; const r = p.getBoundingClientRect(); drag = true; dx = e.clientX - r.left; dy = e.clientY - r.top; head.setPointerCapture(e.pointerId); head.style.cursor = 'grabbing'; });
        head.addEventListener('pointermove', e => { if (!drag) return; p.style.right = 'auto'; p.style.bottom = 'auto'; p.style.left = Math.max(0, Math.min(innerWidth - 60, e.clientX - dx)) + 'px'; p.style.top = Math.max(0, Math.min(innerHeight - 40, e.clientY - dy)) + 'px'; });
        head.addEventListener('pointerup', () => { drag = false; head.style.cursor = 'grab'; });
    }
    window.openFeedbackPanel = openPanel;

    // ---- abrir: janela separada (PC/Linux) ou painel flutuante
    window.openFeedback = async function () {
        const api = window.pywebview && window.pywebview.api;
        if (!window.__LUME_IOS && api && api.open_feedback) { try { if (await api.open_feedback()) return; } catch (e) { /* cai no painel */ } }
        openPanel();
    };
    document.addEventListener('keydown', e => { if (e.ctrlKey && e.shiftKey && (e.key === 'F' || e.key === 'f') && !e.altKey && window.LumeUI && document.getElementById('titlebar') !== null) { e.preventDefault(); window.openFeedback(); } });
})();
