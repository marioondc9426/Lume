"""Gera o Lume.exe (PyInstaller): dist/Lume.exe, com o icone do Lume e a versao do app.

    python build_exe.py               gera e espera terminar
    python build_exe.py --background  gera por tras, sem travar o terminal (usado pelo hook do git); o log fica em build/build.log

Se chegar outro pedido enquanto uma geracao esta rodando, ele so marca "de novo" e a geracao em andamento
repete uma vez no final (assim varios commits seguidos nao empilham geracoes)."""
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(ROOT, "build")
DIST = os.path.join(ROOT, "dist")
LOCK = os.path.join(BUILD, ".lock")
AGAIN = os.path.join(BUILD, ".again")
LOG = os.path.join(BUILD, "build.log")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DATA = ["index.html", "share.html", "dashboard.html", "CHANGELOG.md", "icons"]   # o que vai dentro do .exe (pasta de destino: a raiz)


def say(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)


def app_version():
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as f:
        m = re.search(r'^VERSION = "([^"]+)"', f.read(), re.M)
    return m.group(1) if m else "0.0"


def ensure(modules):
    """Instala o que falta (pyinstaller e pillow so servem para gerar o .exe)."""
    for mod, pkg in modules:
        try: __import__(mod)
        except ImportError:
            say(f"Instalando {pkg}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])


def make_icon():
    """icons/lume.png -> build/lume.ico com varios tamanhos (o Windows escolhe o melhor em cada lugar)."""
    from PIL import Image
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, "lume.ico")
    src = Image.open(os.path.join(ROOT, "icons", "lume.png")).convert("RGBA")
    src.save(out, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return out


def version_file(version):
    """Recurso de versao do Windows (Detalhes > Propriedades do .exe)."""
    nums = ([int(x) for x in re.findall(r"\d+", version)] + [0, 0, 0, 0])[:4]
    tup = ", ".join(map(str, nums))
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Lume'), StringStruct('FileDescription', 'Lume - chat de IA local'),
      StringStruct('FileVersion', '{version}'), StringStruct('InternalName', 'Lume'),
      StringStruct('OriginalFilename', 'Lume.exe'), StringStruct('ProductName', 'Lume'), StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path = os.path.join(BUILD, "version_info.txt")
    with open(path, "w", encoding="utf-8") as f: f.write(text)
    return path


def build():
    ensure([("PyInstaller", "pyinstaller"), ("PIL", "pillow"), ("pystray", "pystray")])
    version = app_version(); ico = make_icon(); vfile = version_file(version)
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed", "--name", "Lume",
           "--icon", ico, "--version-file", vfile, "--distpath", DIST, "--workpath", os.path.join(BUILD, "work"), "--specpath", BUILD,
           "--collect-all", "webview", "--hidden-import", "clr", "--hidden-import", "clr_loader", "--hidden-import", "tls", "--hidden-import", "guests", "--hidden-import", "pystray._win32",
           "--exclude-module", "tkinter", "--exclude-module", "matplotlib", "--exclude-module", "numpy"]
    for item in DATA:
        src = os.path.join(ROOT, item)
        if os.path.exists(src): cmd += ["--add-data", f"{src}{os.pathsep}{item if os.path.isdir(src) else '.'}"]
    cmd.append(os.path.join(ROOT, "app.py"))
    say(f"Gerando Lume.exe v{version}...")
    t0 = time.time()
    with open(os.path.join(BUILD, "pyinstaller.log"), "w", encoding="utf-8") as lf:   # a saida do PyInstaller fica aqui (ajuda a achar o motivo quando falha)
        r = subprocess.run(cmd, cwd=ROOT, creationflags=NOWIN, stdout=lf, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        with open(os.path.join(BUILD, "pyinstaller.log"), encoding="utf-8", errors="replace") as lf: say("Fim do log do PyInstaller:\n" + "".join(lf.readlines()[-15:]))
    exe = os.path.join(DIST, "Lume.exe")
    if r.returncode != 0 or not os.path.exists(exe):
        say(f"FALHOU (codigo {r.returncode})"); return False
    say(f"Pronto: {exe} ({os.path.getsize(exe) / 1048576:.1f} MB) em {time.time() - t0:.0f} s")
    return True


def pid_alive(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, creationflags=NOWIN).stdout
        return str(pid) in out
    except Exception:
        return False


def worker():
    os.makedirs(BUILD, exist_ok=True)
    if os.path.exists(LOCK):
        try: other = int(open(LOCK).read().strip())
        except (ValueError, OSError): other = 0
        if other and pid_alive(other):   # ja tem uma geracao rodando: ela repete no final
            open(AGAIN, "w").close(); say("Ja ha uma geracao em andamento; vai repetir quando ela terminar."); return 0
    with open(LOCK, "w") as f: f.write(str(os.getpid()))
    try:
        while True:
            if os.path.exists(AGAIN): os.remove(AGAIN)
            ok = build()
            if not os.path.exists(AGAIN): return 0 if ok else 1
            say("Houve novos commits durante a geracao: gerando de novo.")
    finally:
        try: os.remove(LOCK)
        except OSError: pass


def main():
    if "--background" in sys.argv:
        os.makedirs(BUILD, exist_ok=True)
        log = open(LOG, "a", encoding="utf-8")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | NOWIN
        subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags)
        return 0
    return worker()


if __name__ == "__main__":
    sys.exit(main())
