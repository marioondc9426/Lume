/* Painel "Servidores MCP" (Configuracoes > Code): o dono cola a configuracao no formato do Claude Desktop ({"mcpServers": {...}}),
   o Lume liga cada servidor e mostra se conectou e quantas ferramentas ele tem. A IA do modo Code usa essas ferramentas (sempre pedindo permissao). Usa LumeUI (libs/lume-ui.js). */
(() => {
    const T = (s, v) => (typeof tr === 'function' ? tr(s, v) : s);
    const EX = '{\n  "mcpServers": {\n    "filesystem": {\n      "command": "npx",\n      "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\\\Users\\\\voce\\\\Documents"]\n    }\n  }\n}';
    const STATE = { ready: ['✅', '#3fb950'], starting: ['⏳', '#f0b429'], error: ['⛔', '#e5484d'], off: ['⚪', '#8b949e'] };

    async function api(path, body) {
        const r = await fetch(API + path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : undefined);
        const d = await r.json().catch(() => ({})); if (!r.ok && !d.error) d.error = 'HTTP ' + r.status; return d;
    }

    function open() {
        const w = LumeUI.modal({ title: 'Servidores MCP', width: 640 }), el = LumeUI.el;
        const hint = el('div', 'lu-hint', T('MCP liga ferramentas externas à IA do modo Code (arquivos, GitHub, bancos de dados...). Cole aqui a configuração no formato do Claude Desktop. Cada servidor é um programa que roda no seu PC; só ligue os que você confia. A IA sempre pede permissão antes de usar uma ferramenta (vale 10 minutos por servidor).'));
        const box = el('textarea'); box.rows = 11; box.spellcheck = false; box.placeholder = EX;
        box.style.cssText = 'width:100%;box-sizing:border-box;font-family:Consolas,monospace;font-size:.82em;resize:vertical;border-radius:10px;padding:10px;background:var(--bg-input,rgba(128,128,128,.12));color:var(--text-main);border:1px solid var(--border-color)';
        const list = el('div'); list.style.cssText = 'display:flex;flex-direction:column;gap:6px';
        const msg = el('div', 'lu-hint'); w.body.append(hint, box, msg, list);
        const draw = status => {
            list.innerHTML = '';
            (status || []).forEach(s => {
                const [ic, col] = STATE[s.state] || STATE.off, row = el('div'); row.style.cssText = 'padding:8px 10px;border-radius:10px;background:rgba(128,128,128,.10);font-size:.86em';
                const head = el('div'); head.innerHTML = '<span>' + ic + '</span> <b></b> <span style="opacity:.6"></span>'; head.querySelector('b').textContent = s.name;
                head.lastChild.textContent = s.state === 'ready' ? T('{n} ferramentas', { n: s.tools.length }) : s.state === 'starting' ? T('conectando...') : s.state === 'off' ? T('desligado') : T('erro');
                head.style.color = col; head.querySelector('b').style.color = 'var(--text-main)'; row.appendChild(head);
                const sub = el('div', 'lu-hint', s.state === 'error' ? s.error : s.state === 'ready' ? s.tools.slice(0, 12).join(', ') + (s.tools.length > 12 ? '…' : '') : s.command); sub.style.wordBreak = 'break-word'; row.appendChild(sub); list.appendChild(row);
            });
            if (!(status || []).length) list.appendChild(el('div', 'lu-hint', T('Nenhum servidor configurado.')));
        };
        const load = async () => { const d = await api('/api/mcp'); if (d.error) { msg.textContent = T('Só no PC do dono.'); return; } box.value = (d.status || []).length ? d.json : ''; draw(d.status); };
        const save = async restart => {
            msg.textContent = T('Conectando... (a primeira vez pode baixar o servidor, isso demora)'); msg.style.color = '';
            const d = await api('/api/mcp_save', { json: box.value.trim() || '{}', restart: !!restart });
            if (d.error) { msg.textContent = d.error; msg.style.color = '#e5484d'; return; }
            box.value = (d.status || []).length ? d.json : ''; draw(d.status); const ok = (d.status || []).filter(s => s.state === 'ready').length;
            msg.textContent = T('Salvo. {n} servidor(es) conectado(s).', { n: ok }); msg.style.color = '';
        };
        LumeUI.button(w.foot, 'Reiniciar todos', () => save(true));
        LumeUI.button(w.foot, 'Salvar e conectar', () => save(false), 'primary');
        load();
    }
    window.lumeMcp = { open };
})();
