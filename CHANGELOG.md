# Versões

Como numerar:
- **1.1, 1.2, 1.3...** = versão nova, com novidades (sobe o número depois do ponto).
- **1.1.01, 1.1.02...** = correções (patches) da versão 1.1, sem novidades.
- O número fica em `VERSION` no topo do `app.py` e aparece em Configurações > Atualizações.
- Cada versão ganha uma tag no Git (`v1.0`, `v1.1.01`...).

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
