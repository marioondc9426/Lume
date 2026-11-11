/* Notas dos modelos: velocidade (medida aqui, no seu aparelho), inteligencia (Gratisfy/Artificial Analysis) e o seu ranking pessoal (votos da arena).
   Serve ao "Comparar modelos" (sortear por mais rapido/lento/inteligente), as dicas do mascote (qual modelo tentar depois de um erro) e a quem mais precisar.
     await lumeScores.load()            baixa as notas de inteligencia (guardadas 24 h pelo servidor)
     lumeScores.iq(m)                   nota de inteligencia do modelo (ou null se o Gratisfy nao conhece)
     await lumeScores.measure(models, { signal, onProgress, concurrency })   mede o tempo de resposta (pergunta minuscula)
     lumeScores.ms(m)                   tempo medido em ms (ou uma estimativa pela velocidade do Gratisfy; veja .estimated)
     lumeScores.order(models, 'fast' | 'slow' | 'smart' | 'dumb' | 'mine' | 'random')
     lumeScores.lineup(models, modo, n) n modelos sorteados entre os melhores do criterio (sem repetir o mesmo modelo de outro provedor)
     lumeScores.vote(vencedorId, [perdedorIds], empate)   e   lumeScores.record(id) -> { w, l, t } */
(() => {
    const SPEED_KEY = 'lume_speed_v1', VOTE_KEY = 'lume_arena_v1';
    const rd = k => { try { return JSON.parse(localStorage.getItem(k) || '{}') || {}; } catch (e) { return {}; } };
    const wr = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* sem armazenamento */ } };
    // cada leitura decodificava o JSON inteiro do localStorage (varias vezes por modelo, e de novo em cada comparacao do sort): a tabela de velocidade e o ranking travavam. Agora fica em memoria.
    const cache = {}, store = k => cache[k] || (cache[k] = rd(k));
    window.addEventListener('storage', e => { delete cache[e.key]; });

    // ---- inteligencia (Gratisfy). As chaves sao o nome do modelo so com letras e numeros (o mesmo calculo do servidor).
    let table = null, loading = null, loadErr = '';
    const keys = (...names) => {
        const out = new Set();
        for (let n of names) {
            if (!n) continue; n = String(n).toLowerCase().replace(/\([^)]*\)/g, '');
            const base = n.split('/').pop().replace(/:(free|cloud|thinking|latest|beta)$/, ''), noPre = n.replace(/^(?:pol|or|cf|groq|tdc|vc|l7|lr|ac|ah|tk|vd|nv|xp|x|ph|bm)[a-z]{0,3}:(?=[a-z@/])/, '');
            [n, base, noPre, noPre.split('/').pop().replace(/:(free|cloud|thinking|latest|beta)$/, '')].forEach(v => { const k = v.replace(/[^a-z0-9]/g, ''); if (k.length >= 4) out.add(k); });
        }
        return out;
    };
    const memo = new Map();
    function entry(m) {
        if (!table) return null; if (memo.has(m.id)) return memo.get(m.id);
        let best = null; for (const k of keys(m.id, m.label, m.famName && m.params ? m.famName + ' ' + m.params : '')) { const e = table.get(k); if (e && (!best || e[0] > best[0])) best = e; }
        memo.set(m.id, best); return best;
    }
    async function load(refresh) {
        if (table && !refresh) return true; if (loading) return loading;
        loading = (async () => {
            try {
                const r = await fetch(API + '/api/model_scores' + (refresh ? '?refresh=1' : '')), d = await r.json(); if (!r.ok || d.error) throw new Error(d.error || ('erro ' + r.status));
                table = new Map((d.rows || []).map(([k, i, t]) => [k, [i, t]])); memo.clear(); loadErr = ''; return true;
            } catch (e) { loadErr = String(e.message || e).slice(0, 140); return false; } finally { loading = null; }
        })();
        return loading;
    }
    const iq = m => { const e = entry(m); return e ? e[0] : null; };
    const tps = m => { const e = entry(m); return e && e[1] ? e[1] : null; };

    // ---- velocidade medida aqui
    const speed = () => store(SPEED_KEY);
    const cloud = m => !!(m.cloud || m.pol || m.or || m.cf || m.groq || m.tdc || m.vc || m.l7 || m.x);
    const paid = m => !!((m.pol && !m.free) || (m.xp && (m.credBase || m.credIn || m.credOut)) || m.priceIn > 0 || m.priceOut > 0);
    async function one(m, signal) {
        const t0 = performance.now(); let first = 0;
        try {
            await lumeAsk({ model: m, system: 'Responda no máximo com uma palavra.', user: 'Responda só com a palavra: ok', timeoutMs: 25000, signal, onText: () => { if (!first) first = performance.now() - t0; } });
            return { ok: true, ms: Math.round(performance.now() - t0), ttft: Math.round(first || performance.now() - t0), ts: Date.now() };
        } catch (e) { if (signal && signal.aborted) throw e; return { ok: false, ms: Math.round(performance.now() - t0), err: String(e.message || e).slice(0, 90), ts: Date.now() }; }
    }
    async function measure(models, o) {
        o = o || {}; const list = models.slice(), total = list.length, store = speed(); let done = 0, next = 0;
        const worker = async () => {
            while (next < list.length) {
                if (o.signal && o.signal.aborted) return; const m = list[next++];
                let r; try { r = await one(m, o.signal); } catch (e) { return; }
                store[m.id] = r; wr(SPEED_KEY, store); done++; if (o.onProgress) o.onProgress(done, total, m, r);
            }
        };
        await Promise.all(Array.from({ length: Math.max(1, Math.min(o.concurrency || 3, 6)) }, worker)); return done;
    }
    const measured = m => speed()[m.id] || null;
    // tempo para responder: o medido (ok) ou, sem medida, uma estimativa pela velocidade (tok/s) do Gratisfy
    function ms(m) { const r = measured(m); if (r && r.ok) return r.ms; const t = tps(m); return t ? Math.round(400 + 150000 / t) : null; }
    const estimated = m => { const r = measured(m); return !(r && r.ok) && !!tps(m); };

    // ---- votos da arena (o seu ranking)
    const votes = () => store(VOTE_KEY);
    function vote(winner, losers, tie) {
        const v = votes(), bump = (id, k) => { const e = v[id] || (v[id] = { w: 0, l: 0, t: 0 }); e[k]++; e.ts = Date.now(); };
        if (tie) [winner].concat(losers).forEach(id => bump(id, 't')); else { bump(winner, 'w'); losers.forEach(id => bump(id, 'l')); }
        wr(VOTE_KEY, v);
    }
    const record = id => votes()[id] || { w: 0, l: 0, t: 0 };
    const rate = id => { const e = votes()[id]; if (!e) return null; const n = e.w + e.l + e.t; return n ? (e.w + e.t / 2) / n : null; };

    // ---- ordenar / sortear
    const asc = (f, m1, m2) => { const a = f(m1), b = f(m2); return a == null ? (b == null ? 0 : 1) : b == null ? -1 : a - b; };
    function order(models, mode) {
        const l = models.slice();
        if (mode === 'fast') return l.sort((a, b) => asc(ms, a, b));
        if (mode === 'slow') return l.sort((a, b) => asc(m => { const v = ms(m); return v == null ? null : -v; }, a, b));
        if (mode === 'smart') return l.sort((a, b) => asc(m => { const v = iq(m); return v == null ? null : -v; }, a, b));
        if (mode === 'dumb') return l.sort((a, b) => asc(iq, a, b));
        if (mode === 'mine') return l.sort((a, b) => asc(m => { const v = rate(m.id); return v == null ? null : -v; }, a, b));
        for (let i = l.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [l[i], l[j]] = [l[j], l[i]]; } return l;
    }
    const known = { fast: ms, slow: ms, smart: iq, dumb: iq, mine: m => rate(m.id) };
    function lineup(models, mode, n) {
        const ord = order(models, mode), f = known[mode], pool = [], seen = new Set();
        for (const m of ord) {
            if (f && f(m) == null) continue; const fam = String(m.label || m.id).toLowerCase().replace(/\([^)]*\)/g, '').replace(/[^a-z0-9]/g, '');   // o mesmo modelo por outro provedor nao entra duas vezes
            if (seen.has(fam)) continue; seen.add(fam); pool.push(m); if (pool.length >= Math.max(8, n * 3)) break;
        }
        const src = pool.length >= n ? pool : order(models, 'random');   // sem dados suficientes para o criterio: sorteia de todos
        return order(src, 'random').slice(0, n);
    }
    window.lumeScores = { load, iq, tps, measure, measured, ms, estimated, order, lineup, vote, record, rate, cloud, paid, get error() { return loadErr; }, get ready() { return !!table; } };
})();
