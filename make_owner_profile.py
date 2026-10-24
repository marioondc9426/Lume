"""Gera o owner.mobileconfig (nesta pasta): um icone para a tela do iPhone que abre <link>/owner-<codigo> e ja entra como dono.

    python make_owner_profile.py [link]      sem argumento usa o endereco do Tailscale (https://PC.rede.ts.net)

O codigo vem do owner_code do config.json. O arquivo tem o seu codigo dentro: fica so nesta pasta (.gitignore) e nao vai para o GitHub."""
import os
import sys

sys.argv, argv = sys.argv[:1], sys.argv[1:]
import app

cfg = app.load_config()
code = cfg.get("owner_code") or ""
if not code: sys.exit("O config.json nao tem owner_code.")
link = (argv[0] if argv else "").rstrip("/")
if not link:
    ts = app.tailscale_status()
    if ts.get("name"): link = "https://" + ts["name"]
if not link: sys.exit("Passe o link do seu servidor: python make_owner_profile.py https://seu-endereco")
if not link.startswith(("http://", "https://")): link = "https://" + link
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "owner.mobileconfig")
with open(out, "wb") as f: f.write(app.build_ios_profile(f"{link}/owner-{code}", app.APP_NAME + " (dono)"))
print("Pronto:", out, "->", link + "/owner-<codigo>")
