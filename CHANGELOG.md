# Versões

Como numerar:
- **1.1, 1.2, 1.3...** = versão nova, com novidades (sobe o número depois do ponto).
- **1.1.01, 1.1.02...** = correções (patches) da versão 1.1, sem novidades.
- O número fica em `VERSION` no topo do `app.py` e aparece em Configurações > Atualizações.
- Cada versão ganha uma tag no Git (`v1.0`, `v1.1.01`...).

## v3.0 (em desenvolvimento)
- Configurações: **mostrar a mensagem completa da IA no terminal** (raciocínio, resposta inteira, chamadas de ferramenta e resultados, sem cortar). A busca na web agora diz ao modelo (e na dica de "Fontes") com que texto pesquisou, para ele não inventar o motivo de resultados estranhos.
- **tomdacat** como provedor (Configurações > Chaves de API): só entram modelos de até 100 créditos por milhão de tokens e que o Lume ainda não tinha: GPT-5 Mini, MiMo V2.5, Mercury 2, Celeris 1, DiffusionGemma 4 26B e Nemotron 3 Nano Omni. O padrão continua sendo o mais barato; os do tomdacat ficam depois dos grátis.
- Planejado para a 3.0 (depois): redesenho completo da interface com um botão para voltar à interface original, e vários temas que mudam o layout e não só a cor.
- O tema "Kimi" (que é roxo) agora se chama **Roxo**. Todos os GLM 5.3 Flash (2 grátis, MarcosFRG e Saauf) e o GLM 4.6V nas duas abas; Qwen 3.8 Max (vendouple) com o oficial de reserva; grátis com 90%+ de sucesso continuam na frente dos pagos.
- **Groq** de volta, agora sem a biblioteca: Qwen 3.8 27B, GPT-OSS 120B e 20B (abas Chat e Code), com os limites do Groq (pedidos por dia e tokens por minuto) no painel e um aviso quando estão acabando; erro de limite explica o que estourou e quando renova. **Kimi** K2.6 e K3, GPT 6.1 Sol / 5.6 Sol e Qwen 3.8 Max mais baratos da comunidade (o oficial fica de reserva), MiniMax M3 oficial. Tirei o GPT 5.3 Codex. Em "Pollinations", o provedor mais barato vira o padrão mesmo se o catálogo o marcar como instável.
- Seletor de modelos: continua aberto ao mudar parâmetros/provedor; logos dos provedores no canto direito (Ollama com um "+" azul quando o modelo também roda no PC, OpenRouter, Pollinations, Cloudflare). Estatísticas: ordenar por respostas, tokens, média ou melhor tok/s, nos dois sentidos. DeepSeek V4 Flash barato (vendouple) como reserva dos grátis; provedores fora do ar vão para o fim da fila de reserva.
- **Esforço de raciocínio** (seletor de modelos, só nos modelos da Pollinations que aceitam): Automático / Nenhum / Baixo / Médio / Alto / Máximo. O Lume aprende sozinho quais níveis cada modelo aceita (pelo erro dele) e usa o mais próximo. Sem o botão Pensar o padrão é "nenhum" em todos os que aceitam (antes só nos GPT), o que corta a espera antes da 1ª palavra.
- **Pollinations**: lista completa de modelos (reliability=all), ferramentas nativas só nos modelos que têm a capacidade, espera o tempo do `Retry-After` quando o limite de pedidos estoura, latência típica (p50) no seletor de provedor, aviso de limite de pedidos por minuto, ⚠ também para provedores fora do ar. O status "Conectando ao Pollinations" virou "Esperando o Pollinations responder" (a conexão leva 0,03 s; a espera é o modelo).
- **Novos modelos (Pollinations)**: GLM 5.3 Flash (2 grátis + 1 pago de reserva) e GLM 4.6V Flash, Muse Glimmer 30B, Muse Spark 1.3 (⚠ registra as conversas), Laguna S 2.1 na aba Code; Llama 3.1 8B xTurbo ⚡⚡, MiniMax M3.1 Flash, DeepSeek V4 Flash 0731 e Gemini 3.1 Pro grátis (⚠) nas duas abas. Provedores com aviso mostram um triângulo ⚠ e um aviso ao escolher.

## v2.3
- **Permitir sozinho** (Configurações > pasta de trabalho): a IA roda comandos e grava arquivos sem o popup, mas comandos perigosos (diskpart, format, apagar pastas do sistema/usuário, registro, contas, serviços, desligar, baixar e executar código) são bloqueados de vez.

## v2.2
- **Aba Code**: o botão Rodar vira **Parar** enquanto o código roda (encerra o programa e os filhos); vários pedidos de ferramenta de uma vez (até 5, em ordem); chamada de ferramenta nativa nos modelos da Pollinations (os GPT Luna não seguiam o formato de texto); aviso automático quando o modelo diz "vou atualizar…" e não chama nada.
- **GPT**: todos os GPT de texto da Pollinations (5.4, 5.4 Mini, 5.5, 5.6 Sol/Terra, 6 Sol, 6.1 Sol, 6 Astra, GPT-OSS 20B/120B da comunidade) e os GPT da Pollinations/OpenRouter também na aba Code; sem o botão Pensar, os GPT 5/6 respondem bem mais rápido (raciocínio mínimo).
- **Correções**: erro "can only concatenate str" com Qwen Coder da Cloudflare; painel de VRAM/GPU e popup de permissão não dependem mais da inicialização terminar (e a tela diz em que passo ela falhou); lista de modelos não quebra a inicialização; modelos sem sufixo (gpt-5.5) não derrubam mais o carregamento da lista da Pollinations.

## v2.1
Tudo que for pedido até o "push tudo isso aí" entra aqui. Já está dentro: o `Lume.exe` (antes `Qwen.exe`) e a geração automática (v1.8.x), a tela de boas-vindas com a aba de configurações (v1.9) e:
- Animações: Configurações, Memória, Estatísticas, Exportar e as caixas de diálogo agora entram e saem com fade e deslize (e as abas internas das Configurações também). Respeitam "Animações" desligadas e a preferência de menos movimento do Windows.
- **Várias conversas ao mesmo tempo**: dá para trocar de chat enquanto a IA ainda responde e conversar em outro; cada chat tem a sua geração (o "parar" só para a do chat aberto). Na barra lateral um ponto azul pulsa nos chats respondendo e um verde marca os que terminaram enquanto você estava em outro.
- **Fila de mensagens**: se a IA está demorando, o que você enviar espera a vez (aparece pontilhado no fim do chat) e sai sozinho quando a resposta acabar. Dá para apagar uma mensagem da fila (lixeira) antes de a IA vê-la; se der erro, o texto volta para a caixa de digitação.
- **Pensar mais de uma vez**: na aba Code (e sempre que a IA usa ferramentas) cada rodada de raciocínio ganha o seu próprio bloco ("Pensamento 1", "Pensamento 2").
- **Editar, regenerar e ramificar**: lápis nas suas mensagens (edita e reenvia), ↻ nas respostas (tenta de novo com o mesmo modelo ou escolhe outro) e lixeira para apagar qualquer mensagem. A versão antiga não se perde: aparece um seletor ‹ 1/2 › que alterna entre as versões, cada uma com o resto da conversa que veio depois dela.
- **Anexos**: agora lê **Word (.docx), Excel (.xlsx), PowerPoint (.pptx) e LibreOffice (.odt/.ods/.odp)**, sem instalar nada. O tipo vem do conteúdo, não da extensão. Se o arquivo tem uma extensão que ninguém conhece (ex.: `.slaoq123`) mas por dentro é texto normal, PDF, imagem ou Office, o app pergunta se pode trocar a extensão (para `.txt`, `.pdf`, `.png`...) e anexar.
- **Gerenciador de modelos do Ollama** (Configurações): lista os modelos instalados com o tamanho, baixa qualquer modelo pelo nome com barra de progresso (e cancelar), atualiza e apaga. Modelos baixados que não estão na lista do app passam a aparecer no seletor sozinhos. A tela de boas-vindas baixa o primeiro modelo com um clique.
- **Atualizadores automáticos**: os modelos instalados podem se atualizar sozinhos (uma vez por semana, com o app aberto) e o app pode **baixar e instalar as próprias atualizações** em segundo plano, pedindo só a confirmação do reinício.
- **Tailscale Funnel**: botão em Configurações → Servidor que publica o app num endereço fixo `https://PC.rede.ts.net` (precisa do Tailscale conectado e do Funnel ligado na conta). Continua exigindo a senha pela internet, e o Funnel é desligado quando o app fecha.
- **Ícone na bandeja do sistema** (opção na tela de boas-vindas e em Configurações → Aplicativo): fechar a janela só a esconde; o ícone ao lado do relógio abre de novo ou sai. Com "iniciar com o Windows" o app abre já escondido na bandeja.
- **Memória que sugere**: quando você conta algo pessoal e duradouro (nome, profissão, preferência, projeto), a IA pode terminar a resposta com uma sugestão e aparece "💡 Lembrar? “…”" com os botões Lembrar e Não embaixo dela; Lembrar guarda na Memória Global. Dá para desligar na janela da Memória. Não vale na aba Code nem nos modelos do celular. Cada memória da lista tem um botão de lixeira para apagar.
- **Modelos e marcas**: entra o **Nemotron 3 Ultra** (nuvem); saem o DeepSeek V4.1 Flash e o clef do seletor. Cada modelo mostra a **logo da marca ao lado do nome** (Google para o Gemma, OpenAI para o GPT-OSS, NVIDIA para o Nemotron...); no Qwen, no DeepSeek e no Beam a própria imagem já traz o nome. A marca é detectada pelo nome do modelo, então modelos novos já saem com a logo certa; logos de uma cor só (OpenAI, Bonsai) acompanham a cor do tema. Para adicionar uma marca, ponha o arquivo em `icons/` e uma linha na lista `BRANDS` do `index.html`.
- Corrigido: quem entrava como root pelo iPhone não via o botão **Instalar app** (a tela de Servidor mostrava a parte do PC). Agora aparece, e o perfil usa o endereço que o iPhone abriu.
- **Perfil do dono para o iPhone**: `/downloadowner` baixa um `.mobileconfig` que põe na tela inicial um ícone que abre `<endereço>/owner-<código>` e já entra como dono (só responde na rede de casa/Tailscale e com o link secreto ligado, nunca por túnel público). `python make_owner_profile.py [link]` gera o mesmo arquivo na pasta do programa como `owner.mobileconfig` (ignorado pelo Git, porque tem o código dentro).
- **Seletor de modelos**: as famílias aparecem em ordem alfabética, primeiro as que têm modelo local e depois as só da nuvem; os logos do Qwen e do DeepSeek ficam sem o fundo branco e o do Beam acompanha a cor do tema; a etiqueta **visão** agora segue o que o Ollama informa de cada modelo instalado (aparece em todos que aceitam imagem).
- **OpenRouter (só modelos grátis)**: cole a chave em Configurações → Chaves de API e os modelos gratuitos do OpenRouter aparecem na lista (aba Chat), agrupados pela empresa e com logo da marca. A lista vem do catálogo do OpenRouter na hora (preço zero na entrada e na saída; só os que respondem texto). O servidor recusa qualquer modelo que não seja grátis, então não há como gastar saldo por engano. Respeita o limite do plano grátis (avisa quando o OpenRouter responde 429). Os amigos (`/share`) não usam essa chave.
- **Cloudflare Workers AI**: cole o token e o Account ID em Configurações → Chaves de API e os modelos de texto do Workers AI (Llama, Gemma, GPT-OSS, DeepSeek R1 distill, Qwen...) aparecem na lista, agrupados pela empresa. O plano gratuito dá 10.000 "neurônios" por dia e para quando acaba (o Lume avisa); só uma conta no plano pago pode ser cobrada além disso. Na primeira vez (e no botão "Reconferir quais modelos meu plano aceita") o Lume manda um pedido minúsculo a cada modelo e tira da lista os que o seu plano não aceita (os premium, como DeepSeek V4, Kimi e GLM 5, exigem o plano pago); se um modelo recusar na hora de usar, ele também sai da lista.
- **Contexto máximo dividido**: com "Usar o contexto máximo" ligado aparece "Dividir o limite de contexto para deixar mais usável", com uma lista (2, 3, 4, 6, 8, 16, 32) e uma caixa para digitar qualquer número ao mesmo tempo; mostra um exemplo (ex.: 256K ÷ 4 = 64K). Vale para a barra de contexto, a compactação e o espaço dos arquivos, e para o `num_ctx` dos modelos locais.
- Seletor: o Nemotron mostra "3, 4B / 3, 30B / 3, 120B / 4, 550B"; o Llama 3.2 saiu; os logos (DeepSeek, NVIDIA, Google, OpenAI, Beam) foram recortados sem a margem transparente, então aparecem maiores, e o DeepSeek e o Qwen ficam sem o fundo branco.
- Marcas novas na detecção de logos (Qwen genérico, Mistral, Z.ai/GLM, IBM, Cohere, Liquid, Poolside, Thinking Machines, OpenRouter): ponha o PNG com o nome exato em `icons/` e a logo aparece; sem o arquivo aparece só o nome. Ficam fora das listas do OpenRouter e do Cloudflare: Llama, MiniMax, Krea, Z.ai/GLM, os da própria Cloudflare, os de moderação, os LoRA e os pouco conhecidos ou fracos (a lista `MODEL_EXCLUDE` no `app.py`).
- **Monitor de neurônios do Cloudflare**: ao usar um modelo do Cloudflare aparece no topo do chat "☁ 135,6 / 10k" com uma barra (verde, amarela a partir de 70%, vermelha a partir de 90%); também na seção do Cloudflare em Configurações. Se o token tiver a permissão "Account Analytics: Read" o número vem direto da Cloudflare; sem ela o Lume estima (preço por milhão de tokens do catálogo, 1.000 neurônios = US$ 0,011, a mesma conta da Cloudflare) e dá para ajustar ao número do painel clicando no contador. Zera às 00:00 UTC.
- **Famílias por marca**: todas as versões e provedores de uma marca ficam numa linha só da lista de modelos ("Gemma 3 e 4", "Qwen 2.5, 3, 3.5, 3.8 e QwQ", "Nemotron 3, 3.5 e 4"), e a lista de parâmetros traz "versão, tamanho" ("3.5, 4B", "4, 26B · Cloudflare"), em ordem de versão e tamanho. Primeiro as marcas com modelo local, depois as só da nuvem, cada grupo em ordem alfabética. O `qwen2.5-coder-32b` do Cloudflare aparece só na aba Code.
- **Pollinations (modelos pagos em pollen)**: cole a chave em Configurações e aparece, no fim da lista de modelos, o grupo **Pagos** (GPT 5, 5.4, 5.6 e 6, Qwen 3.7 Flash e DeepSeek V4.1). O saldo de pollen aparece no topo do chat (🌸) com uma estimativa de quantas mensagens ainda dá para mandar. O **DeepSeek V4.1** tem uma lista de **provedores** (oficial e comunitários) com o preço por mensagem: o padrão é o mais barato que não é grátis, e se o provedor cair antes de responder o Lume tenta sozinho o próximo mais barato (os grátis ficam por último). A lista de modelos mostra no máximo 8 linhas de uma vez e rola.
- **Lista de modelos por cor e por provedor**: uma lista só, em ordem alfabética, com locais, nuvem e pagos misturados; a cor mostra o tipo (azul = local, cinza = nuvem grátis, amarelo = pago em pollen) na linha, nas bolinhas e nas opções. Cada modelo (versão + tamanho) tem um **seletor de provedor** quando existe em mais de um lugar (Ollama local ou nuvem, Cloudflare, OpenRouter, vários do Pollinations), com o do Pollinations em amarelo e o preço por mensagem. O padrão é o local, depois a nuvem grátis, e entre os do Pollinations o grátis saudável ou o pago mais barato. Se o provedor escolhido falhar antes de responder, o Lume **mostra o erro na mensagem e recomeça sozinho com o próximo mais barato do mesmo modelo** (instáveis ficam por último).
- Pollinations: entram o Llama 3.1 8B (⚡⚡), o Gemini 3.1 Flash Lite, os provedores do DeepSeek V4 e V4.1 (oficial, MarcosFRG, vendouple, scriptsnsenses-sys), o Qwen 3.8 27B grátis, e o Nemotron 3 Ultra, o Nemotron 3.5 Lightning e o Beam grátis. Cada resposta de modelo pago mostra quantos 🌸 pollen gastou (estimado pelos tokens).
- Cloudflare: com o token que tem "Account Analytics: Read" o contador de neurônios agora vem direto da Cloudflare.
- Ao crescer a caixa de digitação (nova linha), o chat continua no fim: o texto da IA sobe em vez de ficar escondido.
- Seletor de modelos: os dois menus de parâmetro e provedor agora são listas próprias do Lume (abrem dentro da linha, com as cores de cada tipo) em vez da lista do navegador. Entrou o Gemini 3.1 Pro grátis (`scriptsnsenses-sys`) e saiu o Llama 3.1 8B do Pollinations.
- **Tempo limite nos provedores da nuvem** (Pollinations, OpenRouter, Cloudflare): se o provedor não conectar em 45 s, ou ficar 60 s sem mandar nenhum dado (no começo ou no meio da resposta), o Lume corta a conexão, mostra o erro e, havendo outro provedor do mesmo modelo, recomeça com ele. Antes um provedor travado deixava o "Conectando..." para sempre. Enquanto espera, a mensagem mostra há quantos segundos ("Conectando ao Pollinations · 12 s"). Os tempos ficam em `CLOUD_*_TIMEOUT` no `app.py`.
- **Raciocínio em `<think>`**: modelos que escrevem o raciocínio dentro do texto, entre `<think>` e `</think>` (ou `<thinking>`), agora têm essa parte separada em tempo real e mostrada no bloco "Pensamento", em vez de aparecer na resposta. Funciona com qualquer provedor (Ollama, OpenRouter, Cloudflare, Pollinations), mesmo com a tag cortada entre dois pedaços. Se o modelo só mandar o `</think>` (abriu o raciocínio no próprio prompt), o que veio antes dele vai para o bloco de pensamento quando a resposta termina.
- **Velocidade (tokens/s) enquanto a resposta chega**: a estimativa agora só começa no primeiro token (a espera da conexão e do prompt não conta mais) e olha só os últimos ~2 s, então acompanha a velocidade de verdade em vez de uma média arrastada pela espera (uma IA a 600 t/s aparecia como 13 t/s). Cada pedaço conta no mínimo 1 token e o raciocínio também entra na conta. Quando a resposta termina continua valendo o número real medido.
- **Fim dos engasgos durante a resposta**: o texto era redesenhado inteiro (markdown, código, fórmulas) a cada token, e o painel de desempenho fazia 20 pedidos por segundo. Agora o texto é redesenhado no máximo ~14 vezes por segundo, o painel é atualizado ~6 vezes por segundo e a leitura da GPU não passa de 4 por segundo (2 durante uma resposta). Medido com uma resposta simulada de ~500 tokens/s: o maior travamento caiu de **1,4 s para 27 ms**. O contador de segundos da espera não pisca mais.
- **Velocidade (t/s) mais fiel**: a estimativa conta 1 token por pedaço curto (o Ollama local manda 1 por vez) e ~4 caracteres por token nos pedaços grandes (a nuvem junta uns 4). O número "real" dos provedores da nuvem (OpenRouter, Cloudflare, Pollinations) agora começa a contar no primeiro token de qualquer tipo, inclusive o raciocínio (antes só contava a resposta e dava 700 ou 3000 t/s falsos). A nuvem do Ollama não informa o tempo de geração: o Lume mede pelo relógio, do primeiro ao último token.
- Provedores que seguram a resposta e soltam tudo de uma vez (o Pollinations faz isso: o 1o dado chega só no fim) davam velocidades absurdas como 7.000 t/s; nesses casos (ou se o resultado passar de 2.500 t/s) o Lume usa o tempo total do pedido. O intervalo entre os desenhos do texto cresce junto com o texto (respostas muito longas não travam mais); o botão de regenerar deixou de aparecer preto no tema escuro.
- O seletor de provedor aparece sempre, mesmo com um provedor só. Cloudflare: o limite de resposta passa de 256 para 8192 tokens (modelos que pensam, como o R1, acabavam sem resposta); respostas cortadas pelo limite avisam, e "só pensou e parou" tem mensagem própria.
- **Novo nome: Lume**, com logo própria (um hexágono aberto em catavento com o centro aceso, degradê âmbar → rosa → violeta, inspirada na forma da logo do Qwen) e a palavra "Lume". O app deixa de usar o nome e a marca do modelo Qwen, que continua na lista de modelos. Trocou: `Lume.exe`, a pasta de dados `%LOCALAPPDATA%\Lume` (a pasta `Qwen` antiga é renomeada sozinha, então conversas e configurações vêm junto), o log `lume.log` e as variáveis `LUME_DATA_DIR`, `LUME_PORT` e `LUME_CONSOLE` (as `QWEN_*` ainda funcionam). "Iniciar com o Windows" troca a entrada antiga `Qwen` pela `Lume` ao ser ligado de novo.
- **Ícones**: o ícone do app (janela, `.exe`, bandeja) tem fundo transparente; o do celular e da aba do navegador usa a marca branca sobre um gradiente "líquido" distorcido; a tela de boas-vindas ganhou um gradiente animado que muda de forma. Tudo é gerado por `python make_icons.py`, que desenha a logo do zero.

## v1.9
- A tela de boas-vindas ganhou a aba **Configurações**, com as opções mais usadas valendo na hora: idioma, tema, **iniciar com o terminal**, **iniciar com o Windows**, pesquisa na web, atualizações, animações, painel de desempenho e acesso pela rede.
- **Iniciar com o terminal** (só no `Qwen.exe`): abre uma janela de terminal que acompanha o log ao vivo, como o `run.bat`. É uma janela à parte: fechá-la não fecha o app.
- **Iniciar com o Windows** (só no `Qwen.exe`): grava na chave `Run` do seu usuário, sem precisar de administrador.
- Corrigido: o botão de avisar sobre atualizações em Configurações não guardava a escolha.

## v1.8.02
- `config.json` e os outros arquivos de dados abrem mesmo se foram salvos com BOM (acontece ao editar no Bloco de Notas ou no PowerShell).

## v1.8.01
- O `.exe` sempre grava o log em `qwen.log` (antes dependia de como o programa era aberto).

## v1.8
- **Qwen.exe**: o app vira um programa único (`python build_exe.py` gera `dist/Qwen.exe`, com o ícone do Qwen e a versão do app). Os dados ficam em `%LOCALAPPDATA%\Qwen` e o log em `qwen.log`. O `.exe` usa o Python do PC só para os blocos de código.
- O `.exe` é gerado sozinho a cada commit (gancho do Git em `.githooks`, ative com `setup-hooks.bat`) e no GitHub (Actions: em tags `v*` o `.exe` vai para uma Release, de onde o app se atualiza).
- Tela de **boas-vindas** na primeira vez: o idioma vem do Windows (português ou inglês; qualquer outro idioma cai no inglês), com a checagem do Ollama, dos modelos e da placa de vídeo.

## v1.7.03
- Logo do topo da barra lateral sem fundo branco: a estrela roxa e o texto "Qwen" (que acompanha o tema: branco nos escuros, preto no claro) são imagens transparentes separadas.

## v1.7.02
- Pela internet, `/api/ping` não entrega mais o nome do PC e `/api/auth/status` mostra a regra de senha da internet (não a da rede de casa).

## v1.7.01
- Botão "Baixar cloudflared (sem administrador)": baixa o programa do túnel para a pasta `tools` do app e confere a assinatura digital da Cloudflare. Não precisa de admin (o `winget` precisava).

## v1.7
- Dois botões de senha independentes: **rede de casa** e **internet (túnel)**. Ligar de novo uma senha que estava desligada desconecta todos os aparelhos na hora.
- **Link secreto `/owner-CODIGO`** (desligado por padrão): abre uma sessão "root", com os mesmos poderes da janela do `run.bat` no PC (configurações, chaves, aba Code, rodar código, painel), de qualquer aparelho. O código pode ser escolhido ou gerado aleatório; trocar o código ou desligar derruba as sessões root na hora. Tentativas erradas bloqueiam o IP.

## v1.6
- Nome do app agora é **Qwen**, com o logo do Seeklogo no topo da barra lateral.
- **Modo amigos** (`/share`): cada amigo cria uma conta só com um nome de usuário; as conversas e memórias ficam separadas por conta. Entram só no Chat (sem aba Code, sem configurações, sem rodar código).
- **Painel do dono** (`/dashboard`): uso de cada amigo (respostas, tokens, modelos usados), liga/desliga cada um ou todos (com aviso e contagem, ou na hora), bloqueio de recursos e de modelos, limite de respostas por dia/minuto, código de convite, fechar cadastros e código de acesso para o amigo entrar em outro aparelho.
- Amigos usam sempre o DuckDuckGo na pesquisa (nunca o Exa), têm limite de contexto e de tamanho de resposta, e o uso deles entra na conta do Ollama.
- **Acesso de fora de casa**: túnel do Cloudflare com um clique (ou Tailscale Funnel). Pela internet a senha é sempre obrigatória, e configurações, comandos e a aba Code continuam só no PC. Limite de tentativas de senha por IP e geral.

## v1.5.01
- A porta 8000 passa a aceitar também HTTPS: se o navegador trocar `http://ip:8000` por `https://ip:8000` sozinho, a página abre em vez de dar "conexão segura".

## v1.5
- Botão ▶ Rodar nos blocos de código (Python, JavaScript/Node, PowerShell, Batch, Bash). Python detecta as bibliotecas que faltam pelo `import`, pergunta e instala com pip numa pasta do app (`code_packages`); programas com janela (tkinter, pygame...) abrem soltos.
- Estatísticas: seção do Ollama com o uso da nuvem nas últimas 5 h e 7 dias (respostas e tempo de GPU) e por modelo.
- Maximizar a janela não cobre mais a barra de tarefas e agora tem animação.

## v1.4
- Botão "Apagar os modelos baixados" na seção do celular, com o espaço usado pelo site.

## v1.3.01
- Benchmark do celular mede a memória até 3 GB (antes parava em 1,6 GB e não achava o limite de aparelhos mais fortes).

## v1.3
- HTTPS local: o servidor abre também em `https://IP:8443` com uma autoridade (CA) própria, que só vale para redes locais. O perfil da CA é baixado pelo celular em Configurações > Servidor.
- Modelos rodando no celular (WebLLM + WebGPU): lista de modelos pequenos, download na primeira vez, chat sem passar pelo PC.
- Benchmark do celular: mede a memória e a velocidade da placa gráfica e deixa em cinza (sem clique) os modelos que não vão rodar.
- Requer o pacote `cryptography` (já está no requirements.txt). Modelos da nuvem continuam passando pelo PC.

## v1.2.01
- Corrigido o ícone do botão "+" (o arquivo era PNG com nome .svg e não carregava; agora é `icons/plus.png`).
- Avisos ficam menos tempo na tela e somem com fade; clicar num aviso fecha.

## v1.2
- Markdown completo nas respostas: títulos (#, ##, ###), linhas ---, citações, tabelas, itálico, riscado, links e `código`.
- LaTeX vira Unicode ($ightarrow$, $\sum$, $x^2$, frações, raiz, letras gregas...) e emojis em `:nome:` (:fire:); a IA é instruída a usar esse formato.
- A rolagem não é mais puxada para baixo enquanto a resposta chega (botão ↓ para voltar ao fim).
- Fontes da pesquisa mostram só os logos dos sites, com "Mostrar mais" para abrir os cartões.
- Botão de copiar também nas mensagens do usuário, e outro para copiar pergunta + resposta.

## v1.1
- Aviso fixo no topo quando a versão em uso está desatualizada (com botão Atualizar agora e Depois). Checa ao abrir o app e a cada 6 horas.

## v1.0
Primeira versão numerada.
- Chat local com Ollama e modelos da nuvem do Ollama (GPT-OSS, Gemma 4, Beam, Nemotron 3, DeepSeek), busca na web com Exa, aba Code com agente.
- Anexar arquivos e imagens, fontes clicáveis, histórico com busca/fixados/pastas, estatísticas de uso.
- Blocos de código com cores, etiqueta do modelo com velocidade, contexto máximo, logos dos modelos.
- Servidor na rede com senha opcional, busca de servidores por perto, sistema de atualizações pelo GitHub.
