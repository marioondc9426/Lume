/* Voz do Lume: microfone (STT, fala -> texto) e ler em voz alta (TTS, texto -> fala), pelo Pollinations (gasta pollen da sua chave).
   Configuracoes ficam em Configuracoes > Geral. O servidor faz as chamadas: /api/stt e /api/tts (PC e iPhone). */
(() => {
    const T = s => (typeof tr === 'function' ? tr(s) : s);
    const DEF = { stt: 'openai/whisper-large-v3', lang: 'pt', tts: 'openai/tts-1', voice: 'nova', auto: false, send: false };
    const STT = [['openai/whisper-large-v3', 'Whisper large v3 (padrão)'], ['openai/gpt-transcribe', 'GPT Transcribe'], ['microsoft/mai-transcribe-2', 'MAI Transcribe 2']];
    const TTS = [['openai/tts-1', 'OpenAI TTS-1 (rápido)'], ['openai/tts-1-hd', 'OpenAI TTS-1 HD (mais natural)'], ['microsoft/mai-voice-2.1', 'MAI Voice 2.1'], ['microsoft/mai-voice-2.1-flash', 'MAI Voice 2.1 Flash']];
    const LANGS = [['pt', 'Português'], ['en', 'English'], ['es', 'Español'], ['fr', 'Français'], ['de', 'Deutsch'], ['it', 'Italiano'], ['', 'Automático']];
    const OPENAI_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'];
    const MAI_VOICES = { 'Português (Brasil)': ['pt-BR-Luana', 'pt-BR-Caio', 'pt-BR-Pedro', 'pt-BR-Rafael', 'pt-BR-Harper', 'pt-BR-Grant'], 'Português (Portugal)': ['pt-PT-Rui', 'pt-PT-Harper', 'pt-PT-Grant'],
        'English (US)': ['en-US-Olivia', 'en-US-Ethan', 'en-US-Iris', 'en-US-Jasper', 'en-US-Sage', 'en-US-Harper', 'en-US-Grant'], 'English (UK)': ['en-GB-Emily', 'en-GB-Harry'],
        'Español': ['es-ES-Marta', 'es-MX-Valeria', 'es-MX-Alejo', 'es-MX-Harper', 'es-MX-Grant'], 'Français': ['fr-FR-Soleil', 'fr-FR-Marc', 'fr-FR-Harper', 'fr-FR-Grant'], 'Deutsch': ['de-DE-Mia', 'de-DE-Klaus', 'de-DE-Harper', 'de-DE-Grant'], 'Italiano': ['it-IT-Rosa', 'it-IT-Luca', 'it-IT-Harper', 'it-IT-Grant'] };
    const V = () => Object.assign({}, DEF, (window.config && config.voice) || {});
    const el = (id) => document.getElementById(id);
    const mkOpts = (sel, list, val) => { sel.textContent = ''; list.forEach(([v, l]) => sel.add(new Option(T(l), v))); sel.value = val; };

    // ---- configuracoes (Configuracoes > Geral): os campos estao no index.html; aqui so enchemos e lemos
    function fillVoices(model, cur) {
        const sel = el('opt-tts-voice'); if (!sel) return; sel.textContent = '';
        if (model.startsWith('openai/')) OPENAI_VOICES.forEach(v => sel.add(new Option(v, v)));
        else Object.entries(MAI_VOICES).forEach(([g, vs]) => { const og = document.createElement('optgroup'); og.label = g; vs.forEach(v => og.appendChild(new Option(v.split('-').pop() + ' · ' + v.slice(0, 5), v))); sel.appendChild(og); });
        sel.value = [...sel.options].some(o => o.value === cur) ? cur : sel.options[0].value;
    }
    window.lumeVoiceLoad = () => {
        const v = V(); if (!el('opt-stt-model')) return;
        mkOpts(el('opt-stt-model'), STT, v.stt); mkOpts(el('opt-stt-lang'), LANGS, v.lang); mkOpts(el('opt-tts-model'), TTS, v.tts);
        fillVoices(v.tts, v.voice); el('opt-tts-auto').checked = !!v.auto; el('opt-stt-send').checked = !!v.send;
        el('opt-tts-model').onchange = () => fillVoices(el('opt-tts-model').value, '');
    };
    window.lumeVoiceSave = () => {
        if (!el('opt-stt-model')) return;
        config.voice = { stt: el('opt-stt-model').value, lang: el('opt-stt-lang').value, tts: el('opt-tts-model').value, voice: el('opt-tts-voice').value, auto: el('opt-tts-auto').checked, send: el('opt-stt-send').checked };
    };
    window.lumeVoiceTest = () => { window.lumeVoiceSave(); speak(T('Olá! Esta é a voz que você escolheu.'), null); };

    // ---- ler em voz alta (TTS)
    let player = null, playBtn = null;
    const stopSpeak = () => { if (player) { try { player.pause(); } catch (e) { /* ja parou */ } player = null; } if (playBtn) { playBtn.classList.remove('speaking', 'loading'); playBtn = null; } };
    const speakable = t => String(t || '').replace(/```[\s\S]*?```/g, ' ').replace(/`([^`]*)`/g, '$1').replace(/!\[[^\]]*\]\([^)]*\)/g, ' ').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/https?:\/\/\S+/g, ' ')
        .replace(/^\s{0,3}#{1,6}\s*/gm, '').replace(/^\s*[-*+]\s+/gm, '').replace(/^\s*\d+[.)]\s+/gm, '').replace(/\|/g, ' ').replace(/[*_~>]+/g, '').replace(/:[a-z0-9_+-]+:/gi, ' ').replace(/\s+/g, ' ').trim();
    async function speak(text, btn) {
        if (btn && btn === playBtn) { stopSpeak(); return; }   // segundo clique no mesmo botao para
        stopSpeak(); const t = speakable(text); if (!t) return;
        const v = V(); if (btn) { playBtn = btn; btn.classList.add('loading'); }
        try {
            const r = await fetch(API + '/api/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: t, model: v.tts, voice: v.voice }) });
            if (!r.ok) { let m = ''; try { m = (await r.json()).error; } catch (e) { /* sem corpo */ } throw new Error(m || ('erro ' + r.status)); }
            if (btn && playBtn !== btn) return;   // o usuario parou enquanto carregava
            const url = URL.createObjectURL(await r.blob()); player = new Audio(url);
            player.onended = player.onerror = () => { URL.revokeObjectURL(url); stopSpeak(); };
            if (btn) { btn.classList.remove('loading'); btn.classList.add('speaking'); }
            await player.play();
        } catch (e) { stopSpeak(); if (typeof showInfo === 'function') showInfo(T('Não consegui falar: ') + String(e.message || e).slice(0, 160), 6000); }
    }
    window.lumeSpeak = speak; window.lumeStopSpeak = stopSpeak;
    window.lumeAutoRead = div => { if (!V().auto || !div) return; const s = div.querySelector('.final-text'); if (s) speak(s.innerText || s.textContent, null); };
    window.lumeSpeakBtn = (div, btn) => speak((div.querySelector('.final-text') || {}).innerText || div._raw || '', btn);

    // ---- microfone (STT)
    let rec = null, stream = null, chunks = [], timer = null, t0 = 0;
    const micBtn = () => el('mic-btn');
    const micState = s => { const b = micBtn(); if (!b) return; b.classList.toggle('rec', s === 'rec'); b.classList.toggle('busy', s === 'busy'); b.title = s === 'rec' ? T('Parar de gravar') : s === 'busy' ? T('Transcrevendo...') : T('Falar (microfone)'); };
    const b64 = blob => new Promise((res, rej) => { const f = new FileReader(); f.onload = () => res(String(f.result).split(',')[1] || ''); f.onerror = () => rej(f.error); f.readAsDataURL(blob); });
    async function mic() {
        if (rec) { rec.stop(); return; }
        if (!navigator.mediaDevices || !window.MediaRecorder) { showInfo(T('Este aparelho não deixa gravar áudio aqui.'), 6000); return; }
        try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); } catch (e) { showInfo(T('Sem permissão para usar o microfone.'), 6000); return; }
        const type = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'].find(t => MediaRecorder.isTypeSupported(t)) || '';
        chunks = []; rec = new MediaRecorder(stream, type ? { mimeType: type } : {});
        rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
        rec.onstop = async () => {
            clearInterval(timer); stream.getTracks().forEach(t => t.stop()); const mime = (rec && rec.mimeType) || type || 'audio/webm'; rec = null;
            if (Date.now() - t0 < 600 || !chunks.length) { micState('idle'); return; }   // toque sem querer
            micState('busy');
            try {
                const v = V(), r = await fetch(API + '/api/stt', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ audio: await b64(new Blob(chunks, { type: mime })), mime, model: v.stt, lang: v.lang }) });
                const d = await r.json(); if (!r.ok || d.error) throw new Error(d.error || ('erro ' + r.status));
                if (!d.text) { showInfo(T('Não entendi o áudio. Tente de novo.'), 5000); }
                else { const p = el('prompt'); p.value = (p.value ? p.value.replace(/\s+$/, '') + ' ' : '') + d.text; p.dispatchEvent(new Event('input')); p.focus(); if (v.send && typeof onSendClick === 'function') onSendClick(); }
            } catch (e) { showInfo(T('Não consegui transcrever: ') + String(e.message || e).slice(0, 160), 6000); }
            micState('idle');
        };
        t0 = Date.now(); rec.start(); micState('rec'); timer = setInterval(() => { if (Date.now() - t0 > 120000 && rec) rec.stop(); }, 1000);   // para sozinho em 2 minutos
    }
    window.lumeMic = mic;
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && rec) { chunks = []; rec.stop(); } });

    const css = document.createElement('style');
    css.textContent = `
        .mic-btn { flex: none; width: 36px; height: 36px; padding: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; order: 9; margin: 0; }
        .mic-btn svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
        .mic-btn.rec { background: #e5484d; border-color: #e5484d; color: #fff; animation: micPulse 1s ease-in-out infinite; } .mic-btn.busy { opacity: .55; pointer-events: none; }
        @keyframes micPulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(229,72,77,.55); } 50% { box-shadow: 0 0 0 8px rgba(229,72,77,0); } }
        .copy-btn.speaking { border-color: var(--accent); background: rgba(100,140,255,.22); } .copy-btn.loading { opacity: .5; }
        .copy-btn svg.spk { width: 14px; height: 14px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    `;
    document.head.appendChild(css);
    const init = () => { const b = micBtn(); if (b && (!navigator.mediaDevices || !window.MediaRecorder)) b.style.display = 'none'; };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
