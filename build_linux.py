"""Gera o Lume para Linux (PyInstaller, janela Qt): dist/Lume-linux.

    python build_linux.py            versao normal
    python build_linux.py --owner    versao so para o dono: nunca abre a porta para a rede (sem acesso remoto, amigos nem tunel)

Rode no Linux (o GitHub Actions faz isso em .github/workflows/linux.yml). Precisa de: pip install -r requirements.txt "pywebview[qt]" pyinstaller"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
DATA = ["index.html", "share.html", "dashboard.html", "CHANGELOG.md", "CHANGELOG-EN.md", "icons", "fonts", "libs"] + (["sounds"] if os.path.isdir(os.path.join(ROOT, "sounds")) else [])


def main():
    owner = "--owner" in sys.argv
    name = "Lume-linux-owner" if owner else "Lume-linux"
    os.makedirs(BUILD, exist_ok=True)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", name,
           "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
           "--collect-all", "webview", "--hidden-import", "webview.platforms.qt", "--hidden-import", "qtpy", "--hidden-import", "tls", "--hidden-import", "guests",
           "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "numpy"]
    for item in DATA:
        src = os.path.join(ROOT, item)
        if os.path.exists(src): cmd += ["--add-data", f"{src}{os.pathsep}{item if os.path.isdir(src) else '.'}"]
    if owner:
        flag = os.path.join(BUILD, "owner_only.flag")
        open(flag, "w").write("so o dono: sem acesso pela rede\n")
        cmd += ["--add-data", f"{flag}{os.pathsep}."]
    cmd.append(os.path.join(ROOT, "app.py"))
    print("Gerando", name, "...", flush=True)
    r = subprocess.run(cmd, cwd=ROOT)
    out = os.path.join(DIST, name)
    if r.returncode != 0 or not os.path.exists(out):
        print("FALHOU", r.returncode); return 1
    print(f"Pronto: {out} ({os.path.getsize(out) / 1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
