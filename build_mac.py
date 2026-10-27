"""Gera o Lume para macOS (PyInstaller, janela nativa WKWebView): dist/Lume.app e dist/Lume-macos-intel.zip.

    python build_mac.py

Rode no Mac (o GitHub Actions faz isso em .github/workflows/macos.yml, num Mac Intel; o app roda tambem nos Macs Apple Silicon pelo Rosetta).
Precisa de: pip install -r requirements.txt pyinstaller pillow. O app nao e assinado pela Apple: na primeira vez, botao direito > Abrir."""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
DATA = ["index.html", "share.html", "dashboard.html", "CHANGELOG.md", "CHANGELOG-EN.md", "icons", "fonts", "libs"] + (["sounds"] if os.path.isdir(os.path.join(ROOT, "sounds")) else [])


def version():
    m = re.search(r'^VERSION = "([^"]+)"', open(os.path.join(ROOT, "app.py"), encoding="utf-8").read(), re.M)
    return m.group(1) if m else "0.0"


def icns():
    """icons/lume.png -> build/lume.icns (Pillow grava .icns)."""
    from PIL import Image
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, "lume.icns")
    Image.open(os.path.join(ROOT, "icons", "lume.png")).convert("RGBA").resize((512, 512)).save(out, format="ICNS")
    return out


def main():
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "Lume", "--icon", icns(),
           "--osx-bundle-identifier", "app.lume.chat", "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
           "--collect-all", "webview", "--hidden-import", "tls", "--hidden-import", "guests",
           "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "numpy"]
    for item in DATA:
        src = os.path.join(ROOT, item)
        if os.path.exists(src): cmd += ["--add-data", f"{src}{os.pathsep}{item if os.path.isdir(src) else '.'}"]
    cmd.append(os.path.join(ROOT, "app.py"))
    print(f"Gerando Lume.app v{version()} ...", flush=True)
    if subprocess.run(cmd, cwd=ROOT).returncode != 0: print("FALHOU"); return 1
    app = os.path.join(DIST, "Lume.app")
    if not os.path.isdir(app): print("Lume.app nao foi criado"); return 1
    zp = os.path.join(DIST, "Lume-macos-intel.zip")
    subprocess.check_call(["ditto", "-c", "-k", "--keepParent", app, zp])   # zip que preserva o pacote do app
    print(f"Pronto: {zp} ({os.path.getsize(zp) / 1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
