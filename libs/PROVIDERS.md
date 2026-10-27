# Como adicionar um provedor de IA

Os provedores "extras" (os que falam o formato da OpenAI) ficam todos em **`libs/providers.js`**. Esse arquivo é lido pelo `app.py`, pelo iPhone (`ios/lume-backend.js`) e pela interface (`index.html`): **não precisa mexer em mais nada** para um provedor comum.

1. Em `libs/providers.js`, copie um item de `window.LUME_PROVIDERS` e troque:
   - `id`: código curto e único (ex.: `zz`); os ids dos modelos ficam `zz:<modelo>`
   - `key` e `name`: nome interno (para o logo) e o nome mostrado
   - `field`: o campo da chave no `config.json` (ex.: `zz_api_key`; a reserva é `zz_api_key_backup`)
   - `url`: base da API, terminando em `/v1`
   - `spacing`: segundos entre testes de saúde; `showAll`: `true` mostra todos os modelos de chat sem teste
   - `kind`: `"openai"` (genérico: tudo que o `/models` lista e é de chat). Os outros (`ac`, `ah`, `lr`, `px`, `vd`, `tk`) já têm regra própria no código
   - `placeholder`, `hint`: o texto do campo de chave em Configurações
   - `logo`: arquivo em `icons/` (ex.: `prov-zz.png`) ou `letter: "Z"` para uma bolinha azul com a letra
2. Ponha o logo em `icons/` (se tiver).
3. Pronto: o campo de chave aparece em Configurações > Chaves de API, o painel de provedores lista, os modelos entram na lista e o iPhone usa o mesmo registro.

Só se o provedor tiver uma regra de listagem diferente (plano, filtro, preço), crie um `kind` novo nos dois lugares: `extra_models` no `app.py` e `extraRaw` no `ios/lume-backend.js`.
