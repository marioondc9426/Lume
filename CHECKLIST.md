# Lume: checklist e guia do projeto

> **REGRA: atualize este arquivo SEMPRE que adicionar, mudar ou remover algo no app (no mesmo commit).**
> Ele existe para a memória sobreviver quando o contexto da conversa é compactado. Se uma coisa não está aqui, assume-se que ela não existe.
> Legenda: `[x]` pronto e testado · `[~]` pronto, mas **não verificado de verdade** (ver "Não verificado") · `[ ]` ideia / a fazer · `[-]` removido de propósito.

Última atualização: 2026-11-03 (v4.0 em desenvolvimento, só local, sem push nem tag).

---

## 1. Regras de trabalho (do dono do projeto)

- [x] O dono escreve em **pt-BR** e não é programador profissional: responder em pt-BR, direto, dizendo **o que foi testado e o que não foi**.
- [x] Tom: pode ser descontraído e escrever do jeito dele, **exceto** em coisas ligadas ao pai dele e em texto que outras pessoas leem (commit, CHANGELOG, PR).
- [x] **v4.0 fica local**: commitar, **não** dar push nem tag até o dono pedir. Tudo que ele pedir entra na versão em desenvolvimento.
- [x] CHANGELOG: uma linha por mudança em `CHANGELOG.md` (só português; o `CHANGELOG-EN.md` não tem seção 4.0).
- [x] Commit termina com `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- [x] **Nunca abrir o conteúdo de `state.json`, `history.json` ou `config.json`** para depurar sem perguntar (têm chaves e conversas).
- [x] Painéis novos usam o kit `libs/lume-ui.js` (guia `libs/UI-KIT.md`): ✕ no canto, poucos controles visíveis, o resto recolhido ou em menu.
- [x] O app se chama **Lume** (antes Qwen). A logo é gerada por `make_icons.py`.
- [x] Modelos que o dono **não quer**: Grok, Llama (fracos e meio caros), Gemma/Nemotron extras, Google AI Studio, Cerebras, NIM, GitHub Models, SiliconFlow, Chutes. (Mistral Large 4 ele pediu, então entra.)
- [x] Não matar processos em massa (`taskkill /IM python.exe` é negado): matar só o PID do meu teste (achar pela porta com `netstat`).
- [x] O dono reconhece que o `app.py` está bagunçado e não quer reclamação sobre isso.
- [x] A **integração com o navegador fica como está**, e o tema dela é o do app (escuro).

## 2. Como rodar, testar e montar

| O quê | Comando |
|---|---|
| Rodar do código | `python app.py` (ou `run.bat`) |
| Testes | `python -m unittest discover -s tests` (hoje: 18 OK) e `node tests/test_ios_backend.js` |
| Sintaxe do `index.html` | extrair o `<script>` mais longo e rodar `node --check` nele (fazer **depois de toda edição** no HTML) |
| `.exe` | `python build_exe.py` → `dist/Lume.exe` (+ `Lume-Setup.exe` no GitHub) |
| Linux | `python build_linux.py` (testado só em CachyOS/KDE por SSH, pasta `~/lume-test`) |
| iPhone | `python ios/build_www.py` (+ `python ios/gen_data.py` se a lista de modelos mudou); o `.ipa` não é assinado |
| Dados | `%LOCALAPPDATA%\Lume` no `.exe`; a pasta do projeto quando roda do código. `LUME_DATA_DIR` e `LUME_PORT` mudam isso (para testes) |

Dicas de teste (a "harness" = script que abre o Lume numa janela pywebview escondida, aperta botões por código e tira print):
- [x] Rodar com `python -u` quando usar `os._exit`. Heredoc com `\n` dentro de f-string quebra: usar a ferramenta Edit ou `chr(10)`.
- [x] Modelo falso: trocar `app.stream_model` por um gerador que devolve `('content', 'texto')`.
- [x] Teste de selecionar texto: não usar tkinter (o loop não roda aqui); usar um formulário do PowerShell (ele é terminal, então desligar o filtro de terminal no teste).
- [x] O `taskkill` só no PID do meu teste.

## 3. Mapa dos arquivos

| Arquivo / pasta | Para que serve |
|---|---|
| `app.py` | Servidor HTTP + janela pywebview + toda a lógica (provedores, agente, ferramentas, config, atualizador) |
| `index.html` | A interface inteira (CSS, HTML e JS num arquivo só) |
| `quick.html` | A caixinha flutuante do Alt+Espaço |
| `vcomp.py` | Computador virtual: prints, janelas, mouse e teclado em segundo plano (Windows) |
| `lumemcp.py` | Cliente MCP (servidores de ferramentas por stdio) |
| `lumebrowser.py` | Ponte com a extensão do navegador (fila, pareamento, ferramentas `mcp__browser__*`) |
| `browser-extension/` | A extensão (MV3): `manifest.json`, `background.js`, `popup.html/js`, `LEIA-ME.txt` |
| `guests.py` | Modo amigos (contas e limites) |
| `tls.py` | HTTPS local com CA própria |
| `libs/` | Módulos da interface: `providers.js` (registro de provedores), `lume-ui.js` (kit de UI), `lume-router.js` (Lume Auto), `lume-scores.js` (notas), `lume-compare.js` (arena), `lume-chess.js`, `lume-games.js`, `lume-duel.js`, `lume-pet.js` (mascote), `lume-voice.js`, `lume-select.js` (barrinha ao selecionar texto), `lume-modelpick.js`, `lume-mcp.js`, `lume-spend.js`, `lume-feedback.js`... |
| `ios/` | App do iPhone: `lume-backend.js` (porte do `app.py` em JS), `backend-data.js` (gerado), `build_www.py`, `project.yml` |
| `tests/` | `test_core.py`, `test_feedback.py`, `test_ios_backend.js` |
| `feedback-app/`, `lume-feedback/` | App de feedback e servidor + dashboard de feedback |
| `installer/` | Instaladores (Windows Inno Setup, Linux) |
| `.github/workflows/` | `build`, `linux`, `ios`, `ios-live`, `tests`, `feedback`, `release-notes` |
| `icons/`, `fonts/`, `sounds/` | Imagens/logos (nome exato = logo aparece sozinha), fontes locais, sons opcionais |
| `accounts/` | Uma pasta por conta (conversas, memórias, `account.json` com o papel) |
| `CHANGELOG.md`, `CHANGELOG-EN.md`, `README.md` | Histórico e apresentação |

## 4. Atalhos e portas

- [x] **Alt+Espaço**: caixinha flutuante (liga/desliga em Configurações > App).
- [x] **Ctrl+Alt+Espaço**: caixinha já com o **texto selecionado** em qualquer app (liga/desliga em Configurações > App).
- [x] **Ctrl+Shift+F**: janela de feedback. **Ctrl+Enter** na arena compara. **Esc** fecha janelas, a caixinha e o seletor em tela cheia.
- [x] Servidor: porta **8000** (HTTP) e **8443** (HTTPS). A extensão do navegador procura o Lume nas portas **8000 a 8010**.

---

## 5. Chat

- [x] Várias conversas ao mesmo tempo (trocar de chat com a IA respondendo); cada chat tem a sua geração e o seu "parar".
- [x] Fila de mensagens (aparece pontilhada e sai sozinha); apagar a mensagem da fila antes de a IA ver.
- [x] Editar suas mensagens (lápis) e reenviar, regenerar respostas (↻, mesmo modelo ou outro), versões `‹ 1/3 ›`, apagar.
- [x] Blocos de raciocínio ("Pensamento 1", "2"...), incluindo `<think>` dentro do texto e esforço de raciocínio (Automático, Nenhum... Máximo).
- [x] Markdown completo (títulos, tabelas, listas aninhadas, tarefas `- [x]`, citações, riscado, links), LaTeX vira Unicode, emojis `:nome:`.
- [x] Pesquisa na web decidida pela IA (ferramenta `search_web` e `read_url`; Exa com chave, senão DuckDuckGo), cartões de fonte, 1 a 25 resultados.
- [x] Anexos: imagem, PDF, Word, Excel, PowerPoint, OpenDocument; arrastar, colar, "tratar como .txt". Botão **Imagens** (troca as imagens antigas por descrição em texto).
- [x] Memória: o Lume sugere "Lembrar?", você apaga o que quiser; memória por conta.
- [x] Busca de chats com filtros: `modelo:`, `desde:`, `ate:`, `pasta:`, `fixado`, `tudo`. Fixados e pastas.
- [x] Barrinha ao selecionar texto no chat: Copiar, Pesquisar, Traduzir, Citar, Explicar, Ler em voz alta.
- [x] Voz: microfone (STT) e alto-falante (TTS) pelo Pollinations; enviar sozinho; ler tudo sozinho; escolha dos modelos de fala.
- [x] Mascote (bolinha com olhos): dicas de erro com "Tentar com outro modelo", analisa código antes de rodar (Seguro/Atenção/Perigoso), 10 expressões, bem customizável.
- [x] Medidores: tokens/s ao vivo, barra de contexto, VRAM/GPU, FPS opcional, estimativa de custo ao digitar, gastos por modelo (🌸 pollen, 💵 TokenReply, 💳 VoidAI).
- [x] Conversa fica colada no fim enquanto as imagens carregam; botão ↓ para voltar ao fim.
- [x] Português e inglês (dicionário `tr()`; chave nova entra antes de `'Minimizar': 'Minimize'`).

## 6. Seletor de modelos (v4.0, mexido neste ciclo)

- [x] Famílias por marca, com logos dos provedores à direita, cores: **azul** local, **cinza** nuvem grátis, **amarelo** pago.
- [x] Linha de **Parâmetros** e **Provedor** abaixo; esforço de raciocínio com botão ↻ (descobre os níveis aceitos).
- [x] **Ordem padrão: das marcas mais famosas para as menos** (GPT, Claude, Gemini, DeepSeek, Qwen, Kimi, GLM, Grok, Llama, Mistral, MiniMax, Gemma, Nemotron, resto A–Z). Lista em `FAME` no `index.html`.
- [x] **Ordenar por**: Mais famosos · A–Z · Preço barato→caro · Preço caro→barato · Velocidade · Novos (usa o campo `created` do catálogo). Escolha salva em `config.modelSort`.
- [x] **Favoritos** (estrela ☆/★ em cada família, seção no topo; `config.favModels`).
- [x] **Recomendados** (seção quando a ordem é "Mais famosos"; lista `REC_GRPS`: gpt, claude, gemini, deepseek, qwen, kimi, glm).
- [x] **Modelo que abre ao clicar na família** (`REC_PICK`): GPT → **6.1 Terra** (rápido e barato; o 6.1 Sol e o 5.6 Sol são caros) e Kimi → **K2.6** (o K3 é lento e caro). O que você escolheu antes continua valendo.
- [x] **Nomes compactos**: muitas versões viram faixas, ex.: `GPT 5 – 5.6 Sol, 6 Luna – 6.1 Sol` (nome só nas pontas: o mais barato no começo, o mais caro no fim).
- [x] **Tela cheia**: padrão no celular/iPhone; no PC é um interruptor (Configurações > Aparência: "Seletor de modelos em tela cheia"). Tem ✕, busca e ordenação.
- [~] Tela cheia no celular de verdade (testado só numa janela estreita no PC).
- [x] Compactar a conversa sozinho quando o contexto passa de 85% (interruptor em Aparência; padrão ligado, **desligado em modelos de 32K de contexto ou menos** enquanto você não escolher), igual ao botão Compactar.
- [x] Abre rápido e volta ao último modelo; lista só é reconstruída quando algo muda (não fecha sozinha).
- [x] Modelos de provedores extras com id fora do padrão (FreeTheAI: `claude-4-5-haiku`, `deepseek-chat`, `qwen-plus`, `grok-4.6`) agora caem na família certa (antes cada um virava uma linha solta, com o logo do DeepSeek sem nome). Regras em `parseDyn`; modelos sem logo continuam escondidos.
- [x] Lista de modelos que o dono mandou tirar (`UNWANTED` em `isAvail`): Celeris, MythoMax, Ising, LFM, Hermes, North, Riva, Cosmos, dots, Grok, Muse — somem em qualquer provedor. O Llama foi liberado de novo.
- [x] Gemma: o "26" do `diffusiongemma-26b` era o tamanho lido como versão ("Gemma 3, 4 e 26"); agora a família fica "Gemma 3 e 4".
- [x] FreeTheAI: modelo que está na lista mas responde 404 "was not found" (ex.: `gemini-4-argon`) é escondido por 12 h (`provider_follow.json`, como o erro de seguir provedor). Só aprende depois do primeiro erro.
- [~] Linhas do seletor numa linha só: nome da família com reticências (completo ao passar o mouse) e logos dos provedores sem quebrar de linha (antes o nome comprido virava uma coluna alta). Só conferido por sintaxe.
- [~] Seletor de modelos mais largo no PC (440 px; no celular continua a largura da tela).
- [~] Título da família com mais de 4 versões fica compacto: Mistral vira só "Mistral"; versões com letra e número (Kimi K2…K3, MiniMax M2…M3) viram faixa ("Kimi K2 – K3.1"). A lista completa continua em Parâmetros.
- [x] Erro "ConnectionAbortedError" no terminal quando a página fecha no meio de uma resposta: agora é ignorado em silêncio (`send_json`).
- [-] Modo offline: descartado pelo dono (besteira). Não fazer.

## 7. Provedores (todos só com modelos grátis, exceto Pollinations)

- [x] **Ollama** local + **Ollama Cloud** (gerenciador: baixar, atualizar, apagar, atualização automática semanal).
- [x] **Pollinations** (pago em pollen, ferramentas nativas só onde o catálogo permite, espera o `Retry-After`, saldo, menu do catálogo com saúde).
- [x] **OpenRouter** (só grátis) · **Cloudflare Workers AI** (10k neurônios/dia, contador) · **Groq** · **Vercel AI Gateway** · **LLM7** · **tomdacat**.
- [x] **FreeTheAI exige seguir o provedor de cada modelo** (freetheai.org/providers/NOME): o 403 "You don't follow X" vira mensagem em português com o link e o Lume esconde os modelos desse provedor por 12 h (`provider_follow.json`, aprende pelo erro, sem gastar pedidos). Ainda não portado para o iPhone (`lume-backend.js`).
- [x] Extras pelo registro `libs/providers.js`: **LiteRouter, AIHubMix, Paxsenix, FreeTheAI** (50 pedidos/dia, check-in no site), **VoidAI**, **TokenReply**. Adicionar um = um item no registro (guia `libs/PROVIDERS.md`).
- [x] Várias chaves + chaves de reserva; teste de saúde automático (modelo fora do ar some da lista); painel de provedores com cota diária.
- [x] Troca automática de modelo quando um falha (desligada por padrão) e "tentar o próximo mais barato".
- [x] Tempo limite 45 s / 60 s sem dados; erros de provedor aparecem com a mensagem real; modelos sem streaming vêm inteiros.
- [x] Modelos novos da comunidade: `community/Saauf/mistral-large-4` (chat e Code, 1M de contexto, visão) e `community/Saauf/laguna-xs-2.1` (Code). `community/Lorodn4x/ps5-beta` testado (parece Mistral; não foi adicionado à lista).
- [-] Removidos: Aichixia (fechou), modelos sem logo, Lume Auto do seletor (virou "Troca automática").

## 8. Aba Code (agente)

- [x] Ferramentas: `list_files`, `read_file`, `write_file`, `edit_file` (troca um trecho), `cmd`, `powershell`, `search_web`, `read_url`. Até 5 por passo; limite por mensagem configurável (1–200, padrão 25).
- [x] Gravar e rodar **sempre pedem permissão**; "Permitir sozinho" filtra comandos perigosos (filtro, não garantia).
- [x] Botão **Rodar/Parar** nos blocos de código (Python com pip automático, JS, PowerShell, BAT, Bash).
- [x] Cartões de chamada de ferramenta redesenhados (ícone, nome, alvo, resultado ligado com selo ✓/✕, prévia ao vivo, barra animada); bronca quando a IA inventa resultado.
- [x] **MCP**: Configurações > Code > Servidores MCP (formato do Claude Desktop); ferramentas `mcp__servidor__ferramenta`.
- [x] Terminal mostra a mensagem crua da IA e o raciocínio em tempo real (opção).

## 9. A IA usando o computador (Windows, desligado por padrão nas opções do Code/Chat)

- [x] `screenshot`, `mouse_move`, `mouse_click`, `scroll`, `type_text`, `press_key`, `list_windows`, `use_apps` (até 3 programas ao mesmo tempo, em segundo plano, **mouse virtual**: não usa o seu mouse), `launch_app`, `close_app`.
- [x] **`take_screenshot`** (Chat e Code): um print por app, título, `.exe`, PID ou `desktop`; a IA escolhe se a caixinha do Alt+Espaço aparece; **categorias** `browser`, `terminal`, `editor`, `explorer`, `chat` (até 3 prints); avisa no chat quando usa um alvo parecido; se pedir Chrome e só o **Comet** estiver aberto, o resultado manda chamá-lo de Comet.
- [~] `take_screenshot` com um modelo de verdade (só testado com resultados simulados).

## 10. IA no navegador (extensão)

- [x] Extensão MV3 em `browser-extension/` (Comet, Chrome, Edge, Brave, Firefox temporário). Instalar: `chrome://extensions` > modo do desenvolvedor > Carregar sem compactação > pasta `browser-extension`.
- [x] Ponte local: a extensão pareia só com Origin de extensão, faz long-poll (20 s) e devolve resultados; ferramentas só aparecem com a extensão conectada.
- [x] Ferramentas `mcp__browser__*`: `tabs`, `open_url`, `read_page` (texto + lista numerada), `click`, `type`, `scroll`, `read_current_page` (texto bruto ou **PDF**), `screenshot_current_page` (parte visível ou **página inteira**), `switch_tab`, `close_tab`, `back`. Senhas nunca aparecem.
- [x] PDF e página inteira usam a permissão opcional `debugger` (só Chromium; botão no popup da extensão; aparece um aviso amarelo "depurando" por segundos). Sem ela volta um aviso e a IA usa texto/parte visível.
- [x] Botão **Instalar no meu navegador** (Configurações > App): abre a página de extensões do navegador padrão + a pasta e mostra o passo a passo (instalação 100% automática não existe).
- [~] `read_current_page`/`screenshot_current_page`, o `debugger` e o botão de instalar: testados só pela ponte com extensão falsa e detecção do navegador padrão (neste PC o padrão do Windows aparece como **Firefox**); não rodaram num navegador de verdade.
- [x] Chat e Code usam; interruptor "IA no navegador" nas configurações (card com status e botão para abrir a pasta).
- [~] A extensão **rodando de verdade** no Comet/Firefox (APIs `chrome.*`, sono do service worker) ainda não foi testada.
- [x] Comet é de instância única: abrir com porta de depuração (CDP) não funciona; por isso a extensão.

## 11. Caixinha Alt+Espaço (Windows)

- [x] Janela pequena sem borda, sempre por cima, abre no monitor do mouse; digitar e mandar mostra a conversa logo abaixo; Alt+Espaço, Esc ou clicar fora esconde.
- [x] Fundos **Mica, Acrylic, Aero** ou sólido (segue o tema claro/escuro do Windows); botão com a logo do Lume leva tudo para um chat novo.
- [x] **Ctrl+Alt+Espaço**: pega o texto selecionado em qualquer app (copia com Ctrl+C e devolve a área de transferência) e mostra **Explicar · Traduzir · Resumir · Corrigir**; digitar uma instrução também vale. Nunca age em terminais (Ctrl+C interromperia o programa) nem se a área de transferência tem imagem/arquivo.
- [~] Mica no tema claro do Windows; Esc para esconder; resposta de modelo real na caixinha com o texto selecionado.

## 12. Jogos, arena e extras

- [x] Xadrez contra modelo ou Stockfish (nível 0–20): lances ilegais, ranking dos lances, PGN, premoves (até 10), editor de tabuleiro, 14 estilos de peça e 7 tabuleiros, lances seguidos, duelo (modelo × modelo × Stockfish) com explicação dos lances.
- [x] Jogos: velha, forca (8 erros, dicas), 20 perguntas, quiz, "eu adivinho".
- [x] **Comparar modelos / arena**: 2–3 modelos lado a lado, sorteio por critério, às cegas, votos viram o seu ranking, aba de velocidade.
- [x] **Lume Auto** (roteador por tipo de pedido) como troca automática; notas de inteligência pelo Gratisfy (`https://gratisfy.xyz/api/benchmarks`, guardadas 24 h em `model_scores.json`).

## 12b. Pet, companheiro e atualização sem sumir (v4.0)

- [x] **Pet na área de trabalho** (`pet.html` + `pet_loop` no `app.py`, Windows): arrastar, jogar, quicar nas bordas com gravidade e gelatina, clique = pulinho, segurado = olhos `> <`, olhos seguem o cursor, grudar na borda, tamanho 50–300% (padrão 200%), resetar posição, posição lembrada (`pet_pos`). Config: `pet_desktop` (padrão desligado), `pet_size`, `pet_snap`. Janela transparente (vidro do DWM + fundo preto), sem botão na barra de tarefas, sem roubar foco, região circular (cliques passam no resto).
- [~] Pet testado com um mouse simulado (jogada, 6 a 11 quicadas, chão e paredes certos); não testado: vários monitores, grudar na borda, o clique real em cima de outros programas.
- [x] Mascote mais parecido com o do Kimi (aro escuro translúcido, luz de baixo, olhos em cápsula, `mood-held` com `> <`, estilo LED).
- [x] **Companheiro** (`lumePet.openProfile`): dias com você, conversas, sequência, mapa de calor (data da criação de cada chat), crescimento por mensagens, "Crescer sozinho" = sugestões de memória.
- [x] **Lume Rápido**: transparência real (`quick_backcolor`: BackColor preto do formulário), animações, **troca de modelo** (lista = cache de modelos da nuvem do app + instalados; escolha em `localStorage.lume_quick_model`).
- [~] Terminal: rodando do `run.bat` o app novo herda o terminal (não usa `DETACHED_PROCESS`); no `.exe` fecha o terminal antigo (`set_terminal(False)`). Testado só o reinício; o terminal de verdade (Windows Terminal) não foi observado.
- [x] **Reiniciar sem sumir** (`restart_app`: `--handoff`, arquivos `lume-handoff-*` na pasta temporária; o app antigo só fecha com `os._exit` quando o novo mostra a janela, no mesmo lugar). No `.exe` com troca de arquivo (atualização baixada) a janela ainda fecha antes (o arquivo precisa estar livre), mas a nova abre no mesmo lugar.
- [x] Atualização do código: pergunta com **Atualizar agora / Deixar para depois** (20 s; o depois volta em 30 min). Emergência = Release com `[urgente]`/`[security]`: sem botões, reinicia sozinho quando a IA está parada.
- [x] Botão da extensão lista os navegadores instalados e instala no escolhido.

## 13. Interface, temas e configurações

- [x] Interface moderna (padrão) + clássica; 6 temas (DeepSeek, Roxo, Claude, Ollama, Gemini, Perplexity) que mudam fonte, cantos, layout e logo; editor de temas com gradiente e imagem de fundo; temas salvos em `custom themes`.
- [x] Fontes (interface e código), telas de carregamento por marca, escala, tela de boas-vindas, bandeja do sistema, iniciar com o Windows/terminal, aceleração de hardware (automática/ligada/desligada), overlay de desempenho.
- [x] Campos de número das configurações usam botões − e + (função `enhanceNumbers`), não as setinhas do navegador.
- [x] Configurações em cartões num mosaico; abas: Geral, Aparência, Code, Chaves de API, Servidor, App. Trocar de seção tem animação e não amontoa os cartões (também ao entrar/sair da interface clássica).
- [x] Atualização automática (`.py` mudou): mostra "Atualizando o Lume..." antes de fechar e "Lume atualizado ✓" na volta.
- [x] Celular: botões redondos, gaveta lateral, gestos (arrastar da borda abre as conversas).

## 14. Rede, contas e amigos

- [x] Acesso na rede de casa e de fora (Cloudflare Tunnel, Tailscale Funnel); senha separada para casa e internet; HTTPS local com CA própria.
- [x] Contas sem senha em pastas, exportar/importar (`.json`), importar o seu `config.json` (nunca importa senha, sessões, portas, acesso remoto).
- [x] Modo amigos (`/share`) com limites e painel do dono (`/dashboard`); link secreto `/owner-CODIGO`; perfil `.mobileconfig` para o iPhone.
- [x] Modelos no celular (WebLLM/WebGPU) com benchmark.

## 15. iPhone, Linux, instaladores, atualização

- [x] iPhone: a mesma interface com `lume-backend.js` (roda sem PC); atualiza sozinho pela branch `ios-live`; **não tem**: aba Code, rodar código, Cloudflare, túnel, atualizador, PDF/Word.
- [~] `created` (para "Novos") e o seletor em tela cheia no iPhone: só testados no PC.
- [x] Linux nativo (Qt, AppImage, instalador); **não há macOS** (Ventura/macOS foi recusado).
- [x] `Lume-Setup.exe` (Inno Setup, sem administrador), atualização automática do `.exe` por GitHub Releases; no código-fonte o Lume reinicia/recarrega sozinho quando `.py`/`.html`/`.js` mudam.
- [x] Testes automáticos no GitHub (`tests.yml`), feedback numa janela separada, app e servidor de feedback.

---

## 16. Não verificado (pendente de teste de verdade)

- [ ] Extensão do navegador dentro do Comet/Firefox (e se o Comet deixa "Carregar sem compactação").
- [ ] Card "IA no navegador" nas configurações (só checado por sintaxe).
- [ ] `take_screenshot` e as ferramentas do navegador com modelo real.
- [ ] Caixinha: Esc para esconder, Mica no tema claro, Ctrl+Alt+Espaço com um modelo real e em vários apps (Chrome, Word, VS Code).
- [ ] Seletor em tela cheia num celular de verdade e no iPhone.
- [ ] Pet na área de trabalho: vários monitores, grudar na borda, uso por horas (CPU da física a 60 quadros).
- [ ] Atualização de emergência (Release de verdade com `[urgente]`) e o reinício sem sumir no `.exe`.
- [ ] Seletor: ordenar por "Novos" usa `created` (só o Pollinations/iOS preenchem; modelos locais ficam por último).

## 17. Ideias e backlog

- [-] **Modo offline** (esmaecer/sumir modelos de nuvem sem internet): o dono disse que é besteira (2026-11-03). NÃO fazer.
- [ ] Ideias novas (2026-11-03, escolher): presets de personalidade por chat; "projetos" (pasta com instruções e arquivos fixos); pesquisa profunda (várias buscas + relatório com fontes); gerar imagem (Pollinations); resumir sozinho quando a barra de contexto enche; Ctrl+Shift+Espaço manda o print da janela da frente para a caixinha; botão "Substituir" na caixinha da seleção (cola o texto corrigido de volta no app); "perguntar sobre esta página" no popup da extensão; tarefas agendadas ("todo dia 8h resuma...").
- [ ] Resposta lado a lado no próprio chat (a arena já faz fora do chat).
- [ ] Backup/exportar tudo num arquivo (conversas + configurações) para outro PC/iPhone.
- [ ] Ações rápidas do navegador ("resumir esta aba" com um clique) depois que a extensão provar que funciona.
- [ ] Mais ações na caixinha da seleção (ex.: "responder isto", "reescrever mais curto").
- Já existem (não refazer): voz, memória, anexos de arquivo, pesquisa nos chats, mascote, comparar modelos.

## 18. Ranking dos modelos GPT (nota de inteligência do Artificial Analysis via Gratisfy; preço em pollen por 1M de tokens entrada/saída)

| # | Modelo | Nota | Preço | Tempo (p50) | Observação |
|---|---|---|---|---|---|
| 1 | GPT 6.1 Sol | 54,5 | 1,5 / 7,5 | 8,7 s | o mais forte, mas lento e caro |
| 2 | **GPT 6.1 Terra** | 51 | 0,75 / 3,75 | 2,0 s | **o melhor custo-benefício (recomendado)** |
| 3 | GPT 6 Luna | 27,8 | 0,075 / 0,375 | 4,3 s | barato, fraco |
| – | GPT 5.6 Sol / 5.6 Luna / 5.4 Mini / 5.4 Nano / 5 Nano / GPT-OSS 20B/120B / 6.1 Sol Quest | sem nota | (varia) | (varia) | o Gratisfy não tem nota; ordem abaixo é estimativa |

Estimativa para os sem nota: 5.6 Sol > 5.6 Luna ≈ 5.4 Mini > GPT-OSS 120B > 5.4 Nano > GPT-OSS 20B ≈ 5 Nano. A nota muda com o catálogo: rodar de novo `fetch_model_scores(refresh=True)`.
