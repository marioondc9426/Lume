# Kit de interface do Lume (`libs/lume-ui.js`)

Tudo que fica **fora da tela principal** (xadrez, mascote, painéis novos) usa estes blocos, para ter sempre o mesmo visual.
Cores vêm das variáveis do tema (`--bg-main`, `--text-main`, `--accent`...), então acompanham qualquer tema.

```js
const w = LumeUI.modal({ title: 'Meu painel', width: 440 });   // ✕ no canto; fecha com ✕, Esc ou clicando fora
const s = LumeUI.section(w.body, 'Aparência', { open: true });  // grupo que abre/fecha
LumeUI.toggle(s, 'Ligar isso', true, v => {});                   // interruptor
LumeUI.row(s, 'Cor', LumeUI.color('#2f8bff', v => {}, ['#2f8bff', '#ee5a8a']));
LumeUI.row(s, 'Estilo', LumeUI.select([['a', 'A'], ['b', 'B']], 'a', v => {}));
LumeUI.row(s, 'Tamanho', LumeUI.range(20, 80, 40, v => {}));
LumeUI.row(s, 'Nome', LumeUI.text('Lume', v => {}, 20));
LumeUI.seg(w.body, [['w', 'Brancas'], ['b', 'Pretas']], 'w', v => {});
LumeUI.button(w.foot, 'Salvar', () => {}, 'primary');
```

Regras de estilo (para não esquecer):
- Sem botão "Fechar": use o ✕ do `modal`.
- Mostre só o essencial; o resto vai em `section` (fechada) ou num menu "⋯".
- Texto sempre em português com tradução no dicionário `tr()` do `index.html`.
- Não escreva CSS novo para botão, interruptor, seletor ou grupo: use as classes `lu-*` (ou os helpers).
- Carregue `libs/lume-ui.js` antes do seu script em `index.html`.
