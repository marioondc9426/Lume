// Backend do iPhone no Node, com a rede de mentira: registro de provedores, listagem generica e salvamento de chaves.
//   node tests/test_ios_backend.js
const fs = require('fs'), assert = require('assert'), path = require('path');
const R = path.join(__dirname, '..') + '/';
const store = {}; globalThis.localStorage = { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; }, removeItem: k => { delete store[k]; } };
globalThis.window = globalThis; globalThis.document = { documentElement: { classList: { add() {} } }, addEventListener() {} }; globalThis.location = { href: 'file:///index.html', origin: 'file://' };
eval(fs.readFileSync(R + 'libs/providers.js', 'utf8'));
const reg0 = window.LUME_PROVIDERS.length;
window.LUME_PROVIDERS.push({ id: 'zz', key: 'zz', name: 'ZZ', field: 'zz_api_key', url: 'https://zz.example/v1', spacing: 1, showAll: true, kind: 'openai' });
globalThis.fetch = async (url, o) => String(url) === 'http://fb.example/api/feedback' ? new Response(JSON.stringify({ ok: true, id: 7, got: JSON.parse(o.body).message }), { status: 201 }) : String(url) === 'https://zz.example/v1/models'
  ? new Response(JSON.stringify({ data: [{ id: 'chat-a' }, { id: 'text-embed-3' }, { id: 'vendor/chat-b', context_window: 32000 }, { id: 'x-image' }] }), { status: 200 })
  : new Response('{}', { status: 404 });
eval(fs.readFileSync(R + 'ios/backend-data.js', 'utf8').replace('window.LUME_DATA', 'globalThis.LUME_DATA'));
eval(fs.readFileSync(R + 'ios/lume-backend.js', 'utf8'));
(async () => {
  const f = globalThis.fetch, post = (p, b) => f('/api/' + p, { method: 'POST', body: JSON.stringify(b) });
  await post('save_config', { zz_api_key: 'k' });
  const ex = await (await f('/api/extra_models?prov=zz&force=1')).json();
  assert.strictEqual(ex.zz.saved, true, 'chave do provedor novo nao foi salva');
  assert.deepStrictEqual(ex.zz.models.map(m => m.id), ['chat-a', 'vendor/chat-b']);
  assert.strictEqual(ex.zz.models[1].ctx, 32000);
  assert.strictEqual(Object.keys(ex).length, reg0 + 1, 'todos os provedores do registro devem aparecer');
  const ov = await (await f('/api/providers_overview')).json();
  assert.ok(ov.zz && ov.zz.key === true && ov.lr, 'painel de provedores incompleto');
  const tts = await post('tts', { text: '' }); assert.strictEqual(tts.status, 502);
  assert.strictEqual((await post('feedback_send', { message: 'oi' })).status, 502, 'sem servidor configurado deve falhar');
  await post('save_config', { feedback_url: 'http://fb.example/' });
  const fb = await (await post('feedback_send', { category: 'bug', message: 'do iPhone' })).json(); assert.strictEqual(fb.id, 7); assert.strictEqual(fb.got, 'do iPhone');
  console.log('ios backend: ok'); process.exit(0);
})().catch(e => { console.error('FALHOU:', e.message); process.exit(1); });
