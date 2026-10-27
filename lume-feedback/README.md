# lume-feedback

Servidor + dashboardzinho que recebe o que os usuários mandam pelo app **Lume Feedback** (`feedback-app/`).

## Rodar o servidor
```
python lume-feedback/server.py                 # http://0.0.0.0:8787  (dashboard em /dashboard)
python lume-feedback/server.py --port 9000 --host 127.0.0.1
```
Só usa a biblioteca padrão do Python. Os dados ficam em `feedback.db` (SQLite) na pasta do servidor (ou em `FEEDBACK_DATA`).

- **Senha do dashboard:** variável `FEEDBACK_PASSWORD`; se não tiver, o servidor gera uma na primeira vez, mostra no terminal e guarda em `feedback_password.txt`.
- **Chave de envio (opcional):** se `FEEDBACK_KEY` existir, o app precisa mandar o mesmo valor (campo `key` em `~/.lume-feedback.json`).
- Limites: 10 envios por hora por IP (mude com `--rate N`; `--rate 0` = sem limite), mensagem até 5000 caracteres, captura de tela PNG/JPEG até 1,5 MB, 5 senhas erradas = espera de 1 minuto.
- **Dashboard** (`/dashboard`): lista com busca e filtros por categoria e status, detalhe com a captura de tela, marcar novo/lido/resolvido, apagar e exportar CSV. O texto é sempre mostrado como texto (nada que o usuário escreva vira HTML).

## Onde hospedar
Em qualquer máquina que os usuários consigam alcançar (seu PC com a porta aberta, um VPS...). Por trás de HTTPS (Caddy, nginx, Cloudflare Tunnel), já que a senha do dashboard viaja pela rede. Para só **ver** o dashboard num servidor sem porta pública: `ssh -L 8787:localhost:8787 usuario@servidor` e abra http://localhost:8787/dashboard.

## O app que envia
`feedback-app/lume_feedback.py` (janela em tkinter; precisa só do Python, e do Pillow se quiser capturar a tela):
```
python feedback-app/lume_feedback.py --server http://IP:8787
python feedback-app/lume_feedback.py --server http://IP:8787 --message "texto" --category bug   # sem janela
```
Para distribuir já apontando para o seu servidor, ponha o endereço num arquivo `server.txt` ao lado do app. O app **nunca** lê o `config.json` nem as chaves do Lume.
