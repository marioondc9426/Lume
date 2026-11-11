# style-src: o "Visual novo" em Tailwind

O app **não precisa de Node nem de internet**: ele só carrega `libs/lume-look.css`, que já vem pronto (gerado aqui e guardado no repositório).

- `look.src.css`: a fonte. Cada regra usa `@apply` do Tailwind (`rounded-2xl`, `shadow-pop`, `bg-accent`...). O símbolo `§` vira `body[data-look="tw"][data-ui="modern"]`, então nada disso vale com o **Visual novo desligado** (Configurações > Aparência) nem na interface clássica.
- `tailwind.config.js`: as cores apontam para as variáveis de cada tema (`--bg-main`, `--accent`...), por isso os 7 temas e o editor de temas continuam funcionando. Só saem as regras escritas em `look.src.css` (nenhuma classe solta como `.flex` ou `.hidden`).
- `build.py`: gera `../libs/lume-look.css`.

Para mudar o visual:

```
cd style-src
npm install      # uma vez
python build.py  # depois de editar look.src.css
```

Depois é só recarregar o Lume (rodando do código-fonte ele recarrega sozinho). Os nomes de variáveis que começam com `--tw-` são do próprio Tailwind: as do Lume usam `--lk-`.
