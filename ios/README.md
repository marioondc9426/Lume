# Lume no iPhone

O app do iPhone é o mesmo `index.html` dentro de um `WKWebView`. As chamadas `/api/...` não vão para um servidor: o `lume-backend.js` (porte do `app.py` para JavaScript) responde dentro da própria página.

| Você quer | Como funciona |
|---|---|
| Rodar sem PC ligado | O backend está dentro do app. Conversas, chaves e temas ficam no aparelho (IndexedDB). |
| Modelos da nuvem | Pollinations, OpenRouter, Groq, Vercel, LLM7 e tomdacat, com chaves de reserva e o mesmo teto de preço. |
| Modelos locais | Em Configurações > "Ollama no PC", coloque `http://IP-DO-PC:11434` (o Ollama do PC precisa de `OLLAMA_HOST=0.0.0.0`). |

Não existe no iPhone: aba Code com ferramentas, rodar código, Cloudflare Workers AI, túnel/compartilhar, atualizador e leitura de PDF/Word.

## Gerar o .ipa sem assinatura

Precisa de um Mac (o GitHub empresta um): Actions > "iOS (IPA sem assinatura)" > Run workflow. O arquivo `Lume-unsigned.ipa` sai em "Artifacts". Depois assine com o seu certificado (Sideloadly, AltStore, ou `zsign`/Xcode com o seu perfil) e instale.

Local (num Mac): `python ios/build_www.py && cd ios && xcodegen generate && open Lume.xcodeproj`.

`ios/backend-data.js` é gerado do `app.py` (`python ios/gen_data.py`): rode de novo quando mudar a lista de modelos.
