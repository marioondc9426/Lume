# Versões

Como numerar:
- **1.1, 1.2, 1.3...** = versão nova, com novidades (sobe o número depois do ponto).
- **1.1.01, 1.1.02...** = correções (patches) da versão 1.1, sem novidades.
- O número fica em `VERSION` no topo do `app.py` e aparece em Configurações > Atualizações.
- Cada versão ganha uma tag no Git (`v1.0`, `v1.1.01`...).

## v2.0 (em desenvolvimento, ainda não enviado ao GitHub)
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
