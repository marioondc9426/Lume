# Versões

Como numerar:
- **1.1, 1.2, 1.3...** = versão nova, com novidades (sobe o número depois do ponto).
- **1.1.01, 1.1.02...** = correções (patches) da versão 1.1, sem novidades.
- O número fica em `VERSION` no topo do `app.py` e aparece em Configurações > Atualizações.
- Cada versão ganha uma tag no Git (`v1.0`, `v1.1.01`...).

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
