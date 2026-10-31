/* Registro dos provedores EXTRAS (os que falam o formato da OpenAI): e a unica lista que o app.py, o iPhone (lume-backend.js) e a interface leem.
   Para adicionar um provedor novo (guia em libs/PROVIDERS.md): inclua um item aqui, e pronto (campo de chave, logo, lista de modelos e teste saem sozinhos).
     id        codigo curto (usado no id do modelo: "<id>:<modelo>")
     key       nome do provedor no logo/tabela de logos (icons/prov-<key>.png)    name   nome mostrado
     field     campo da chave no config.json            url   base da API (termina em /v1)
     spacing   segundos entre testes de saude (limite de pedidos do plano)
     showAll   true = mostra todos os modelos de chat, sem teste de saude; false = so os que passam no teste
     kind      como listar os modelos: "openai" (generico: tudo que o /models lista e e de chat) ou um dos especiais abaixo, que ja existem no codigo:
               ac (so tier free), ah (so ids terminados em free), lr (so ":free"), px, vd, tk (cada um com a regra do seu plano)
     placeholder / hint   o campo de chave nas Configuracoes     logo   arquivo em icons/ (ou "letter" para uma bolinha azul com a letra)
   Este arquivo e JSON dentro de "window.LUME_PROVIDERS = ...;": o Python le o texto e faz json.loads. */
window.LUME_PROVIDERS = [
  { "id": "lr", "key": "literouter", "name": "LiteRouter", "field": "literouter_api_key", "url": "https://api.literouter.com/v1", "spacing": 8.0, "showAll": true, "kind": "lr", "placeholder": "cole a chave", "logo": "prov-literouter.png",
    "hint": "Só os modelos \":free\". O plano grátis aceita 1 pedido a cada 7 segundos (o Lume espera sozinho). Chave em literouter.com, painel de chaves." },
  { "id": "ah", "key": "aihubmix", "name": "AIHubMix", "field": "aihubmix_api_key", "url": "https://aihubmix.com/v1", "spacing": 1.5, "showAll": false, "kind": "ah", "placeholder": "sk-...", "logo": "prov-aihubmix.png",
    "hint": "Só os modelos que terminam em \"free\". Chave em console.aihubmix.com." },
  { "id": "px", "key": "paxsenix", "name": "Paxsenix", "field": "paxsenix_api_key", "url": "https://api.paxsenix.org/v1", "spacing": 1.5, "showAll": true, "kind": "px", "placeholder": "sk-paxsenix-...", "letter": "P",
    "hint": "Mostra todos os modelos de chat. Chave em api.paxsenix.org." },
  { "id": "ft", "key": "freetheai", "name": "FreeTheAI", "field": "freetheai_api_key", "url": "https://api.freetheai.org/v1", "spacing": 1.5, "showAll": true, "kind": "openai", "placeholder": "ftai_...", "letter": "F",
    "hint": "Mostra todos os modelos, sem teste (o plano grátis tem só 50 pedidos por dia). Antes de usar, faça o check-in diário com captcha em freetheai.org/checkin. Chave em freetheai.org/dashboard/api-keys." },
  { "id": "vd", "key": "voidai", "name": "VoidAI", "field": "voidai_api_key", "url": "https://api.voidai.app/v1", "spacing": 1.5, "showAll": true, "kind": "vd", "placeholder": "sk-voidai-...", "logo": "prov-voidai.png",
    "hint": "Só os modelos que o plano grátis cobre. Os créditos diários do seu plano valem para todos. Chave em voidai.app/dashboard." },
  { "id": "tk", "key": "tokenreply", "name": "TokenReply", "field": "tokenreply_api_key", "url": "https://api.tokenreply.com/v1", "spacing": 1.5, "showAll": true, "kind": "tk", "placeholder": "sk-...", "logo": "prov-tokenreply.png",
    "hint": "Só os modelos do nível grátis e os \"semanais em destaque\" (gastam o crédito grátis da conta). Chave em tokenreply.com." }
];
