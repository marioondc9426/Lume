import http.server
import socketserver
import threading
import json
import urllib.request
import urllib.error
import urllib.parse
import re
import time
import subprocess
import os
import sys
import atexit
import base64
import html as html_mod
import io
import difflib
import ipaddress
import webbrowser
import copy
import hmac
import secrets
import socket
import ssl
import importlib
import importlib.util
import ctypes
import ast
import shutil
from ctypes import wintypes
import struct
import uuid
import zlib
import plistlib
import functools
import webview
import concurrent.futures

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

PORT = 8000
OLLAMA_URL = "http://127.0.0.1:11434"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
try: import tls   # HTTPS local (precisa do pacote "cryptography")
except Exception: tls = None
CERTS_DIR = os.path.join(BASE_DIR, "certs")
HTTPS_PORT = 8443
APP_NAME = "Qwen"
import guests as guests_mod   # contas de amigos (/share) e painel (/dashboard)
guests = guests_mod.Guests(os.path.join(BASE_DIR, "guests.json"), os.path.join(BASE_DIR, "guest_data"))
stop_events = {}        # id do amigo -> Event (parar so a geracao dele)
guest_active = {}       # id do amigo -> geracoes em andamento
guest_recent = {}       # id do amigo -> horarios das ultimas respostas (limite por minuto)
guest_lock = threading.Lock()
login_recent_fails = []  # horarios das senhas erradas de qualquer IP (trava global contra tentativas pela internet)
# Versao: "1.2" = versao nova com novidades (o numero depois do ponto sobe); "1.2.01", "1.2.02"... = correcoes (patches) dessa versao.
VERSION = "1.7.03"
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")     # chaves de API, pasta de trabalho, uso
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")   # chats
STATE_FILE = os.path.join(BASE_DIR, "state.json")       # preferencias da interface + memorias
STATS_FILE = os.path.join(BASE_DIR, "stats.json")       # uso: tokens/s por modelo, gasto do Exa
UNDO_DIR = os.path.join(BASE_DIR, "undo")               # copias dos arquivos que a IA sobrescreveu (botao Desfazer)
MAX_BODY_BYTES = 60 * 1024 * 1024   # tamanho maximo de uma requisicao (anexos)
MAX_FILE_CHARS = 60000              # texto maximo extraido de um arquivo anexado
THEMES_DIR = os.path.join(BASE_DIR, "custom themes")    # temas criados no editor de temas
MAX_AGENT_STEPS = 8        # limite de chamadas de ferramenta por mensagem
MAX_TOOL_OUTPUT = 8000     # caracteres devolvidos a IA por ferramenta
TOOL_TIMEOUT = 60          # segundos para cmd/powershell
MIN_WEB_QUERY = 5         # mensagens menores que isso ("oi") nao disparam pesquisa na web
MONITOR_EVERY_S = 2.5     # de quanto em quanto tempo a memoria da GPU e conferida
VRAM_ALERT_EVERY_S = 2.5 # a cada quantos segundos o aviso de VRAM alta (terminal) se repete
VRAM_WARN_MB = 7144        # aviso de VRAM alta (7 GB)
ollama_process = None
pending_command = {"cmd": "", "resolve": None}
stop_generation_flag = threading.Event()
generation_active = False  # True enquanto uma geracao esta em andamento (streaming)
active_model = ""          # modelo da geracao em andamento
model_usage = {}           # modelo -> {"last_used": ts, "uses": n, "chars": n}
started_at = time.time()

COLOR_RESET = "\033[0m"; COLOR_GREEN = "\033[92m"; COLOR_YELLOW = "\033[93m"; COLOR_RED = "\033[91m"; COLOR_BLUE = "\033[94m"; COLOR_CYAN = "\033[96m"; COLOR_GRAY = "\033[90m"
if os.name == 'nt':
    os.system("")  # habilita cores ANSI no terminal do Windows

def log(tag, msg, color=COLOR_RESET):
    print(f"{COLOR_GRAY}{time.strftime('%H:%M:%S')}{COLOR_RESET} {color}[{tag}]{COLOR_RESET} {msg}", flush=True)

# ---------------------------------------------------------------- GPU
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
GPU_QUERY = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader,nounits"]
gpu_sample = {"used": None, "total": None, "util": None, "ts": 0.0}
gpu_proc = None
gpu_lock = threading.Lock()
gpu_interval_ms = 50

def parse_gpu_line(line):
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 3:
        return int(parts[0]), int(parts[1]), int(parts[2])
    return None

def _gpu_reader(proc):
    for line in proc.stdout:
        try:
            vals = parse_gpu_line(line)
            if vals: gpu_sample.update(used=vals[0], total=vals[1], util=vals[2], ts=time.time())
        except ValueError:
            pass

def stop_gpu_stream():
    global gpu_proc
    with gpu_lock:
        if gpu_proc:
            try: gpu_proc.terminate()
            except Exception: pass
            gpu_proc = None

def start_gpu_stream(ms):
    """Mantem UM nvidia-smi aberto lendo a cada `ms` ms (bem mais rapido do que abrir um processo por leitura)."""
    global gpu_proc, gpu_interval_ms
    stop_gpu_stream()
    with gpu_lock:
        gpu_interval_ms = ms
        try:
            gpu_proc = subprocess.Popen(GPU_QUERY + ["-lms", str(ms)], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, creationflags=NO_WINDOW)
        except FileNotFoundError:
            log("GPU", "nvidia-smi nao encontrado: sem metricas de GPU.", COLOR_YELLOW)
            return False
        threading.Thread(target=_gpu_reader, args=(gpu_proc,), daemon=True).start()
    log("GPU", f"Leitura de GPU a cada {ms} ms", COLOR_BLUE)
    return True

def get_gpu_metrics():
    """Retorna (vram_used_mb, vram_total_mb, gpu_util_pct) ou (None, None, None) se indisponivel."""
    if gpu_proc and time.time() - gpu_sample["ts"] < 3 and gpu_sample["used"] is not None:
        return gpu_sample["used"], gpu_sample["total"], gpu_sample["util"]
    try:
        out = subprocess.check_output(GPU_QUERY, stderr=subprocess.DEVNULL, timeout=3, creationflags=NO_WINDOW).decode().strip()
        vals = parse_gpu_line(out.splitlines()[0]) if out else None
        if vals: return vals
    except Exception:
        pass
    return None, None, None

# ---------------------------------------------------------------- arquivos de dados
def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception:
        return default

def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)

_cfg_cache = {"mtime": None, "data": None}

def load_config():
    """Le o config.json (com cache pelo horario de modificacao: o app consulta isso a cada requisicao)."""
    try:
        mtime = os.path.getmtime(CONFIG_FILE)
        if _cfg_cache["mtime"] == mtime and _cfg_cache["data"] is not None:
            return copy.deepcopy(_cfg_cache["data"])
    except OSError:
        mtime = None
    cfg = {}
    if mtime is not None:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: cfg = json.load(f)
        except Exception as e:
            log("CONFIG", f"config.json invalido ({e}). Usando padrao.", COLOR_RED)
    else:
        log("CONFIG", "Criando config padrao", COLOR_YELLOW)
    cfg.setdefault("groq_api_key", "")
    cfg.setdefault("workdir", "")
    cfg.setdefault("usage", {}).setdefault("groq", 0)
    cfg.setdefault("remote_enabled", True)       # aceitar conexoes de outros aparelhos da rede (ligado por padrao; exige senha)
    cfg.setdefault("allow_remote_code", False)   # deixar aparelhos remotos usarem a aba Code
    cfg.setdefault("tokens", {})                 # aparelhos conectados
    cfg.setdefault("password_required", True)    # False = qualquer aparelho da rede de casa entra sem senha
    cfg.setdefault("internet_password_required", True)   # False = quem abrir o endereco publico (tunel) entra como dono, sem senha
    cfg.setdefault("owner_link_enabled", False)  # link secreto /owner-CODIGO: entra com acesso total (como a janela do PC)
    cfg.setdefault("owner_code", "")
    cfg.setdefault("port", PORT)
    cfg.setdefault("exa_api_key", "")            # pesquisa feita para IAs (exa.ai); vazio = usa DuckDuckGo
    cfg.setdefault("search_provider", "auto")    # auto | exa | duckduckgo
    cfg.setdefault("exa_type", "lite")           # lite (US$ 0,004/busca) | auto (US$ 0,007) | deep-lite
    cfg.setdefault("search_results", 5)          # resultados por busca (ate 10 o preco do Exa e o mesmo)
    cfg.setdefault("search_daily_limit", 100)    # maximo de buscas pagas do Exa por dia (0 = sem limite)
    changed = False
    if not cfg.get("password"):
        cfg["password"] = generate_password(); changed = True
        log("AUTH", "Senha do servidor gerada (veja em Configuracoes > Servidor).", COLOR_GREEN)
    if not cfg.get("net_default_on_v1"):   # migracao unica: quem ja tinha config antiga passa a ter a rede ligada por padrao
        cfg["remote_enabled"] = True; cfg["net_default_on_v1"] = True; changed = True
    if changed: save_config(cfg)
    _cfg_cache["mtime"] = os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else None
    _cfg_cache["data"] = copy.deepcopy(cfg)
    return cfg

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)
    _cfg_cache["mtime"] = None   # forca a releitura

def load_history():
    """Chats: {id: {title, messages, tab, welcome}}. Aceita o formato antigo (lista)."""
    data = _read_json(HISTORY_FILE, {})
    if isinstance(data, list):
        data = {c["id"]: {k: v for k, v in c.items() if k != "id"} for c in data if isinstance(c, dict) and "id" in c}
    return data if isinstance(data, dict) else {}

def save_history(data): _write_json(HISTORY_FILE, data)
def load_state(): return _read_json(STATE_FILE, {})
def save_state(data): _write_json(STATE_FILE, data)

def safe_theme_name(name):
    return re.sub(r'[^\w\- ]', '_', str(name)).strip()[:40] or "tema"

def list_custom_themes():
    """Temas salvos em 'custom themes/<nome>.json'."""
    out = []
    if os.path.isdir(THEMES_DIR):
        for f in sorted(os.listdir(THEMES_DIR)):
            if f.lower().endswith(".json"):
                data = _read_json(os.path.join(THEMES_DIR, f), None)
                if isinstance(data, dict):
                    data["name"] = os.path.splitext(f)[0]
                    out.append(data)
    return out

def get_workdir(cfg=None):
    cfg = cfg or load_config()
    wd = cfg.get("workdir") or BASE_DIR
    return wd if os.path.isdir(wd) else BASE_DIR

# ---------------------------------------------------------------- ferramentas
SEARCH_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
             'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'}
MAX_SEARCH_RESULTS = 5   # padrao; o valor real vem da configuracao "search_results"

def max_results():
    try: return max(1, min(10, int(load_config().get("search_results", MAX_SEARCH_RESULTS))))
    except (TypeError, ValueError): return MAX_SEARCH_RESULTS


def _clean_html(text):
    return re.sub(r'\s+', ' ', html_mod.unescape(re.sub(r'<[^>]+>', '', text))).strip()

def _fetch(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**SEARCH_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=10) as r: return r.read(2_000_000).decode('utf-8', 'replace')

# ---------------------------------------------------------------- estatisticas de uso
_stats_lock = threading.Lock()

def record_event(ev):
    ev["ts"] = time.time()
    try:
        with _stats_lock:
            data = _read_json(STATS_FILE, {"events": []})
            evs = data.get("events", []); evs.append(ev)
            data["events"] = evs[-5000:]
            _write_json(STATS_FILE, data)
    except Exception as e:
        log("STATS", f"Nao consegui gravar estatistica: {e}", COLOR_RED)

def is_ollama_cloud(model): return bool(re.search(r"(:|-)cloud$", model or ""))

def build_stats(days=30):
    now = time.time()
    allev = _read_json(STATS_FILE, {"events": []}).get("events", [])
    evs = [e for e in allev if e.get("ts", 0) >= now - days * 86400 and not e.get("user")]
    # Ollama: a conta so mede o uso da nuvem por tempo de GPU em janelas de 5 h e 7 dias; aqui e a soma do que passou por este app
    oll = {"h5": {"requests": 0, "seconds": 0.0, "tokens": 0}, "d7": {"requests": 0, "seconds": 0.0, "tokens": 0}, "month": {}, "local": {"requests": 0, "seconds": 0.0, "tokens": 0}}
    for e in allev:
        if e.get("type") != "chat" or str(e.get("model", "")).startswith("groq") or e.get("ts", 0) < now - 30 * 86400: continue
        sec, tk, age = e.get("seconds", 0.0), e.get("tokens", 0), now - e["ts"]
        if is_ollama_cloud(e.get("model")):
            if age <= 5 * 3600: oll["h5"]["requests"] += 1; oll["h5"]["seconds"] += sec; oll["h5"]["tokens"] += tk
            if age <= 7 * 86400: oll["d7"]["requests"] += 1; oll["d7"]["seconds"] += sec; oll["d7"]["tokens"] += tk
            mm = oll["month"].setdefault(e["model"], {"requests": 0, "seconds": 0.0, "tokens": 0}); mm["requests"] += 1; mm["seconds"] += sec; mm["tokens"] += tk
        elif age <= days * 86400:
            oll["local"]["requests"] += 1; oll["local"]["seconds"] += sec; oll["local"]["tokens"] += tk
    models, daily = {}, {}
    exa = {"searches": 0, "reads": 0, "cost": 0.0}
    tot = {"requests": 0, "tokens": 0, "seconds": 0.0}
    for e in evs:
        d = daily.setdefault(time.strftime("%Y-%m-%d", time.localtime(e["ts"])), {"requests": 0, "tokens": 0, "exa_cost": 0.0})
        if e.get("type") == "chat":
            m = models.setdefault(e.get("model", "?"), {"requests": 0, "tokens": 0, "seconds": 0.0, "best_tps": 0.0, "cloud": bool(e.get("cloud"))})
            tk, sec = e.get("tokens", 0), e.get("seconds", 0.0)
            m["requests"] += 1; m["tokens"] += tk; m["seconds"] += sec
            if sec > 0.2 and tk: m["best_tps"] = max(m["best_tps"], tk / sec)
            d["requests"] += 1; d["tokens"] += tk
            tot["requests"] += 1; tot["tokens"] += tk; tot["seconds"] += sec
        elif e.get("type") == "exa":
            exa["reads" if e.get("kind") == "contents" else "searches"] += 1
            exa["cost"] += e.get("cost") or 0.0; d["exa_cost"] += e.get("cost") or 0.0
    for m in models.values(): m["avg_tps"] = m["tokens"] / m["seconds"] if m["seconds"] > 0 else 0.0
    series = []
    for i in range(min(days, 14) - 1, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
        series.append({"day": day, **daily.get(day, {"requests": 0, "tokens": 0, "exa_cost": 0.0})})
    return {"days": days, "totals": tot, "models": models, "exa": exa, "series": series, "since": min((e["ts"] for e in evs), default=None), "ollama": oll}

# ---------------------------------------------------------------- rodar codigo dos blocos
RUN_DIR = os.path.join(BASE_DIR, "code_runs")          # os scripts que voce mandou rodar
PKG_DIR = os.path.join(BASE_DIR, "code_packages")      # bibliotecas instaladas para esses scripts (nao mexe no Python do app)
RUN_TIMEOUT = 60
PIP_NAMES = {"cv2": "opencv-python", "PIL": "pillow", "sklearn": "scikit-learn", "yaml": "pyyaml", "bs4": "beautifulsoup4", "skimage": "scikit-image", "dateutil": "python-dateutil",
             "dotenv": "python-dotenv", "serial": "pyserial", "Crypto": "pycryptodome", "OpenSSL": "pyopenssl", "jwt": "pyjwt", "discord": "discord.py", "telegram": "python-telegram-bot",
             "docx": "python-docx", "pptx": "python-pptx", "fitz": "pymupdf", "usb": "pyusb", "win32api": "pywin32", "win32com": "pywin32", "win32gui": "pywin32", "attr": "attrs",
             "magic": "python-magic", "git": "gitpython", "mpl_toolkits": "matplotlib", "pynput": "pynput", "PyQt5": "PyQt5", "PyQt6": "PyQt6", "PySide6": "PySide6", "wx": "wxPython",
             "speech_recognition": "SpeechRecognition", "pyaudio": "PyAudio", "Xlib": "python-xlib", "google": "google-api-python-client", "sounddevice": "sounddevice", "bson": "pymongo"}
GUI_MODULES = {"tkinter", "turtle", "pygame", "PyQt5", "PyQt6", "PySide2", "PySide6", "kivy", "wx", "pyglet", "arcade", "customtkinter", "ursina", "vpython", "pyglet", "dearpygui", "ttkbootstrap", "tkinterdnd2"}
RUN_LANGS = {"python": ".py", "javascript": ".js", "powershell": ".ps1", "bat": ".bat", "bash": ".sh"}
PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")

def py_imports(code):
    """Nomes dos modulos importados no topo do codigo (ast; se o codigo tem erro de sintaxe, uma busca por texto)."""
    mods = set()
    try:
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Import): mods.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module: mods.add(node.module.split(".")[0])
    except SyntaxError:
        for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w., ]+))", code, re.M):
            if m.group(1): mods.add(m.group(1).split(".")[0])
            else: mods.update(x.strip().split(" as ")[0].split(".")[0] for x in m.group(2).split(","))
    return {m for m in mods if m}

def missing_python_packages(code):
    """(pacotes pip que faltam, usa janela/GUI?)"""
    mods = py_imports(code); std = getattr(sys, "stdlib_module_names", set()); missing = []
    if PKG_DIR not in sys.path: sys.path.insert(0, PKG_DIR)
    importlib.invalidate_caches()
    for m in sorted(mods):
        if m in std or m == "__future__": continue
        try:
            if importlib.util.find_spec(m) is not None: continue
        except (ImportError, ValueError, AttributeError): pass
        if os.path.exists(os.path.join(RUN_DIR, m + ".py")): continue
        pkg = PIP_NAMES.get(m, m.replace("_", "-"))
        if PIP_SPEC_RE.match(pkg) and pkg not in missing: missing.append(pkg)
    return missing, bool(mods & GUI_MODULES)

def run_code(lang, code, analyze=False, install=False):
    lang = (lang or "").lower()
    if lang not in RUN_LANGS: return {"error": "Linguagem sem botao de rodar."}
    if not isinstance(code, str) or not code.strip() or len(code) > 200000: return {"error": "Codigo vazio ou grande demais."}
    exe, args, missing, gui = None, [], [], False
    if lang == "python": exe, (missing, gui) = sys.executable, missing_python_packages(code)
    elif lang == "javascript": exe = shutil.which("node")
    elif lang == "powershell": exe = shutil.which("powershell")
    elif lang == "bat": exe = shutil.which("cmd")
    elif lang == "bash": exe = shutil.which("bash")
    if not exe: return {"error": {"javascript": "Node.js nao encontrado neste PC (instale em nodejs.org).", "bash": "Bash nao encontrado neste PC (instale o Git for Windows)."}.get(lang, "Interpretador nao encontrado.")}
    if analyze: return {"ok": True, "missing": missing, "gui": gui}
    os.makedirs(RUN_DIR, exist_ok=True)
    for f in os.listdir(RUN_DIR):   # apaga scripts com mais de 1 dia
        fp = os.path.join(RUN_DIR, f)
        try:
            if os.path.isfile(fp) and time.time() - os.path.getmtime(fp) > 86400: os.remove(fp)
        except OSError: pass
    out_install = ""
    if install and missing:
        os.makedirs(PKG_DIR, exist_ok=True)
        log("CODIGO", "Instalando: " + ", ".join(missing), COLOR_YELLOW)
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--target", PKG_DIR, *missing], capture_output=True, text=True, timeout=600, creationflags=NOWIN, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired: return {"error": "A instalacao demorou demais (mais de 10 minutos)."}
        if r.returncode != 0: return {"ok": False, "exit": r.returncode, "output": "Falha ao instalar " + ", ".join(missing) + ":\n" + (r.stderr or r.stdout)[-3000:], "seconds": 0, "installed": []}
        out_install = "Instalado: " + ", ".join(missing) + "\n\n"
    script = os.path.join(RUN_DIR, uuid.uuid4().hex[:8] + RUN_LANGS[lang])
    with open(script, "w", encoding="utf-8", newline="\n" if lang != "bat" else None) as f: f.write(code)
    cmd = {"python": [exe, "-X", "utf8", script], "javascript": [exe, script], "powershell": [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script], "bat": [exe, "/c", script], "bash": [exe, script]}[lang]
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONPATH=os.pathsep.join(p for p in (PKG_DIR, os.environ.get("PYTHONPATH", "")) if p))
    log("CODIGO", f"Rodando {lang}: {os.path.basename(script)}", COLOR_CYAN)
    t0 = time.time()
    if gui:   # programas com janela: roda solto e so espera uns segundos para pegar erro logo de cara
        p = subprocess.Popen(cmd, cwd=RUN_DIR, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=NOWIN)
        try:
            outb, _ = p.communicate(timeout=3)
            return {"ok": p.returncode == 0, "exit": p.returncode, "output": out_install + outb.decode("utf-8", "replace")[-20000:], "seconds": round(time.time() - t0, 2)}
        except subprocess.TimeoutExpired:
            return {"ok": True, "detached": True, "output": out_install + "O programa abriu uma janela e continua rodando. Feche a janela dele quando terminar.", "seconds": 3}
    try:
        r = subprocess.run(cmd, cwd=RUN_DIR, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=RUN_TIMEOUT, creationflags=NOWIN)
        out = (r.stdout.decode("utf-8", "replace") + (("\n" if r.stdout else "") + r.stderr.decode("utf-8", "replace") if r.stderr else "")).strip()
        return {"ok": r.returncode == 0, "exit": r.returncode, "output": out_install + out[-20000:], "seconds": round(time.time() - t0, 2)}
    except subprocess.TimeoutExpired as e:
        partial = ((e.stdout or b"").decode("utf-8", "replace") + (e.stderr or b"").decode("utf-8", "replace")).strip()
        return {"ok": False, "exit": None, "timeout": True, "output": out_install + partial[-20000:] + f"\n\n(parado: passou de {RUN_TIMEOUT} s)", "seconds": RUN_TIMEOUT}

# ---------------------------------------------------------------- desfazer (backup antes de a IA sobrescrever um arquivo)
def save_undo(path, existed, old_bytes):
    os.makedirs(UNDO_DIR, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    _write_json(os.path.join(UNDO_DIR, uid + ".json"), {"path": path, "existed": existed, "old_b64": base64.b64encode(old_bytes or b"").decode(), "ts": time.time()})
    files = sorted((os.path.join(UNDO_DIR, f) for f in os.listdir(UNDO_DIR) if f.endswith(".json")), key=os.path.getmtime)
    for old in files[:-50]:   # guarda so os 50 mais recentes
        try: os.remove(old)
        except OSError: pass
    return uid

def do_undo(uid):
    f = os.path.join(UNDO_DIR, uid + ".json")
    if not re.fullmatch(r'[0-9a-f]{8}', uid) or not os.path.exists(f): raise Exception("Backup nao encontrado (ja foi desfeito ou expirou).")
    d = _read_json(f, {})
    if d.get("existed"):
        with open(d["path"], "wb") as fh: fh.write(base64.b64decode(d.get("old_b64", "")))
        msg = "Arquivo restaurado para a versao anterior."
    else:
        try: os.remove(d["path"]); msg = "Arquivo criado pela IA foi apagado."
        except FileNotFoundError: msg = "O arquivo ja nao existia."
    os.remove(f)
    log("DESFAZER", f"{msg} {d.get('path')}", COLOR_YELLOW)
    return msg

# ---------------------------------------------------------------- arquivos anexados
def extract_file_text(filename, data):
    """Retorna (texto, cortado?, paginas). Aceita texto/codigo (qualquer codificacao comum) e PDF."""
    ext = os.path.splitext(filename.lower())[1]
    pages = None
    if ext == ".pdf":
        try: from pypdf import PdfReader
        except ImportError: raise Exception("Para ler PDF instale o pypdf: pip install pypdf")
        reader = PdfReader(io.BytesIO(data)); pages = len(reader.pages); parts = []; total = 0
        for i, page in enumerate(reader.pages, 1):
            t = (page.extract_text() or "").strip()
            if t: parts.append(f"--- pagina {i} ---\n{t}"); total += len(t)
            if total > MAX_FILE_CHARS: break
        text = "\n\n".join(parts)
        if not text.strip(): raise Exception("Este PDF nao tem texto selecionavel (talvez seja escaneado).")
    else:
        if b"\x00" in data[:8000]: raise Exception("Arquivo binario nao suportado (use texto, codigo ou PDF).")
        try: text = data.decode("utf-8-sig")
        except UnicodeDecodeError: text = data.decode("latin-1")
    return text[:MAX_FILE_CHARS], len(text) > MAX_FILE_CHARS, pages

# ---------------------------------------------------------------- ler uma pagina da web
def _is_public_url(url):
    """Evita que a IA use a ferramenta para acessar a rede interna (SSRF)."""
    try:
        for info in socket.getaddrinfo(urllib.parse.urlsplit(url).hostname or "", None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast: return False
        return True
    except Exception:
        return False

def read_url_text(url, max_chars=12000):
    """Retorna (titulo, texto) da pagina. Usa o Exa /contents (texto limpo) e, sem chave ou se falhar, baixa direto."""
    url = (url or "").strip()
    if not re.match(r'^https?://', url, re.I): raise Exception("URL invalida (use http:// ou https://)")
    key = exa_api_key()
    if key:
        try:
            req = urllib.request.Request("https://api.exa.ai/contents", data=json.dumps({"urls": [url], "text": {"maxCharacters": max_chars}}).encode(),
                                         headers={"x-api-key": key, "Content-Type": "application/json", "User-Agent": "thingmabobber/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r: data = json.load(r)
            record_event({"type": "exa", "kind": "contents", "cost": (data.get("costDollars") or {}).get("total")})
            r0 = (data.get("results") or [None])[0]
            if r0 and (r0.get("text") or "").strip(): return r0.get("title") or url, r0["text"].strip()
        except Exception as e:
            log("WEB", f"Exa /contents falhou ({e}); baixando a pagina direto.", COLOR_YELLOW)
    if not _is_public_url(url): raise Exception("endereco bloqueado (rede privada)")
    page = _fetch(url)
    title = re.search(r'<title[^>]*>(.*?)</title>', page, re.S | re.I)
    body = re.sub(r'(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>', ' ', page)
    body = re.sub(r'(?i)<br\s*/?>|</(p|div|li|tr|h[1-6]|section|article)>', '\n', body)
    text = html_mod.unescape(re.sub(r'<[^>]+>', '', body))
    text = re.sub(r'[ \t]+', ' ', text); text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
    if not text: raise Exception("a pagina nao tem texto legivel")
    return (_clean_html(title.group(1)) if title else url), text[:max_chars]

def _search_ddg(query):
    """DuckDuckGo 'lite' (o endpoint /html/ passou a exigir verificacao anti-robo)."""
    page = _fetch("https://lite.duckduckgo.com/lite/", data=urllib.parse.urlencode({'q': query}).encode(), headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if re.search(r'anomaly|bots use duckduckgo', page, re.I): raise Exception("pediu verificacao anti-robo")
    out = []
    for m in re.finditer(r"""<a[^>]*href="([^"]+)"[^>]*class='result-link'[^>]*>(.*?)</a>.*?<td[^>]*class='result-snippet'[^>]*>(.*?)</td>""", page, re.S):
        url = html_mod.unescape(m.group(1))
        if 'duckduckgo.com/y.js' in url: continue   # anuncio
        out.append((_clean_html(m.group(2)), _clean_html(m.group(3)), 'https:' + url if url.startswith('//') else url))
        if len(out) >= max_results(): break
    return out

EXA_URL = "https://api.exa.ai/search"
EXA_TYPES = ("lite", "auto", "deep-lite")
NEWS_RE = re.compile(r'\b(not[ií]cias?|news|[uú]ltimas not[ií]cias|latest news|breaking)\b', re.I)

def exa_api_key(cfg=None):
    return ((cfg or load_config()).get("exa_api_key") or os.environ.get("EXA_API_KEY") or "").strip()

def _search_exa(query, key, kind="auto"):
    """Exa (busca feita para IAs): devolve os trechos mais relevantes de cada pagina ("highlights") e a data de publicacao."""
    kind = kind if kind in EXA_TYPES else "auto"
    body = {"query": query, "numResults": max_results(), "type": kind, "contents": {"highlights": {"maxCharacters": 800}}}
    if kind != "lite":   # o tipo "lite" aceita poucos parametros
        if NEWS_RE.search(query): body["category"] = "news"   # so noticias: rapido e traz as de hoje (forcar recrawl so atrasava 4-5 s sem mudar o resultado)
    req = urllib.request.Request(EXA_URL, data=json.dumps(body).encode(), headers={"x-api-key": key, "Content-Type": "application/json", "User-Agent": "thingmabobber/1.0"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=25 if kind == "deep-lite" else 15) as r: data = json.load(r)
    except urllib.error.HTTPError as e:
        why = {401: "chave do Exa invalida", 402: "sem creditos no Exa", 429: "limite de requisicoes do Exa"}.get(e.code, f"Exa respondeu {e.code}")
        raise Exception(why)
    out = []
    for r in data.get("results", [])[:max_results()]:
        text = " ... ".join(h.strip() for h in (r.get("highlights") or []) if h) or r.get("summary") or r.get("text") or ""
        date = (r.get("publishedDate") or "")[:10]
        out.append((r.get("title") or r.get("url", ""), (f"[{date}] " if date else "") + _clean_html(text)[:900], r.get("url", "")))
    cost = (data.get("costDollars") or {}).get("total")
    record_event({"type": "exa", "kind": "search", "cost": cost if isinstance(cost, (int, float)) else 0.0})
    log("WEB", f"Exa ({kind}) em {time.time() - t:.1f}s" + (f", custo US$ {cost:.4f}" if isinstance(cost, (int, float)) else ""), COLOR_GRAY)
    return out

def _search_wikipedia(query):
    """Ultimo recurso: so enciclopedia, mas nunca bloqueia."""
    out = []
    for lang in ("pt", "en"):
        data = json.loads(_fetch(f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit={max_results()}&utf8=1"))
        for x in data.get("query", {}).get("search", []):
            out.append((x["title"], _clean_html(x["snippet"]), f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(x['title'].replace(' ', '_'))}"))
        if out: break
    return out[:max_results()]

_search_cache = {}          # consulta normalizada -> (hora, resultados, fonte)
SEARCH_CACHE_TTL = 6 * 3600  # a mesma busca nao e paga de novo por 6 horas
SEARCH_CACHE_MAX = 200

def exa_searches_today():
    """Quantas buscas pagas do Exa foram feitas hoje (da meia-noite local)."""
    midnight = time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))
    return sum(1 for e in _read_json(STATS_FILE, {"events": []}).get("events", []) if e.get("type") == "exa" and e.get("kind") == "search" and e.get("ts", 0) >= midnight)

GREETING_RE = re.compile(r"(?i)(oi+|ol[aá]|e a[ií]|bom dia|boa tarde|boa noite|obrigad[oa]|valeu|ok(ay)?|certo|entendi|beleza|tchau|hi|hello|hey|thanks?|thank you|bye|cool)[\s!.?,]*")

CREATIVE_RE = re.compile(r"(?i)(me )?(conta|conte|escreva|escreve|crie|cria|gere|gera|invente|traduza|traduz|resuma|resume|reescreva|reescreve|corrija|corrige|revise|explique (esse|este|o|a) (c[oó]digo|texto|trecho)|tell me (a|an)|write|create|generate|make up|translate|summari[sz]e|rewrite|fix|proofread)\b")
FRESH_HINT_RE = re.compile(r"(?i)\b(hoje|agora|atual|atuais|recente|recentes|[uú]ltim[ao]s?|not[ií]cias?|pre[cç]o|cota[cç][aã]o|today|current|latest|recent|news|price|2025|2026)\b")

def needs_web(text):
    """Evita gastar uma busca paga em mensagens que nao precisam: cumprimentos, frases curtas sem pergunta, codigo e arquivos anexados."""
    t = (text or "").strip()
    if len(t) < MIN_WEB_QUERY or GREETING_RE.fullmatch(t): return False
    if len(re.findall(r"\w+", t)) <= 3 and "?" not in t: return False
    if "```" in t or t.startswith("/"): return False
    if "[Arquivo anexado" in t or "[Attached file" in t: return False   # a pergunta e sobre o arquivo
    if CREATIVE_RE.match(t) and not FRESH_HINT_RE.search(t): return False   # pedido criativo/de transformacao: nao precisa de internet
    return True

def search_web_results(query, guest=False):
    """Exa (se houver chave e limite diario), depois DuckDuckGo, depois Wikipedia. Retorna ([(titulo, trecho, link)], fonte) ou ([], None)."""
    cfg = load_config(); key = exa_api_key(cfg); provider = cfg.get("search_provider", "auto")
    if guest: key, provider = "", "duckduckgo"   # amigos nunca gastam o Exa
    ck = ("g:" if guest else "") + re.sub(r"\s+", " ", (query or "").strip().lower())
    hit = _search_cache.get(ck)
    if hit and time.time() - hit[0] < SEARCH_CACHE_TTL:
        log("WEB", "Resultado reaproveitado do cache (busca repetida, sem custo).", COLOR_GRAY)
        return hit[1], hit[2] + " (cache)"
    chain = []
    if provider in ("auto", "exa") and key:
        limit = int(cfg.get("search_daily_limit", 100) or 0)
        if limit and exa_searches_today() >= limit:
            log("WEB", f"Limite diario do Exa atingido ({limit} buscas); usando DuckDuckGo hoje.", COLOR_YELLOW)
        else:
            chain.append(("Exa", lambda q: _search_exa(q, key, cfg.get("exa_type", "lite"))))
    if provider != "exa" or not chain: chain.append(("DuckDuckGo", _search_ddg))
    chain.append(("Wikipedia", _search_wikipedia))
    errors = []
    for name, fn in chain:
        try:
            res = fn(query)
            if res:
                if len(_search_cache) >= SEARCH_CACHE_MAX: _search_cache.pop(next(iter(_search_cache)))
                _search_cache[ck] = (time.time(), res, name)
                return res, name
            errors.append(f"{name}: sem resultados")
        except Exception as e:
            errors.append(f"{name}: {e}")
    log("WEB", "Pesquisa falhou em todas as fontes -> " + "; ".join(errors), COLOR_RED)
    return [], None

def format_search(results, source):
    out = f"\n\n--- RESULTADOS / RESULTS ({source}) ---\n"
    if str(source).startswith("Wikipedia"):   # ultima opcao: busca por palavras, pode trazer paginas sem relacao com a pergunta
        out += ("AVISO / NOTE: a busca principal esta indisponivel; estes resultados podem NAO responder a pergunta. Se nao responderem, diga que nao encontrou. / "
                "The main search is unavailable; these results may NOT answer the question. If they do not, say you could not find it.\n")
    for i, (title, snippet, link) in enumerate(results, 1): out += f"[{i}] {title}\n{snippet}\nLink: {link}\n\n"
    return out

SEARCH_UNAVAILABLE = ("Pesquisa na web indisponivel agora / Web search unavailable right now. "
                      "NAO invente a resposta: diga ao usuario que nao foi possivel pesquisar. / Do NOT make up an answer: tell the user the search was not possible.")

def search_web(query):
    results, source = search_web_results(query)
    if not results:
        return SEARCH_UNAVAILABLE
    log("WEB", f"{len(results)} resultado(s) via {source}", COLOR_GREEN)
    return format_search(results, source)

TOOL_PROMPT = """

[MODO AGENTE]
Voce pode usar ferramentas no computador do usuario. Pasta de trabalho: {workdir}
Para chamar uma ferramenta, escreva EXATAMENTE neste formato e PARE de escrever logo depois:
$$[TOOL: nome] {"argumento": "valor"}$$
Ferramentas:
- list_files {"path": "."} : lista os arquivos de uma pasta
- read_file {"path": "arquivo.txt"} : le um arquivo
- write_file {"path": "arquivo.txt", "content": "texto"} : cria ou sobrescreve um arquivo (pede permissao)
- cmd {"command": "dir"} : executa no CMD (pede permissao)
- powershell {"command": "Get-Date"} : executa no PowerShell (pede permissao)
- search_web {"query": "texto"} : pesquisa na web
- read_url {"url": "https://..."} : le o texto de uma pagina da web (use depois de search_web para ler uma fonte)
Faca UMA chamada por vez; o resultado volta na proxima mensagem. Quando terminar, responda normalmente, sem ferramentas.
"""

TOOL_PROMPT_EN = """

[AGENT MODE]
You can use tools on the user's computer. Working folder: {workdir}
To call a tool, write EXACTLY this format and STOP writing right after it:
$$[TOOL: name] {"argument": "value"}$$
Tools:
- list_files {"path": "."} : list the files in a folder
- read_file {"path": "file.txt"} : read a file
- write_file {"path": "file.txt", "content": "text"} : create or overwrite a file (asks permission)
- cmd {"command": "dir"} : run in CMD (asks permission)
- powershell {"command": "Get-Date"} : run in PowerShell (asks permission)
- search_web {"query": "text"} : search the web
- read_url {"url": "https://..."} : read the text of a web page (use after search_web to read a source)
Make ONE call at a time; the result comes back in the next message. When you are done, answer normally, without tools.
"""

PATH_TOOLS = ("list_files", "read_file", "write_file")

def normalize_args(name, args):
    """Aceita argumentos mal formados (chave errada) pegando o primeiro valor."""
    if not isinstance(args, dict): args = {}
    key = "command" if name in ("cmd", "powershell") else "query" if name == "search_web" else "url" if name == "read_url" else "path" if name in PATH_TOOLS else None
    if key and key not in args and args:
        args[key] = list(args.values())[0]
    return args

def describe_tool(name, args):
    if name in ("cmd", "powershell"): return f"{name}: {args.get('command', '')}"
    if name == "write_file": return f"Escrever arquivo: {args.get('path', '')} ({len(args.get('content', ''))} caracteres)"
    return f"{name} {args}"

def needs_permission(name):
    return name in ("cmd", "powershell", "write_file")

def truncate(text):
    text = str(text)
    if len(text) > MAX_TOOL_OUTPUT:
        return text[:MAX_TOOL_OUTPUT] + f"\n...[cortado, {len(text) - MAX_TOOL_OUTPUT} caracteres omitidos]"
    return text

def execute_tool(tool_name, tool_args, workdir, lang="pt"):
    L = lambda pt, en: en if lang == "en" else pt
    def full(p): return p if os.path.isabs(p) else os.path.join(workdir, p)
    try:
        if tool_name == "list_files":
            return truncate("\n".join(os.listdir(full(tool_args.get("path", ".")))) or L("(pasta vazia)", "(empty folder)"))
        if tool_name == "read_file":
            with open(full(tool_args["path"]), 'r', encoding='utf-8', errors='replace') as f: return truncate(f.read())
        if tool_name == "write_file":
            path = full(tool_args["path"]); new = tool_args.get("content", "")
            existed = os.path.exists(path); old_bytes = b""
            if existed:
                with open(path, "rb") as f: old_bytes = f.read(5_000_000)
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f: f.write(new)
            uid = save_undo(path, existed, old_bytes)
            if b"\x00" in old_bytes[:8000]: return L(f"Arquivo binario substituido. [undo:{uid}]", f"Binary file replaced. [undo:{uid}]")
            diff = list(difflib.unified_diff(old_bytes.decode("utf-8", "replace").splitlines(), new.splitlines(), L("antes", "before") if existed else L("(novo arquivo)", "(new file)"), L("depois", "after"), lineterm="", n=2))
            shown = ("\n".join(diff[:120]) + (L(f"\n... (+{len(diff) - 120} linhas)", f"\n... (+{len(diff) - 120} lines)") if len(diff) > 120 else "")) or L("(sem alteracoes)", "(no changes)")
            return f"{L('Arquivo escrito com sucesso.', 'File written successfully.')} [undo:{uid}]\n```diff\n{shown}\n```"
        if tool_name in ("cmd", "powershell"):
            cmd = tool_args["command"]
            argv = cmd if tool_name == "cmd" else ["powershell", "-NoProfile", "-Command", cmd]
            r = subprocess.run(argv, shell=(tool_name == "cmd"), capture_output=True, text=True, errors="replace", timeout=TOOL_TIMEOUT, cwd=workdir)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0: out += L(f"\n[codigo de saida {r.returncode}]", f"\n[exit code {r.returncode}]")
            return truncate(out.strip() or L("(sem saida)", "(no output)"))
        if tool_name == "search_web":
            return truncate(search_web(tool_args.get("query", "")))
        if tool_name == "read_url":
            title, page = read_url_text(tool_args.get("url", ""))
            return truncate(f"{title}\n\n{page}")
        return L(f"Ferramenta desconhecida: {tool_name}", f"Unknown tool: {tool_name}")
    except subprocess.TimeoutExpired:
        return L(f"Erro: comando passou de {TOOL_TIMEOUT}s e foi cancelado.", f"Error: command exceeded {TOOL_TIMEOUT}s and was cancelled.")
    except KeyError as e:
        return L(f"Erro: argumento faltando: {e}", f"Error: missing argument: {e}")
    except Exception as e:
        return f"Erro: {e}"

TOOL_NAMES = ("list_files", "read_file", "write_file", "cmd", "powershell", "search_web", "read_url")
TOOL_MARK = re.compile(r'(?:\$\$\s*)?\[\s*TOOL\s*[:\s]\s*(\w+)[^\]]*\]', re.IGNORECASE)   # "$$" na frente e opcional
TOOL_MARK_SHORT = re.compile(r'\$\$\s*\[\s*(' + "|".join(TOOL_NAMES) + r')\s*\]', re.IGNORECASE)   # "$$[cmd] {...}$$" (sem a palavra TOOL)
TOOL_INLINE = re.compile(r'\$\$\s*\[\s*(cmd|powershell|search_web|read_url|read_file|list_files)\s*[:=]\s*(.+?)\s*\]\s*\$\$', re.IGNORECASE | re.DOTALL)   # "$$[cmd: "dir"]$$"
INLINE_KEY = {"cmd": "command", "powershell": "command", "search_web": "query", "read_url": "url", "read_file": "path", "list_files": "path"}   # write_file nunca (precisa do conteudo)
FENCE_MARK = re.compile(r'```[ \t]*(' + "|".join(TOOL_NAMES) + r')\b', re.IGNORECASE)    # modelos pequenos as vezes usam ```powershell {...}```
ARG_KEYS = {"command", "path", "content", "query", "url"}

def _decode_json(rest):
    for candidate in (rest, rest.replace("'", '"')):
        try: return json.JSONDecoder().raw_decode(candidate)
        except Exception: pass
    return None

def find_tool_call(text):
    """Procura uma chamada completa de ferramenta. Retorna (nome, args, fim) ou None.
    Formato oficial: $$[TOOL: nome] {json}$$. Tambem aceita sem os $$ e o bloco ```nome {json}```."""
    fence = False
    m = TOOL_MARK.search(text) or TOOL_MARK_SHORT.search(text)
    if not m:
        mi = TOOL_INLINE.search(text)
        if mi:
            name = mi.group(1).lower()
            return name, {INLINE_KEY[name]: mi.group(2).strip().strip('"\'`')}, mi.end()
    if m:
        name, base = m.group(1).lower() if m.re is TOOL_MARK_SHORT else m.group(1), m.end()
    else:
        f = FENCE_MARK.search(text)
        if not f: return None
        name, base, fence = f.group(1).lower(), f.end(), True
    rest = text[base:]
    start = rest.find('{')
    if start == -1: return None
    if fence and rest[:start].strip(): return None   # exemplo de codigo comum, nao uma chamada
    decoded = _decode_json(rest[start:])
    if not decoded: return None
    args, used = decoded
    if fence and (not isinstance(args, dict) or not args or not set(args) <= ARG_KEYS): return None
    end = base + start + used
    if fence:
        close = re.match(r'[\s$]*```', text[end:])
        if close: end += close.end()
    elif text[end:end + 6].lstrip().startswith("$$"):
        end = text.index("$$", end) + 2
    return name, args, end

def looks_like_failed_call(text):
    """A IA tentou chamar uma ferramenta mas errou o formato (nada foi reconhecido)."""
    return bool(re.search(r'\[\s*TOOL|\$\$\s*\[', text, re.I) or re.search(r'\{\s*"(command|path|query|content)"\s*:', text))

CORRECTION_PT = 'Formato invalido: nenhuma ferramenta foi executada. Para usar uma ferramenta escreva EXATAMENTE $$[TOOL: nome] {"argumento": "valor"}$$ (sem bloco de codigo) e pare de escrever. Tente de novo.'
CORRECTION_EN = 'Invalid format: no tool was run. To use a tool write EXACTLY $$[TOOL: name] {"argument": "value"}$$ (no code block) and stop writing. Try again.'

def _schema(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": required}}}

NATIVE_TOOLS = [
    _schema("list_files", "List the files in a folder", {"path": {"type": "string"}}, []),
    _schema("read_file", "Read a text file", {"path": {"type": "string"}}, ["path"]),
    _schema("write_file", "Create or overwrite a file", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _schema("cmd", "Run a command in the Windows CMD", {"command": {"type": "string"}}, ["command"]),
    _schema("powershell", "Run a command in PowerShell", {"command": {"type": "string"}}, ["command"]),
    _schema("search_web", "Search the web", {"query": {"type": "string"}}, ["query"]),
    _schema("read_url", "Read the text of a web page", {"url": {"type": "string"}}, ["url"]),
]

def _clean_arg(v):
    return v.strip().strip('"\'`') if isinstance(v, str) and not v.startswith(("\n", " ")) and len(v) < 4096 and "\n" not in v else v

def native_tool_call(model, messages, num_ctx=None, workdir=None):
    """Plano B para quando a IA nao acerta o formato de texto das ferramentas: usa o recurso NATIVO de
    ferramentas do Ollama (so modelos com a capacidade 'tools'). Retorna (nome, args) ou None."""
    if "tools" not in (get_model_info(model).get("caps") or []): return None
    msgs = [dict(m) for m in messages]
    if msgs and msgs[0].get("role") == "system":   # tira a instrucao do formato de texto, senao a IA continua obedecendo ela
        base = re.split(r'\n\n\[(?:MODO AGENTE|AGENT MODE)\]', msgs[0]["content"])[0]
        msgs[0]["content"] = base + "\n\nYou can use tools on the user's computer through function calls." + (f" Working folder: {workdir}" if workdir else "")
    msgs.append({"role": "user", "content": "Call the tool needed to fulfil the user's request now (use the function call, do not write text)."})
    payload = {"model": model, "messages": msgs, "stream": False, "think": False, "tools": NATIVE_TOOLS}
    if num_ctx: payload["options"] = {"num_ctx": int(num_ctx)}
    try:
        data = json.loads(ollama_post("/api/chat", payload, timeout=120))
    except Exception as e:
        log("AGENTE", f"Plano B falhou: {e}", COLOR_RED)
        return None
    msg = data.get("message") or {}
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}; name = fn.get("name"); args = fn.get("arguments")
        if isinstance(args, str):
            try: args = json.loads(args)
            except ValueError: args = None
        if name in TOOL_NAMES and isinstance(args, dict):
            return name, {k: (_clean_arg(v) if k != "content" else v) for k, v in args.items()}
    c = find_tool_call(msg.get("content") or "")   # alguns modelos respondem com o formato de texto mesmo assim
    return (c[0], c[1]) if c else None

def ask_permission(description):
    """Bloqueia ate o usuario aprovar/negar no popup (ou parar a geracao)."""
    event = threading.Event()
    result = {"ok": False}
    def resolve(val): result["ok"] = bool(val); event.set()
    pending_command["cmd"] = description
    pending_command["resolve"] = resolve
    log("PERMISSAO", f"Aguardando o usuario: {description}", COLOR_YELLOW)
    while not event.wait(1):
        if stop_generation_flag.is_set(): resolve(False)
    pending_command["cmd"] = ""
    pending_command["resolve"] = None
    return result["ok"]

# ---------------------------------------------------------------- ollama
def ollama_is_running():
    try: urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2); return True
    except: return False

def ollama_post(path, payload, timeout=120):
    req = urllib.request.Request(f"{OLLAMA_URL}{path}", data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()

def ollama_tags():
    """Modelos INSTALADOS no Ollama ([{name, size, ...}]) ou None se o Ollama nao responde."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r: return json.load(r).get("models", [])
    except Exception:
        return None

_model_info_cache = {}
def get_model_info(name):
    """Detalhes de um modelo instalado, lidos do proprio Ollama (parametros, quantizacao, contexto, capacidades)."""
    hit = _model_info_cache.get(name)
    if hit and time.time() - hit[0] < 120: return hit[1]
    try:
        d = json.loads(ollama_post("/api/show", {"model": name}, timeout=10))
    except Exception:
        return {}
    mi = d.get("model_info") or {}
    det = d.get("details") or {}
    info = {"params": det.get("parameter_size"), "quant": det.get("quantization_level"), "caps": d.get("capabilities") or [],
            "ctx": next((v for k, v in mi.items() if k.endswith(".context_length")), None)}
    _model_info_cache[name] = (time.time(), info)
    return info

def ollama_ps():
    """Modelos carregados na memoria agora: [{name, size, size_vram, ...}]."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=2) as r: return json.load(r).get("models", [])
    except Exception:
        return []

def ollama_load(model, num_ctx=None):
    """Carrega o modelo. Com o mesmo num_ctx do chat: contexto diferente faz o Ollama recarregar o modelo (carregava duas vezes)."""
    payload = {"model": model, "keep_alive": "10m"}
    if num_ctx: payload["options"] = {"num_ctx": int(num_ctx)}
    ollama_post("/api/generate", payload)

def ollama_unload(model):
    ollama_post("/api/generate", {"model": model, "keep_alive": 0}, timeout=30)

def start_ollama():
    """Retorna True se o Ollama esta rodando ao final."""
    global ollama_process
    if ollama_is_running(): return True
    log("OLLAMA", "Ollama nao esta rodando. Iniciando...", COLOR_YELLOW)
    try:
        ollama_process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        for _ in range(15):
            if ollama_is_running(): break
            time.sleep(1)
    except FileNotFoundError:
        log("OLLAMA", "Comando 'ollama' nao encontrado. Instale em ollama.com", COLOR_RED)
    except Exception as e:
        log("OLLAMA", f"Falha ao iniciar: {e}", COLOR_RED)
    ok = ollama_is_running()
    log("OLLAMA", "Ollama pronto." if ok else "Ollama nao respondeu.", COLOR_GREEN if ok else COLOR_RED)
    return ok

def stop_ollama():
    global ollama_process
    if ollama_process:
        log("OLLAMA", "Encerrando Ollama iniciado por este programa.", COLOR_YELLOW)
        try: ollama_process.terminate(); ollama_process.wait(timeout=10)
        except Exception: pass
        ollama_process = None

def shutdown_all():
    """Ao fechar o app: para a geracao, descarrega todos os modelos e encerra o que foi iniciado aqui."""
    stop_generation_flag.set()
    stop_tunnel()
    stop_gpu_stream()
    for m in ollama_ps():
        try:
            ollama_unload(m["name"]); log("SAIDA", f"Modelo {m['name']} desligado.", COLOR_YELLOW)
        except Exception as e:
            log("SAIDA", f"Nao consegui desligar {m['name']}: {e}", COLOR_RED)
    stop_ollama()
atexit.register(stop_ollama)

# ---------------------------------------------------------------- monitor de memoria
alert_state = {"id": 0, "kind": "", "text": "", "suggest": "", "count": 0, "used": 0, "total": 0, "partial": False}
_vram_alerts = {"count": 0, "last": 0.0}
_swap_alerts = {"count": 0, "last": 0.0}

def rank_models_to_stop(loaded):
    """Pontua cada modelo carregado: quanto maior, melhor candidato a desligar.
    pontuacao = minutos ocioso + 2 x GB ocupados - 0.5 x usos (maximo 20)."""
    now = time.time()
    ranked = []
    for m in loaded:
        name = m["name"]
        if generation_active and name == active_model: continue   # nao sugere desligar quem esta respondendo
        u = model_usage.get(name, {})
        idle_min = (now - u.get("last_used", started_at)) / 60
        gb = m.get("size", 0) / 1e9
        uses = u.get("uses", 0)
        ranked.append((idle_min + 2 * gb - 0.5 * min(uses, 20), name, f"{name}: ocioso {idle_min:.1f} min, {gb:.1f} GB, {uses} uso(s)"))
    return sorted(ranked, reverse=True)

def emit_alert(kind, text, suggest, count, used=0, total=0, partial=False):
    if kind != "vram":   # "VRAM alta" aparece so no terminal; a janela so mostra o aviso de VRAM no limite
        alert_state.update(id=alert_state["id"] + 1, kind=kind, text=text, suggest=suggest, count=count, used=used, total=total, partial=partial)
    log("MEMORIA", f"{text} (aviso {count})", COLOR_YELLOW)

def check_memory():
    used, total, _ = get_gpu_metrics()
    if used is None: return
    now = time.time()
    loaded = ollama_ps()
    partial = any(m.get("size_vram", 0) < m.get("size", 0) * 0.98 for m in loaded)
    swap = partial or used >= total - 300
    high = used > VRAM_WARN_MB
    if not high: _vram_alerts["count"] = 0
    if not swap: _swap_alerts["count"] = 0
    if swap and now - _swap_alerts["last"] >= 30:
        ranked = rank_models_to_stop(loaded)
        for _, _, detail in ranked: log("MEMORIA", f"  pontuacao -> {detail}", COLOR_GRAY)
        suggest = ranked[0][1] if ranked else ""
        _swap_alerts["count"] += 1; _swap_alerts["last"] = now
        text = f"VRAM no limite ({used / 1024:.1f} de {total / 1024:.1f} GB)" + (", modelo vazando para a RAM/CPU" if partial else "")
        text += f". Recomendado desligar o modelo {suggest}." if suggest else "."
        emit_alert("swap", text, suggest, _swap_alerts["count"], used, total, partial)
    elif high and not swap and now - _vram_alerts["last"] >= VRAM_ALERT_EVERY_S - 0.1:
        _vram_alerts["count"] += 1; _vram_alerts["last"] = now
        emit_alert("vram", f"VRAM alta: {used / 1024:.1f} de {total / 1024:.1f} GB em uso.", "", _vram_alerts["count"], used, total)

def monitor_loop():
    while True:
        time.sleep(MONITOR_EVERY_S)
        try: check_memory()
        except Exception as e: log("MEMORIA", f"Erro no monitor: {e}", COLOR_RED)

# ---------------------------------------------------------------- modelos
def stream_ollama(model, messages, think, num_ctx=None, max_tokens=None):
    """Gera ('content'|'thinking'|'stats', valor)."""
    payload = {"model": model, "messages": messages, "stream": True, "think": bool(think)}
    opts = {}
    if num_ctx: opts["num_ctx"] = int(num_ctx)   # tamanho do contexto (o padrao do Ollama e 4096)
    if max_tokens: opts["num_predict"] = int(max_tokens)
    if opts: payload["options"] = opts
    for attempt in range(2):
        req = urllib.request.Request(f'{OLLAMA_URL}/api/chat', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            response = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')
            if attempt == 0 and payload.get("think") and "think" in body.lower():
                log("OLLAMA", f"{model} nao suporta 'pensar'. Tentando sem.", COLOR_YELLOW)
                payload["think"] = False
                continue
            raise Exception(f"Ollama respondeu {e.code}: {body[:200]}")
        with response:
            for raw in response:
                if not raw.strip(): continue
                data = json.loads(raw)
                if data.get("error"): raise Exception(data["error"])
                msg = data.get("message", {})
                if msg.get("thinking"): yield "thinking", msg["thinking"]
                if msg.get("content"): yield "content", msg["content"]
                if data.get("done") and data.get("eval_count") and data.get("eval_duration"):
                    yield "stats", {"tokens": data["eval_count"], "seconds": data["eval_duration"] / 1e9,
                                    "prompt_tokens": data.get("prompt_eval_count", 0),
                                    "prompt_seconds": data.get("prompt_eval_duration", 0) / 1e9,
                                    "load_seconds": data.get("load_duration", 0) / 1e9,
                                    "total_seconds": data.get("total_duration", 0) / 1e9}
        return

def stream_groq(model, messages, cfg):
    if not HAS_GROQ: raise Exception("Biblioteca Groq nao instalada (pip install groq).")
    if not cfg.get("groq_api_key"): raise Exception("Chave do Groq nao configurada. Abra Configuracoes e cole sua chave.")
    client = Groq(api_key=cfg["groq_api_key"])
    messages = [{"role": m["role"], "content": m["content"]} for m in messages]   # Groq nao aceita o campo "images"
    for chunk in client.chat.completions.create(model=model.replace("groq-", "", 1), messages=messages, stream=True):
        if chunk.choices and chunk.choices[0].delta.content:
            yield "content", chunk.choices[0].delta.content

def stream_model(model, messages, think, cfg, num_ctx=None, max_tokens=None):
    return stream_groq(model, messages, cfg) if model.startswith("groq") else stream_ollama(model, messages, think, num_ctx, max_tokens)

# ---------------------------------------------------------------- servidor
LOOPBACK_IPS = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
LOCAL_HOSTS = ("127.0.0.1", "localhost")
# So estes arquivos sao servidos (nunca config.json, history.json, app.py...)
STATIC_PAGES = ("/", "/index.html")
PAGE_ALIAS = {"/share": "/share.html", "/dashboard": "/dashboard.html"}
# So o proprio PC (janela do app) pode usar estas rotas
LOCAL_ONLY_POST = ("/api/save_config", "/api/save_key", "/api/server_config", "/api/perf_interval",
                   "/api/custom_theme", "/api/custom_theme_delete", "/api/resolve_pending", "/api/export", "/api/ios_profile_save", "/api/undo", "/api/stats_clear", "/api/open_url", "/api/update_apply", "/api/restart_app", "/api/run_code", "/api/tunnel_start", "/api/tunnel_stop", "/api/tunnel_install")
PUBLIC_POST = ("/api/auth/login", "/api/auth/logout", "/api/guest/register", "/api/guest/code")
LOGIN_MAX_FAILS, LOGIN_LOCK_SECONDS = 5, 60
login_failures = {}   # ip -> [falhas, inicio]
httpd = None

PASSWORD_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # sem 0/O/1/I/L para ninguem errar ao digitar no celular

def generate_password():
    raw = "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(10))
    return raw[:5] + "-" + raw[5:]

def norm_password(p):
    return re.sub(r'[^A-Za-z0-9]', '', str(p or '')).upper()

def lan_subnets():
    """Prefixos /24 das redes em que este PC esta (ex.: '192.168.0.')."""
    out = []
    for ip in lan_ips():
        pre = ip.rsplit(".", 1)[0] + "."
        if pre not in out: out.append(pre)
    return out

_discover_cache = {"t": 0, "data": []}

def discover_servers():
    """Procura outros PCs com este app ligado na rede (testa /api/ping em cada IP dos /24 locais). Cache de 20 s."""
    if time.time() - _discover_cache["t"] < 20: return _discover_cache["data"]
    mine = set(lan_ips()); found = []; lock = threading.Lock()
    def probe(ip):
        try:
            with socket.create_connection((ip, PORT), timeout=0.5) as sk:
                sk.settimeout(1.0)
                sk.sendall(f"GET /api/ping HTTP/1.0\r\nHost: {ip}:{PORT}\r\n\r\n".encode())
                buf = b""
                while len(buf) < 4096:
                    ch = sk.recv(1024)
                    if not ch: break
                    buf += ch
            d = json.loads(buf.split(b"\r\n\r\n", 1)[1])
            if d.get("app") == "ai-thing":
                with lock: found.append({"url": f"http://{ip}:{PORT}", "ip": ip, "name": d.get("name", ip), "password_required": bool(d.get("password_required", True)), "remote_enabled": True})
        except Exception:
            pass
    ips = [p + str(n) for p in lan_subnets() for n in range(1, 255) if p + str(n) not in mine]
    with concurrent.futures.ThreadPoolExecutor(max_workers=96) as ex: list(ex.map(probe, ips))
    found.sort(key=lambda x: [int(n) for n in x["ip"].split(".")])
    _discover_cache.update(t=time.time(), data=found)
    return found

def lan_ips():
    """IPs deste PC na rede local (o primeiro e o da rota principal)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1)); ips.append(s.getsockname()[0]); s.close()   # nao envia nada, so descobre a rota
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith(("127.", "169.254.")): ips.append(ip)
    except Exception:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]

def device_name(ua):
    ua = ua or ""
    for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"), ("Windows", "Windows"), ("Macintosh", "Mac"), ("Linux", "Linux")):
        if key in ua: return name
    return "Dispositivo"

_icon_cache = {}
CUSTOM_ICON = os.path.join(BASE_DIR, "icons", "qwen.png")   # se existir, e o icone do app (janela, iPhone, aba do navegador)

def make_icon_png(size=180):
    """Icone do app: icons/qwen.png se existir; senao um raio branco sobre azul gerado sem bibliotecas externas."""
    if os.path.isfile(CUSTOM_ICON):
        try:
            with open(CUSTOM_ICON, "rb") as f: return f.read()
        except OSError: pass
    if size in _icon_cache: return _icon_cache[size]
    poly = [(58, 6), (22, 54), (46, 54), (38, 94), (78, 44), (54, 44)]   # raio em um quadro 100x100
    def inside(x, y):
        c = False
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
        return c
    bg, fg = (0, 86, 179), (255, 255, 255)
    rows = []
    for py in range(size):
        row = bytearray(b'\x00')
        for px in range(size):
            hits = sum(inside((px + (sx + .5) / 2) / size * 100, (py + (sy + .5) / 2) / size * 100) for sx in range(2) for sy in range(2))   # 2x2 suavizacao
            a = hits / 4
            row += bytes(int(bg[i] + (fg[i] - bg[i]) * a) for i in range(3))
        rows.append(bytes(row))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b'')
    _icon_cache[size] = png
    return png

def build_ca_profile(der, label=None):
    label = label or f"{APP_NAME} (certificado)"
    """Perfil .mobileconfig que instala a CA local no iPhone (depois e preciso ativar a confianca em Ajustes > Geral > Sobre)."""
    pid, cid = str(uuid.uuid4()).upper(), str(uuid.uuid4()).upper()
    payload = {
        "PayloadContent": [{
            "PayloadType": "com.apple.security.root", "PayloadVersion": 1, "PayloadUUID": cid,
            "PayloadIdentifier": f"com.thingmabobber.ca.{cid}", "PayloadDisplayName": "Thingmabobber Local CA",
            "PayloadCertificateFileName": "Thingmabobber-CA.cer", "PayloadContent": der,
        }],
        "PayloadType": "Configuration", "PayloadVersion": 1, "PayloadUUID": pid,
        "PayloadIdentifier": f"com.thingmabobber.cafile.{pid}", "PayloadDisplayName": label,
        "PayloadDescription": f"Permite abrir o {APP_NAME} pelo endereco https (necessario para rodar modelos no celular).",
        "PayloadOrganization": "Thingmabobber", "PayloadRemovalDisallowed": False,
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML)

def build_ios_profile(url, label=None):
    label = label or APP_NAME
    """Perfil .mobileconfig com um Web Clip: instala um icone na tela do iPhone que abre so o site."""
    pid, wid = str(uuid.uuid4()).upper(), str(uuid.uuid4()).upper()
    payload = {
        "PayloadContent": [{
            "PayloadType": "com.apple.webClip.managed", "PayloadVersion": 1, "PayloadUUID": wid,
            "PayloadIdentifier": f"com.thingmabobber.webclip.{wid}", "PayloadDisplayName": label,
            "Label": label, "URL": url, "FullScreen": True, "IsRemovable": True, "Precomposed": True,
            "Icon": make_icon_png(),
        }],
        "PayloadType": "Configuration", "PayloadVersion": 1, "PayloadUUID": pid,
        "PayloadIdentifier": f"com.thingmabobber.profile.{pid}", "PayloadDisplayName": label,
        "PayloadDescription": f"Adiciona um atalho para {url} na tela inicial.", "PayloadOrganization": "Thingmabobber",
        "PayloadRemovalDisallowed": False,
    }
    return plistlib.dumps(payload, fmt=plistlib.FMT_XML)

ERR_EN = {
    "Chave do Groq nao configurada": "Groq API key not set. Open Settings and paste your key.",
    "Biblioteca Groq nao instalada": "Groq library not installed (pip install groq).",
    "Nao consegui iniciar o Ollama": "Could not start Ollama. Is it installed?",
}
def localize_error(msg, lang):
    if lang == 'en':
        for k, v in ERR_EN.items():
            if str(msg).startswith(k): return v
    return str(msg)

class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    sniff_context = None   # se definido, a mesma porta atende HTTP e HTTPS (o navegador as vezes sobe "http://ip:8000" para "https://ip:8000" sozinho)

    def finish_request(self, request, client_address):
        ctx = self.sniff_context
        if ctx is not None:
            try:
                request.settimeout(10)
                first = request.recv(1, socket.MSG_PEEK)   # sem consumir: 0x16 = inicio de um aperto de mao TLS
                request.settimeout(None)
                if first == b"":
                    request.settimeout(10); request = ctx.wrap_socket(request, server_side=True); request.settimeout(None)
            except (ssl.SSLError, OSError):
                return
        super().finish_request(request, client_address)

class TLSServer(ThreadingServer):
    """Mesmo servidor, mas com TLS. O aperto de mao e feito na thread de cada conexao (um cliente travado nao trava os outros)."""
    ssl_context = None
    def get_request(self):
        sock, addr = super().get_request()
        return self.ssl_context.wrap_socket(sock, server_side=True, do_handshake_on_connect=False), addr
    def finish_request(self, request, client_address):
        try:
            request.settimeout(10); request.do_handshake(); request.settimeout(None)
        except (ssl.SSLError, OSError):
            return   # celular que ainda nao confia na CA, ou conexao em texto puro
        super().finish_request(request, client_address)
    def handle_error(self, request, client_address): pass

https_httpd = None

def start_https_server():
    """Sobe o HTTPS (porta 8443) ao lado do HTTP quando o acesso pela rede esta ligado. Sem o pacote cryptography fica so o HTTP."""
    global https_httpd
    if tls is None or not tls.HAS_CRYPTO:
        log("HTTPS", "Pacote 'cryptography' nao instalado: HTTPS desligado (pip install cryptography).", COLOR_YELLOW); return
    port = int(load_config().get("https_port", HTTPS_PORT))
    try:
        TLSServer.ssl_context = tls.server_context(CERTS_DIR, lan_ips())
        srv = TLSServer(("0.0.0.0", port), functools.partial(AppHandler, directory=BASE_DIR))
    except Exception as e:
        log("HTTPS", f"Nao consegui ligar o HTTPS na porta {port}: {e}", COLOR_RED); return
    https_httpd = srv
    log("HTTPS", "HTTPS ligado. Enderecos: " + ", ".join(f"https://{ip}:{port}" for ip in lan_ips()), COLOR_YELLOW)
    try: srv.serve_forever()
    finally:
        srv.server_close(); https_httpd = None

class AppHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')   # o celular nao pode ficar com uma versao antiga da pagina
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'no-referrer')
        super().end_headers()

    def log_message(self, format, *args): pass

    def send_json(self, obj, code=200, headers=None):
        body = json.dumps(obj).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body)))
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    # ---- quem esta chamando?
    def host_only(self):
        return urllib.parse.urlsplit('//' + (self.headers.get('Host') or '')).hostname or ''

    def is_tls(self):
        return isinstance(self.connection, ssl.SSLSocket)

    def is_desktop(self):
        """Janela do proprio app: conexao vinda do proprio PC E enderecada a 127.0.0.1/localhost (barra DNS rebinding)."""
        return self.client_address[0] in LOOPBACK_IPS and self.host_only() in LOCAL_HOSTS

    def is_root(self):
        """Sessao aberta pelo link secreto /owner-CODIGO: tem os mesmos poderes da janela do PC (configuracoes, aba Code, rodar codigo...)."""
        if getattr(self, '_root', None) is not None: return self._root
        cfg = load_config(); tok = self.get_token(); info = cfg["tokens"].get(tok) if tok else None
        self._root = bool(cfg.get("owner_link_enabled") and info and info.get("root")); return self._root

    def is_local(self):
        """Quem tem acesso total: a janela do PC ou uma sessao root."""
        return self.is_desktop() or self.is_root()

    def is_proxied(self):
        """Veio por um tunel/proxy instalado neste PC (cloudflared, tailscale funnel...): a conexao chega de 127.0.0.1, mas o Host e o do site publico."""
        return self.client_address[0] in LOOPBACK_IPS and self.host_only() not in LOCAL_HOSTS

    def client_ip(self):
        """IP do cliente para logs e limites. Atras de um proxy local, usa o cabecalho dele (so para isso, nunca para decidir permissao)."""
        ip = self.client_address[0]
        if self.is_proxied():
            for h in ('CF-Connecting-IP', 'X-Forwarded-For'):
                v = (self.headers.get(h) or '').split(',')[0].strip()
                if v and re.fullmatch(r'[0-9a-fA-F:.]{3,45}', v): return v
        return ip

    def is_secure_conn(self):
        return self.is_tls() or (self.is_proxied() and (self.headers.get('X-Forwarded-Proto') or '').lower() == 'https')

    def on_private_network(self):
        """Cliente direto da rede de casa (nunca algo que veio da internet por um tunel)."""
        if self.is_proxied(): return False
        try: return self.is_local() or ipaddress.ip_address(self.client_address[0]).is_private
        except ValueError: return False

    def auth_level(self):
        """('owner', None) = voce; ('guest', (id, conta)) = amigo; (None, None) = sem login."""
        if getattr(self, '_lvl', None) is not None: return self._lvl
        lvl = (None, None)
        if self.is_local(): lvl = ('owner', None)
        else:
            tok = self.get_token(); cfg = load_config(); info = cfg["tokens"].get(tok) if tok else None
            if info:
                if time.time() - info.get("last", 0) > 300:   # registra o "visto por ultimo" sem gravar a cada requisicao
                    info["last"] = time.time(); info["ip"] = self.client_ip(); save_config(cfg)
                lvl = ('owner', None)
            else:
                uid, u = guests.by_token(tok)
                if u: lvl = ('guest', (uid, u))
                elif (not cfg.get("internet_password_required", True)) if self.is_proxied() else (not cfg.get("password_required", True)): lvl = ('owner', None)   # "sem senha": um botao para a rede de casa, outro para a internet
        self._lvl = lvl; return lvl

    def get_token(self):
        t = self.headers.get('X-Auth-Token')
        if t: return t
        for part in (self.headers.get('Cookie') or '').split(';'):
            k, _, v = part.strip().partition('=')
            if k == 'thing_token': return v
        return ''

    def is_authed(self):
        return self.auth_level()[0] == "owner"

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def do_HEAD(self):
        self.send_response(405); self.end_headers()

    def serve_static(self, p):
        if p == '/apple-touch-icon.png':
            png = make_icon_png()
            self.send_response(200); self.send_header('Content-Type', 'image/png'); self.send_header('Content-Length', str(len(png))); self.end_headers()
            self.wfile.write(png); return
        alias = PAGE_ALIAS.get(p.rstrip('/') or '/')
        if alias:
            self.path = alias; log("HTTP", f"Pagina {p} aberta" + ("" if self.is_local() else f" por {self.client_ip()}"), COLOR_BLUE); return super().do_GET()
        icon_ok = p.startswith('/icons/') and '/' not in p[len('/icons/'):] and '\\' not in p and '..' not in p
        if p not in STATIC_PAGES and not icon_ok:
            self.send_response(404); self.end_headers(); return
        if p in STATIC_PAGES:
            log("HTTP", "Interface carregada" + ("" if self.is_local() else f" (dispositivo remoto {self.client_address[0]})"), COLOR_BLUE)
        super().do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        self.query = urllib.parse.parse_qs(parsed.query); self.path = p = parsed.path
        if p.startswith('/owner-'):
            return self.owner_login(p[len('/owner-'):])
        if not p.startswith('/api/'):
            return self.serve_static(p)
        local = self.is_local()
        if p == '/api/tunnel':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json({**tunnel_state, "cloudflared": bool(find_cloudflared()), "tailscale": bool(shutil.which("tailscale")), "port": PORT})
        if p == '/api/update_check':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json(check_update())
        if p in ('/api/ca_profile', '/api/ca_cer'):   # a CA e publica (so o certificado, sem chave); so rede privada
            if tls is None or not tls.HAS_CRYPTO: return self.send_json({"error": "no_crypto"}, 503)
            if not self.on_private_network(): return self.send_json({"error": "forbidden"}, 403)
            der = tls.ca_der(CERTS_DIR)
            if p == '/api/ca_cer':
                self.send_response(200); self.send_header('Content-Type', 'application/x-x509-ca-cert'); self.send_header('Content-Length', str(len(der)))
                self.send_header('Content-Disposition', 'attachment; filename="Thingmabobber-CA.cer"'); self.end_headers(); self.wfile.write(der); return
            body = build_ca_profile(der)
            log("HTTPS", f"Perfil do certificado enviado para {self.client_address[0]}", COLOR_GREEN)
            self.send_response(200); self.send_header('Content-Type', 'application/x-apple-aspen-config'); self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Disposition', 'attachment; filename="' + APP_NAME + '-Certificado.mobileconfig"'); self.end_headers(); self.wfile.write(body); return
        if p == '/api/ping':   # publico: so diz que isto e o app e se pede senha
            cfg = load_config()
            if self.is_proxied(): return self.send_json({"app": "ai-thing"})   # pela internet nao entrega o nome do PC nem as configuracoes da rede de casa
            return self.send_json({"app": "ai-thing", "name": socket.gethostname(), "password_required": cfg.get("password_required", True)})
        if p == '/api/discover':   # publico: lista de servidores por perto (nomes e enderecos da propria rede)
            if not self.on_private_network(): return self.send_json({"error": "forbidden"}, 403)
            return self.send_json({"servers": discover_servers()})
        if p == '/api/auth/status':
            cfg = load_config(); lvl, gu = self.auth_level()
            info = {"local": local, "root": self.is_root(), "authed": lvl is not None, "role": lvl, "remote_enabled": cfg["remote_enabled"], "allow_remote_code": cfg["allow_remote_code"],
                    "password_required": cfg.get("internet_password_required", True) if self.is_proxied() else cfg.get("password_required", True), "version": VERSION, "app_name": APP_NAME,
                    "https_port": int(cfg.get("https_port", HTTPS_PORT)) if https_httpd is not None else 0, "secure": self.is_secure_conn(),
                    "share_open": bool(guests.settings["open"]), "invite_required": bool(guests.settings["invite_code"])}
            if lvl == 'guest': info["guest"] = self.guest_info(*gu)
            return self.send_json(info)
        lvl, gu = self.auth_level()
        if lvl is None:
            return self.send_json({"error": "unauthorized"}, 401)
        if lvl == 'guest':
            return self.guest_get(p, gu)
        if p.startswith('/api/admin/'):
            return self.admin_get(p)
        if p == '/api/usage':
            return self.send_json(load_config().get("usage", {}))
        if p == '/api/check_pending':
            return self.send_json({"cmd": pending_command["cmd"] if local else ""})   # so o PC aprova comandos
        if p == '/api/history':
            return self.send_json(load_history())
        if p == '/api/state':
            st = load_state()
            return self.send_json(st if local else {"memories": st.get("memories", [])})   # preferencias da interface sao de cada aparelho
        if p == '/api/custom_themes':
            return self.send_json(list_custom_themes())
        if p == '/api/stats':
            try: days = max(1, min(365, int((self.query.get('days') or ['30'])[0])))
            except ValueError: days = 30
            return self.send_json(build_stats(days))
        if p == '/api/config_status':
            cfg = load_config()
            return self.send_json({"groq_key_saved": bool(cfg.get("groq_api_key")), "exa_key_saved": bool(exa_api_key(cfg)), "search_provider": cfg.get("search_provider", "auto"), "exa_type": cfg.get("exa_type", "lite"), "search_results": max_results(), "search_daily_limit": cfg.get("search_daily_limit", 100), "exa_today": exa_searches_today(), "workdir": get_workdir(cfg) if local else "", "default_workdir": BASE_DIR if local else ""})
        if p == '/api/models_status':
            tags = ollama_tags(); running = tags is not None
            used, total, _ = get_gpu_metrics()
            loaded = [{"name": m["name"], "size": m.get("size", 0), "size_vram": m.get("size_vram", 0)} for m in ollama_ps()] if running else []
            return self.send_json({"running": running, "loaded": loaded, "vram_total": total, "vram_used": used,
                                   "installed": [m["name"] for m in tags] if running else None,
                                   "installed_sizes": {m["name"]: m.get("size", 0) for m in tags} if running else {}})
        if p == '/api/model_info':
            name = (self.query.get('name') or [''])[0]
            if not re.fullmatch(r'[\w.:\-/]+', name): return self.send_json({"error": "nome invalido"}, 400)
            return self.send_json(get_model_info(name))
        if p == '/api/metrics':
            vram_used, vram_total, gpu_util = get_gpu_metrics()
            vram_pct = None
            vram_warn = ''
            if vram_used is not None and vram_total:
                vram_pct = round(100 * vram_used / vram_total, 1)
                if vram_used >= vram_total - 300: vram_warn = f'VRAM no limite ({vram_pct}%)'
                elif vram_used > VRAM_WARN_MB: vram_warn = f'VRAM alta ({vram_used / 1024:.1f} GB)'
            return self.send_json({
                "vram_used": vram_used, "vram_total": vram_total, "vram": vram_used,
                "vram_pct": vram_pct, "gpu": gpu_util, "vram_warn": vram_warn, "vram_warn_mb": VRAM_WARN_MB,
                "generation_active": generation_active, "alert": alert_state
            })
        if p == '/api/server_info':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            return self.send_json({
                "remote_enabled": cfg["remote_enabled"], "allow_remote_code": cfg["allow_remote_code"], "password": cfg["password"], "password_required": cfg.get("password_required", True),
                "internet_password_required": cfg.get("internet_password_required", True), "owner_link_enabled": bool(cfg.get("owner_link_enabled")), "owner_code": cfg.get("owner_code", ""),
                "port": PORT, "configured_port": cfg.get("port", PORT),
                "listening": f"{'0.0.0.0' if cfg['remote_enabled'] else '127.0.0.1'}:{PORT}",
                "addresses": [f"http://{ip}:{PORT}" for ip in lan_ips()],
                "https_addresses": [f"https://{ip}:{int(cfg.get('https_port', HTTPS_PORT))}" for ip in lan_ips()] if (https_httpd is not None) else [],
                "devices": [{"id": t[:8], "name": i.get("name", ""), "ip": i.get("ip", ""), "created": i.get("created", 0), "last": i.get("last", 0)} for t, i in cfg["tokens"].items()],
            })
        if p == '/api/ios_profile':
            if local:
                host = (self.query.get('host') or [''])[0]
                if not re.fullmatch(r'[\w.\-]+', host or ''): host = (lan_ips() or ['127.0.0.1'])[0]
                base = f"https://{host}:{int(load_config().get('https_port', HTTPS_PORT))}" if (self.query.get('https') or [''])[0] == '1' and https_httpd is not None else f"http://{host}:{PORT}"
            else:
                base = ("https://" if self.is_tls() else "http://") + (self.headers.get('Host') or f"127.0.0.1:{PORT}")   # o mesmo endereco que o celular usou para abrir o site
            body = build_ios_profile(base + "/index.html")
            log("IPHONE", f"Perfil gerado para {base}/index.html", COLOR_GREEN)
            self.send_response(200); self.send_header('Content-Type', 'application/x-apple-aspen-config'); self.send_header('Content-Length', str(len(body)))
            self.send_header('Content-Disposition', 'attachment; filename="' + APP_NAME + '.mobileconfig"'); self.end_headers()
            self.wfile.write(body); return
        self.send_json({"error": "rota desconhecida"}, 404)

    def do_POST(self):
        p = urllib.parse.urlsplit(self.path).path; self.path = p
        length = int(self.headers.get('Content-Length') or 0)
        if length > MAX_BODY_BYTES: return self.send_json({"error": "Requisicao grande demais."}, 413)
        post_data = self.rfile.read(length)
        origin = self.headers.get('Origin')
        if origin and urllib.parse.urlsplit(origin).netloc != (self.headers.get('Host') or ''):
            log("SEGURANCA", f"Requisicao bloqueada: origem {origin} diferente do host", COLOR_RED)
            return self.send_json({"error": "origin"}, 403)   # outro site tentando usar o servidor
        local = self.is_local()
        lvl, gu = self.auth_level()
        if p not in PUBLIC_POST and lvl is None:
            return self.send_json({"error": "unauthorized"}, 401)
        if lvl == 'guest' and p not in PUBLIC_POST:
            return self.guest_post(p, post_data, gu)
        if p in LOCAL_ONLY_POST and not local:
            log("SEGURANCA", f"Rota {p} recusada para dispositivo remoto {self.client_address[0]}", COLOR_RED)
            return self.send_json({"error": "local_only"}, 403)
        quiet = ('/api/chat', '/api/history', '/api/state')
        if p not in quiet: log("API", f"POST {p}", COLOR_BLUE)
        try:
            data = {} if p == '/api/chat' else json.loads(post_data or b'{}')
        except ValueError:
            return self.send_json({"error": "json invalido"}, 400)

        if p == '/api/auth/login':
            return self.handle_login(data)
        if p in ('/api/guest/register', '/api/guest/code'):
            return self.guest_register(p, data)
        if p.startswith('/api/admin/'):
            return self.admin_post(p, data)

        if p == '/api/auth/logout':
            cfg = load_config(); tok = self.get_token()
            if tok in cfg["tokens"]: del cfg["tokens"][tok]; save_config(cfg); log("AUTH", "Dispositivo desconectado", COLOR_YELLOW)
            guests.drop_token(tok)
            return self.send_json({"ok": True}, headers={"Set-Cookie": "thing_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})

        if p == '/api/ios_profile_save':   # salva o perfil na pasta Downloads do PC (para mandar por AirDrop/e-mail)
            host = str(data.get("host") or "")
            if not re.fullmatch(r'[\w.\-]+', host): host = (lan_ips() or ['127.0.0.1'])[0]
            folder = os.path.join(os.path.expanduser("~"), "Downloads"); os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, APP_NAME + "-iPhone.mobileconfig"); n = 1
            while os.path.exists(path):
                path = os.path.join(folder, f"{APP_NAME}-iPhone ({n}).mobileconfig"); n += 1
            with open(path, 'wb') as f: f.write(build_ios_profile(f"http://{host}:{PORT}/index.html"))
            log("IPHONE", f"Perfil salvo em {path}", COLOR_GREEN)
            return self.send_json({"ok": True, "path": path})

        if p == '/api/server_config':
            cfg = load_config(); restart = False; port_changed = False
            if "remote_enabled" in data and bool(data["remote_enabled"]) != cfg["remote_enabled"]:
                cfg["remote_enabled"] = bool(data["remote_enabled"]); restart = True
            if "allow_remote_code" in data: cfg["allow_remote_code"] = bool(data["allow_remote_code"])
            for key, what in (("password_required", "rede de casa"), ("internet_password_required", "internet")):
                if key in data:
                    new = bool(data[key])
                    if new and not cfg.get(key, True):   # senha religada depois de desligada: derruba todos os aparelhos na hora
                        cfg["tokens"] = {}; log("AUTH", f"Senha da {what} religada: todos os dispositivos foram desconectados.", COLOR_YELLOW)
                    cfg[key] = new
                    log("AUTH", f"Senha da {what}: " + ("exigida" if new else "DESLIGADA (entra sem senha)") + ".", COLOR_GREEN if new else COLOR_YELLOW)
            if any(k in data for k in ("owner_link_enabled", "owner_code", "owner_code_random")):
                was, old = bool(cfg.get("owner_link_enabled")), cfg.get("owner_code", "")
                if "owner_link_enabled" in data: cfg["owner_link_enabled"] = bool(data["owner_link_enabled"])
                if data.get("owner_code_random"): cfg["owner_code"] = secrets.token_urlsafe(12)
                elif "owner_code" in data:
                    code = str(data["owner_code"]).strip()
                    if not re.fullmatch(r"[A-Za-z0-9_\-]{5,40}", code): return self.send_json({"error": "O codigo deve ter de 5 a 40 letras, numeros, - ou _."}, 400)
                    cfg["owner_code"] = code
                if cfg["owner_link_enabled"] and not cfg.get("owner_code"): cfg["owner_code"] = secrets.token_urlsafe(12)
                if (was and not cfg["owner_link_enabled"]) or cfg.get("owner_code") != old:   # desligou ou trocou o codigo: sessoes root caem na hora
                    n = len(cfg["tokens"]); cfg["tokens"] = {t: i for t, i in cfg["tokens"].items() if not i.get("root")}
                    if n != len(cfg["tokens"]): log("AUTH", "Sessoes root encerradas.", COLOR_YELLOW)
                log("AUTH", "Link secreto /owner-: " + ("LIGADO" if cfg["owner_link_enabled"] else "desligado"), COLOR_YELLOW if cfg["owner_link_enabled"] else COLOR_GREEN)
            if data.get("regenerate_password"):
                cfg["password"] = generate_password(); cfg["tokens"] = {}
                log("AUTH", "Nova senha gerada; todos os dispositivos foram desconectados.", COLOR_YELLOW)
            if data.get("revoke_all"): cfg["tokens"] = {}; log("AUTH", "Todos os dispositivos desconectados.", COLOR_YELLOW)
            if data.get("revoke"):
                for t in [t for t in cfg["tokens"] if t.startswith(str(data["revoke"]))]: del cfg["tokens"][t]
                log("AUTH", "Dispositivo desconectado.", COLOR_YELLOW)
            if "port" in data:
                port = int(data["port"])
                if not 1024 <= port <= 65535: return self.send_json({"error": "A porta deve estar entre 1024 e 65535."}, 400)
                port_changed = port != PORT; cfg["port"] = port
            save_config(cfg)
            log("SERVIDOR", f"Configuracao do servidor salva (acesso remoto {'LIGADO' if cfg['remote_enabled'] else 'desligado'})", COLOR_GREEN)
            self.send_json({"ok": True, "restart_required": port_changed})
            if restart: restart_server()
            return

        if p in ('/api/save_config', '/api/save_key'):
            cfg = load_config()
            if data.get("workdir") and not os.path.isdir(data["workdir"]):
                log("CONFIG", f"Pasta de trabalho invalida: {data['workdir']}", COLOR_RED)
                return self.send_json({"error": "Pasta de trabalho nao existe."}, 400)
            if data.get("search_provider") not in (None, "auto", "exa", "duckduckgo") or data.get("exa_type") not in (None, *EXA_TYPES):
                return self.send_json({"error": "Opcao de pesquisa invalida."}, 400)
            for k, lo, hi in (("search_results", 1, 10), ("search_daily_limit", 0, 100000)):
                if k in data:
                    try: data[k] = max(lo, min(hi, int(data[k])))
                    except (TypeError, ValueError): return self.send_json({"error": "Opcao de pesquisa invalida."}, 400)
            for k in ("groq_api_key", "exa_api_key", "workdir", "search_provider", "exa_type", "search_results", "search_daily_limit"):
                if k in data: cfg[k] = data[k].strip() if k.endswith("_key") else data[k]
            save_config(cfg)
            secrets_sent = [k for k in ("groq_api_key", "exa_api_key") if k in data]
            log("CONFIG", "Configuracoes salvas (" + ", ".join([k for k in data if k not in secrets_sent] + [f"chave {k.split('_')[0]}" for k in secrets_sent]) + ")", COLOR_GREEN)
            return self.send_json({"ok": True})

        if p == '/api/history':
            save_history(data)
            log("HISTORICO", f"{len(data)} chat(s) salvos", COLOR_GRAY)
            return self.send_json({"ok": True})

        if p == '/api/state':
            if not local:   # celular: so as memorias; o resto das preferencias fica no aparelho
                st = load_state(); st["memories"] = data.get("memories", st.get("memories", [])); data = st
            save_state(data)
            return self.send_json({"ok": True})

        if p == '/api/custom_theme':
            name = safe_theme_name(data.get("name"))
            os.makedirs(THEMES_DIR, exist_ok=True)
            path = os.path.join(THEMES_DIR, name + ".json")
            _write_json(path, data.get("theme", {}))
            log("TEMA", f"Tema '{name}' salvo em {path}", COLOR_GREEN)
            return self.send_json({"ok": True, "name": name, "path": path})

        if p == '/api/custom_theme_delete':
            name = safe_theme_name(data.get("name"))
            path = os.path.join(THEMES_DIR, name + ".json")
            if os.path.exists(path): os.remove(path); log("TEMA", f"Tema '{name}' apagado", COLOR_YELLOW)
            return self.send_json({"ok": True})

        if p == '/api/extract_text':
            try:
                text, truncated, pages = extract_file_text(str(data.get("filename", "")), base64.b64decode(data.get("b64", "")))
            except Exception as e:
                return self.send_json({"error": str(e)}, 400)
            log("ARQUIVO", f"{data.get('filename')}: {len(text)} caracteres" + (" (cortado)" if truncated else ""), COLOR_GRAY)
            return self.send_json({"text": text, "truncated": truncated, "chars": len(text), "pages": pages})

        if p == '/api/undo':
            try: return self.send_json({"ok": True, "message": do_undo(str(data.get("id", "")))})
            except Exception as e: return self.send_json({"error": str(e)}, 400)

        if p == '/api/run_code':
            return self.send_json(run_code(data.get("lang"), data.get("code"), bool(data.get("analyze")), bool(data.get("install"))))
        if p == '/api/update_apply':
            return self.send_json(apply_update())
        if p == '/api/tunnel_install': return self.send_json(install_cloudflared())
        if p == '/api/tunnel_start': return self.send_json(start_tunnel())
        if p == '/api/tunnel_stop': stop_tunnel(); return self.send_json({"ok": True})
        if p == '/api/restart_app':
            self.send_json({"ok": True}); threading.Thread(target=restart_app, daemon=True).start(); return
        if p == '/api/stats_clear':
            _write_json(STATS_FILE, {"events": []}); log("STATS", "Estatisticas apagadas.", COLOR_YELLOW)
            return self.send_json({"ok": True})

        if p == '/api/open_url':   # abre um link no navegador do PC (a janela do app nao navega para fora)
            url = str(data.get("url", ""))
            if not re.match(r'^https?://', url, re.I): return self.send_json({"error": "url invalida"}, 400)
            webbrowser.open(url); return self.send_json({"ok": True})

        if p == '/api/resolve_pending':
            approved = data.get("approved", False)
            log("PERMISSAO", "Aprovado pelo usuario" if approved else "Negado pelo usuario", COLOR_GREEN if approved else COLOR_RED)
            if pending_command["resolve"]:
                pending_command["resolve"](approved)
            return self.send_json({"ok": True})

        if p == '/api/stop':
            log("STOP", "Parada solicitada pelo usuario", COLOR_YELLOW)
            stop_generation_flag.set()
            return self.send_json({"ok": True})

        if p == '/api/start':
            return self.send_json({"running": start_ollama()})

        if p == '/api/model_start':
            model = data.get("model", "")
            try:
                if not start_ollama(): raise Exception("Ollama nao esta rodando.")
                log("MODELO", f"Carregando {model}...", COLOR_CYAN)
                try: nctx = int(data.get("num_ctx") or 0)
                except (TypeError, ValueError): nctx = 0
                t = time.time(); ollama_load(model, nctx or None)
                log("MODELO", f"{model} carregado em {time.time() - t:.1f}s", COLOR_GREEN)
                return self.send_json({"ok": True})
            except Exception as e:
                log("MODELO", f"Falha ao carregar {model}: {e}", COLOR_RED)
                return self.send_json({"ok": False, "error": str(e)}, 500)

        if p == '/api/model_stop':
            model = data.get("model", "")
            if generation_active and active_model == model: stop_generation_flag.set()
            try:
                ollama_unload(model)
                log("MODELO", f"{model} desligado.", COLOR_YELLOW)
                return self.send_json({"ok": True})
            except Exception as e:
                log("MODELO", f"Falha ao desligar {model}: {e}", COLOR_RED)
                return self.send_json({"ok": False, "error": str(e)}, 500)

        if p == '/api/perf_interval':
            ms = max(50, min(5000, int(data.get("ms", 50))))
            if ms != gpu_interval_ms or not gpu_proc: start_gpu_stream(ms)
            return self.send_json({"ok": True, "ms": ms})

        if p == '/api/export':
            name = re.sub(r'[^\w.\- ]', '_', data.get("filename", "chat.txt"))
            folder = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(folder, exist_ok=True)
            base, ext = os.path.splitext(name); path = os.path.join(folder, name); n = 1
            while os.path.exists(path):
                path = os.path.join(folder, f"{base} ({n}){ext}"); n += 1
            with open(path, 'wb') as f: f.write(base64.b64decode(data.get("b64", "")))
            log("EXPORTAR", f"Salvo em {path}", COLOR_GREEN)
            return self.send_json({"ok": True, "path": path})

        if p == '/api/chat':
            return self.handle_chat(json.loads(post_data), local)

        self.send_json({"error": "rota desconhecida"}, 404)

    # ------------------------------------------------------------ amigos (/share) e painel (/dashboard)
    GUEST_ERRORS = {"closed": ("Os cadastros estao fechados no momento.", 403), "invite": ("Codigo de convite incorreto.", 403), "name": ("Use de 3 a 20 letras, numeros, ponto, hifen ou _.", 400),
                    "taken": ("Esse nome ja esta em uso.", 409), "full": ("O limite de contas foi atingido.", 403), "rate": ("Muitas contas criadas deste lugar. Tente mais tarde.", 429), "code": ("Codigo invalido ou vencido.", 403)}

    def guest_cookie(self, tok):
        return {"Set-Cookie": f"thing_token={tok}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax" + ("; Secure" if self.is_secure_conn() else "")}

    def guest_info(self, uid, u):
        on, why = guests.state(u); pol = guests.policy(u)
        used = guests_mod.usage_by_user([e for e in _read_json(STATS_FILE, {"events": []}).get("events", []) if e.get("user") == uid], {uid: u})[uid]["today"]
        return {"name": u["name"], "enabled": on, "reason": why, "blocked_features": sorted(pol["blocked_features"]), "blocked_models": sorted(pol["blocked_models"]),
                "daily_limit": pol["daily_limit"], "used_today": used, "notice": guests.notice_for(u)}

    def guest_register(self, p, data):
        ip = self.client_ip(); now = time.time()
        recent = [t for t in login_recent_fails if now - t < 600]
        try:
            if p == '/api/guest/code': uid, tok = guests.login_with_code(data.get("name"), data.get("code"), ip, self.headers.get('User-Agent'))
            else: uid, tok = guests.register(data.get("name"), ip, self.headers.get('User-Agent'), data.get("invite"))
        except ValueError as e:
            msg, code = self.GUEST_ERRORS.get(str(e), ("Nao foi possivel criar a conta.", 400))
            if str(e) == "code": login_recent_fails.append(now)
            return self.send_json({"error": str(e), "message": msg}, code)
        log("AMIGOS", f"Conta {'conectada' if p.endswith('code') else 'criada'}: {guests.data['users'][uid]['name']} ({ip})", COLOR_GREEN)
        return self.send_json({"ok": True, "name": guests.data["users"][uid]["name"]}, headers=self.guest_cookie(tok))

    def guest_get(self, p, gu):
        uid, u = gu; on, why = guests.state(u)
        if not on: return self.send_json({"error": "disabled", "reason": why, "message": u.get("message") or guests.settings.get("shutdown_msg", "")}, 403)
        if p == '/api/history': return self.send_json(_read_json(guests.history_file(uid), {}))
        if p == '/api/state': return self.send_json({"memories": _read_json(guests.state_file(uid), {}).get("memories", [])})
        if p == '/api/models_status':
            tags = ollama_tags(); running = tags is not None
            return self.send_json({"running": running, "loaded": [], "vram_total": 0, "vram_used": 0, "installed": [m["name"] for m in tags] if running else None, "installed_sizes": {m["name"]: m.get("size", 0) for m in tags} if running else {}})
        if p == '/api/config_status': return self.send_json({"guest": True, "groq_key_saved": False, "exa_key_saved": False})
        if p == '/api/model_info':
            name = (self.query.get('name') or [''])[0]
            if not re.fullmatch(r'[\w.:\-/]+', name): return self.send_json({"error": "nome invalido"}, 400)
            return self.send_json(get_model_info(name))
        if p == '/api/metrics': return self.send_json({"vram_used": None, "vram_total": None, "vram": None, "gpu": None, "vram_warn": "", "generation_active": False, "alert": {"id": 0}})
        if p == '/api/usage': return self.send_json({})
        if p == '/api/check_pending': return self.send_json({"cmd": ""})
        if p == '/api/custom_themes': return self.send_json([])
        return self.send_json({"error": "forbidden"}, 403)

    def guest_post(self, p, post_data, gu):
        uid, u = gu; on, why = guests.state(u)
        if not on: return self.send_json({"error": "disabled", "reason": why, "message": u.get("message") or guests.settings.get("shutdown_msg", "")}, 403)
        if p == '/api/auth/logout':
            guests.drop_token(self.get_token()); return self.send_json({"ok": True}, headers={"Set-Cookie": "thing_token=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
        try: data = json.loads(post_data or b'{}')
        except ValueError: return self.send_json({"error": "json invalido"}, 400)
        pol = guests.policy(u)
        if p == '/api/chat': return self.handle_chat(data, False, guest=gu)
        if p == '/api/history':
            if len(post_data) > 12 * 1024 * 1024: return self.send_json({"error": "Historico grande demais."}, 413)
            if isinstance(data, dict): _write_json(guests.history_file(uid), data)
            return self.send_json({"ok": True})
        if p == '/api/state':
            mem = data.get("memories", []) if isinstance(data, dict) else []
            _write_json(guests.state_file(uid), {"memories": [str(m)[:500] for m in mem][:100]}); return self.send_json({"ok": True})
        if p == '/api/stop':
            ev = stop_events.get(uid)
            if ev: ev.set()
            return self.send_json({"ok": True})
        if p == '/api/extract_text':
            if "files" in pol["blocked_features"]: return self.send_json({"error": "Anexar arquivos esta bloqueado na sua conta."}, 403)
            try: text, truncated, pages = extract_file_text(str(data.get("filename", "")), base64.b64decode(data.get("b64", "")))
            except Exception as e: return self.send_json({"error": str(e)}, 400)
            return self.send_json({"text": text, "truncated": truncated, "chars": len(text), "pages": pages})
        return self.send_json({"error": "forbidden"}, 403)

    def admin_overview(self):
        now = time.time(); events = _read_json(STATS_FILE, {"events": []}).get("events", [])
        use = guests_mod.usage_by_user(events, guests.data["users"], now); users = []
        for uid, u in guests.data["users"].items():
            on, why = guests.state(u, now); pol = guests.policy(u); o = use[uid]
            users.append({"id": uid, "name": u["name"], "created": u.get("created", 0), "last": u.get("last", 0), "online": now - u.get("last", 0) < 45, "enabled": on, "reason": why,
                          "disable_in": max(0, int(u["disable_at"] - now)) if u.get("disable_at") else None, "message": u.get("message", ""), "devices": len(u.get("tokens", {})),
                          "blocked_models": sorted(pol["blocked_models"]), "blocked_features": sorted(pol["blocked_features"]), "daily_limit": pol["daily_limit"], "own_limit": u.get("daily_limit"),
                          "active": guest_active.get(uid, 0), "requests": o["requests"], "today": o["today"], "tokens": o["tokens"], "seconds": round(o["seconds"], 1), "models": o["models"], "last_model": o["last_model"], "last_use": o["last_ts"], "note": u.get("note", "")})
        users.sort(key=lambda x: (-x["online"], -x["last"]))
        tags = ollama_tags()
        st = guests.settings
        return {"now": now, "users": users, "features": guests_mod.FEATURES, "installed": sorted(m["name"] for m in tags) if tags else [],
                "settings": {k: st[k] for k in ("open", "invite_code", "max_users", "default_blocked_features", "default_blocked_models", "daily_limit", "per_minute", "max_parallel", "ctx_cap", "max_tokens", "banner")},
                "global": {"off": st["global_off"], "shutdown_in": max(0, int(st["shutdown_at"] - now)) if st["shutdown_at"] else None, "message": st.get("shutdown_msg", "")},
                "ollama": build_stats(7)["ollama"], "app_name": APP_NAME, "tunnel": dict(tunnel_state)}

    def admin_get(self, p):
        if p == '/api/admin/overview': return self.send_json(self.admin_overview())
        return self.send_json({"error": "rota desconhecida"}, 404)

    def admin_post(self, p, data):
        try: secs = max(0, min(3600, int(data.get("seconds") or 0)))
        except (TypeError, ValueError): secs = 0
        msg = str(data.get("message") or "")[:300]
        if p == '/api/admin/global':
            a = data.get("action")
            if a == "shutdown_all": guests.shutdown_all(secs, msg); log("AMIGOS", f"Desligar todos ({'em %d s' % secs if secs else 'agora'})", COLOR_YELLOW)
            elif a == "enable_all": guests.enable_all(); log("AMIGOS", "Todos ligados", COLOR_GREEN)
            elif a == "cancel_shutdown":
                with guests.lock: guests.settings["shutdown_at"] = None; guests.save()
            else: return self.send_json({"error": "acao desconhecida"}, 400)
            return self.send_json({"ok": True, **self.admin_overview()})
        if p == '/api/admin/settings':
            st = guests.settings
            with guests.lock:
                for k, typ, lo, hi in (("max_users", int, 1, 200), ("daily_limit", int, 0, 100000), ("per_minute", int, 1, 120), ("max_parallel", int, 1, 16), ("ctx_cap", int, 1024, 262144), ("max_tokens", int, 64, 32768)):
                    if k in data:
                        try: st[k] = max(lo, min(hi, typ(data[k])))
                        except (TypeError, ValueError): pass
                if "open" in data: st["open"] = bool(data["open"])
                if "invite_code" in data: st["invite_code"] = str(data["invite_code"]).strip()[:40]
                if "banner" in data: st["banner"] = str(data["banner"])[:300]
                for k in ("default_blocked_features", "default_blocked_models"):
                    if isinstance(data.get(k), list): st[k] = [str(x)[:80] for x in data[k]][:200]
                guests.save()
            return self.send_json({"ok": True, **self.admin_overview()})
        if p == '/api/admin/user':
            uid = str(data.get("id") or ""); a = data.get("action")
            if uid not in guests.data["users"]: return self.send_json({"error": "amigo nao encontrado"}, 404)
            u = guests.data["users"][uid]
            if a == "disable": guests.shutdown_user(uid, secs, msg)
            elif a == "enable": guests.enable_user(uid)
            elif a == "kick":
                with guests.lock: u["tokens"] = {}; guests._reindex(); guests.save()
            elif a == "delete": guests.delete(uid)
            elif a == "code": return self.send_json({"ok": True, "code": guests.new_code(uid)})
            elif a == "message":
                with guests.lock: u["message"] = msg; guests.save()
            elif a == "set":
                with guests.lock:
                    if isinstance(data.get("blocked_features"), list): u["blocked_features"] = [f for f in data["blocked_features"] if f in guests_mod.FEATURES]
                    if isinstance(data.get("blocked_models"), list): u["blocked_models"] = [str(x)[:80] for x in data["blocked_models"]][:200]
                    if "daily_limit" in data: u["daily_limit"] = None if data["daily_limit"] in (None, "") else max(0, int(data["daily_limit"]))
                    if "note" in data: u["note"] = str(data["note"])[:120]
                    guests.save()
            else: return self.send_json({"error": "acao desconhecida"}, 400)
            log("AMIGOS", f"{a}: {u['name']}", COLOR_YELLOW)
            return self.send_json({"ok": True, **self.admin_overview()})
        if p == '/api/admin/apply_defaults':   # aplica os bloqueios padrao a todos os amigos
            with guests.lock:
                for u in guests.data["users"].values(): u["blocked_features"] = list(guests.settings["default_blocked_features"]); u["blocked_models"] = list(guests.settings["default_blocked_models"])
                guests.save()
            return self.send_json({"ok": True, **self.admin_overview()})
        return self.send_json({"error": "rota desconhecida"}, 404)

    def rate_locked(self, ip, now):
        """Segundos de espera se este IP (ou o conjunto de todos) errou demais; 0 se pode tentar."""
        recent = [t for t in login_recent_fails if now - t < 600]; login_recent_fails[:] = recent
        if len(recent) >= 30: return 300
        f = login_failures.get(ip)
        if f and f[0] >= LOGIN_MAX_FAILS and now - f[1] < LOGIN_LOCK_SECONDS: return int(LOGIN_LOCK_SECONDS - (now - f[1]))
        return 0

    def rate_fail(self, ip, now):
        login_recent_fails.append(now); f = login_failures.get(ip)
        if not f or now - f[1] >= LOGIN_LOCK_SECONDS: f = login_failures[ip] = [0, now]
        f[0] += 1

    def owner_login(self, code):
        """GET /owner-CODIGO: se o link secreto estiver ligado e o codigo bater, esta sessao vira "root"."""
        ip, now = self.client_ip(), time.time(); cfg = load_config()
        if self.rate_locked(ip, now): self.send_response(429); self.end_headers(); return
        real = cfg.get("owner_code") or ""
        if not (cfg.get("owner_link_enabled") and real and hmac.compare_digest(code.encode(), real.encode())):
            self.rate_fail(ip, now); log("SEGURANCA", f"Link /owner- recusado ({ip})", COLOR_RED)
            self.send_response(404); self.end_headers(); return
        login_failures.pop(ip, None)
        tok = secrets.token_hex(24)
        cfg["tokens"][tok] = {"ip": ip, "name": "Acesso root (" + device_name(self.headers.get('User-Agent')) + ")", "created": now, "last": now, "root": True}
        while len(cfg["tokens"]) > 20: del cfg["tokens"][min(cfg["tokens"], key=lambda t: cfg["tokens"][t]["last"])]
        save_config(cfg); log("AUTH", f"ACESSO ROOT pelo link secreto: {ip}", COLOR_YELLOW)
        self.send_response(302); self.send_header('Location', '/'); self.send_header('Cache-Control', 'no-store')
        for k, v in self.guest_cookie(tok).items(): self.send_header(k, v)
        self.end_headers()

    def handle_login(self, data):
        ip, now = self.client_ip(), time.time()
        recent = [t for t in login_recent_fails if now - t < 600]; login_recent_fails[:] = recent
        if len(recent) >= 30:   # muitas senhas erradas, de qualquer IP, em 10 min: trava tudo por um tempo (protege contra tentativas pela internet)
            log("AUTH", "Login travado: muitas tentativas no total", COLOR_RED)
            return self.send_json({"error": "locked", "wait": 300}, 429)
        fails = login_failures.get(ip)
        if fails and fails[0] >= LOGIN_MAX_FAILS and now - fails[1] < LOGIN_LOCK_SECONDS:
            wait = int(LOGIN_LOCK_SECONDS - (now - fails[1]))
            log("AUTH", f"Login bloqueado para {ip} (muitas tentativas)", COLOR_RED)
            return self.send_json({"error": "locked", "wait": wait}, 429)
        cfg = load_config()
        given, real = norm_password(data.get("password")), norm_password(cfg["password"])
        if given and hmac.compare_digest(given, real):
            login_failures.pop(ip, None)
            tok = secrets.token_hex(24)
            cfg["tokens"][tok] = {"ip": ip, "name": device_name(self.headers.get('User-Agent')), "created": now, "last": now}
            while len(cfg["tokens"]) > 20:   # mantem so os 20 mais recentes
                del cfg["tokens"][min(cfg["tokens"], key=lambda t: cfg["tokens"][t]["last"])]
            save_config(cfg)
            log("AUTH", f"Dispositivo conectado: {cfg['tokens'][tok]['name']} ({ip})", COLOR_GREEN)
            return self.send_json({"ok": True}, headers=self.guest_cookie(tok))
        login_recent_fails.append(now)
        if not fails or now - fails[1] >= LOGIN_LOCK_SECONDS: fails = login_failures[ip] = [0, now]
        fails[0] += 1
        log("AUTH", f"Senha incorreta de {ip} ({fails[0]}/{LOGIN_MAX_FAILS})", COLOR_RED)
        return self.send_json({"error": "bad_password"}, 401)

    def handle_chat(self, req_json, local=True, guest=None):
        global generation_active, active_model
        lang = 'en' if req_json.get('lang') == 'en' else 'pt'
        L = lambda pt, en: en if lang == 'en' else pt
        cfg = load_config()
        agent = bool(req_json.get("agent"))
        gid, gmax, stop_ev = None, None, stop_generation_flag
        if guest:   # amigo: sem agente, sem Exa, dentro dos limites que o dono definiu
            gid, gu = guest; pol = guests.policy(gu); gs = guests.settings; agent = False
            model0 = req_json.get('model') or ''
            if not model0: return self.send_json({"error": "modelo ausente"}, 400)
            why = guests.check_model(gu, model0)
            if why: return self.send_json({"error": "guest_model", "detail": why}, 403)
            msgs0 = req_json.get("messages", [])
            if not isinstance(msgs0, list) or sum(len(str(m.get("content", ""))) for m in msgs0 if isinstance(m, dict)) > 400000: return self.send_json({"error": "Mensagem grande demais."}, 413)
            if "images" in pol["blocked_features"] and any(isinstance(m, dict) and m.get("images") for m in msgs0): return self.send_json({"error": "guest_blocked", "detail": "images"}, 403)
            if "think" in pol["blocked_features"]: req_json["think"] = False
            if "web" in pol["blocked_features"]: req_json["search_web"] = False
            now = time.time(); today = guests_mod.usage_by_user([e for e in _read_json(STATS_FILE, {"events": []}).get("events", []) if e.get("user") == gid], {gid: gu})[gid]["today"]
            if pol["daily_limit"] and today >= pol["daily_limit"]: return self.send_json({"error": "guest_daily_limit", "limit": pol["daily_limit"]}, 429)
            with guest_lock:
                rec = [t for t in guest_recent.get(gid, []) if now - t < 60]
                if len(rec) >= gs["per_minute"]: guest_recent[gid] = rec; return self.send_json({"error": "guest_rate"}, 429)
                if guest_active.get(gid, 0) >= 1 or sum(guest_active.values()) >= gs["max_parallel"]: return self.send_json({"error": "guest_busy"}, 503)
                rec.append(now); guest_recent[gid] = rec; guest_active[gid] = guest_active.get(gid, 0) + 1
            stop_ev = stop_events.setdefault(gid, threading.Event())
            gmax = int(gs["max_tokens"])
            c = req_json.get("num_ctx")
            req_json["num_ctx"] = min(int(c), int(gs["ctx_cap"])) if c else None
        if agent and not local and not cfg.get("allow_remote_code"):
            log("SEGURANCA", "Modo agente recusado para dispositivo remoto (desligado nas configuracoes do servidor)", COLOR_RED)
            return self.send_json({"error": "remote_code_disabled"}, 403)
        stop_ev.clear()
        if not gid: generation_active = True
        started = time.time()
        model = req_json.get('model', 'qwen3.5:4b')
        if not gid: active_model = model
        messages = req_json.get("messages", [])
        think = bool(req_json.get("think"))
        num_ctx = req_json.get("num_ctx")
        workdir = get_workdir(cfg)
        n_images = sum(len(m.get("images", [])) for m in messages)
        log("CHAT", f"modelo={model} modo={'agente' if agent else 'chat'} mensagens={len(messages)} imagens={n_images} contexto={num_ctx or 'padrao'} pensar={think} web={bool(req_json.get('search_web'))}" + ("" if local else f" origem={self.client_address[0]}"), COLOR_CYAN)

        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.end_headers()

        def emit(obj):
            self.wfile.write((json.dumps(obj) + '\n').encode()); self.wfile.flush()
        def send(text, kind="content"): emit({"message": {"role": "assistant", kind: text}})
        def status(text): emit({"status": text})

        total_chars = 0
        try:
            if not model.startswith("groq"):
                if not ollama_is_running():
                    status("Iniciando Ollama")
                    if not start_ollama(): raise Exception("Nao consegui iniciar o Ollama. Ele esta instalado?")
                if model not in [m["name"] for m in ollama_ps()]:
                    status("Carregando modelo")
            else:
                status("Conectando ao Groq")

            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": ""})
            if agent:
                messages[0]["content"] += (TOOL_PROMPT_EN if lang == 'en' else TOOL_PROMPT).replace("{workdir}", workdir)
            elif req_json.get("search_web"):
                query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")[:200]
                if needs_web(query):
                    status("Pesquisando na web")
                    log("WEB", f"Pesquisando: {query}", COLOR_CYAN)
                    results, source = search_web_results(query, guest=bool(gid))
                    if results:
                        emit({"sources": [{"title": t, "url": u} for t, _, u in results], "provider": source})
                        messages[0]["content"] += L("\n\n[PESQUISA NA WEB - use se for relevante e cite os links]", "\n\n[WEB SEARCH - use it if relevant and cite the links]") + format_search(results, source)
                    else:
                        status("Pesquisa na web indisponível")
                        messages[0]["content"] += L("\n\n[A pesquisa na web falhou: voce NAO tem dados atuais. Se a pergunta depender de informacao recente, diga isso ao usuario em vez de inventar.]",
                                                    "\n\n[The web search failed: you do NOT have current data. If the question depends on recent information, say so instead of making things up.]")
                else:
                    log("WEB", "Mensagem nao precisa de pesquisa (cumprimento, frase curta, codigo ou arquivo); nada foi gasto.", COLOR_GRAY)

            corrections = 0; native_tries = 0
            req_tokens = req_prompt = 0; req_seconds = 0.0   # para as estatisticas
            clean = list(messages)   # conversa sem as tentativas falhas e sem os pedidos de correcao (o plano B usa esta)
            failed_pending = False   # a ultima tentativa de chamar ferramenta falhou e ainda nao houve uma boa
            for step in range(MAX_AGENT_STEPS if agent else 1):
                full = ""
                gen = stream_model(model, messages, think, cfg, num_ctx, gmax)
                try:
                    for kind, piece in gen:
                        if stop_ev.is_set(): break
                        if kind == "thinking":
                            send(piece, "thinking"); continue
                        if kind == "stats":
                            ptps = piece['prompt_tokens'] / piece['prompt_seconds'] if piece['prompt_seconds'] else 0
                            log("OLLAMA", f"{piece['tokens']} tokens em {piece['seconds']:.1f}s = {piece['tokens'] / piece['seconds']:.1f} t/s | prompt {piece['prompt_tokens']} tokens ({ptps:.0f} t/s) | carga do modelo {piece['load_seconds']:.1f}s | total {piece['total_seconds']:.1f}s", COLOR_GREEN)
                            req_tokens += piece["tokens"]; req_seconds += piece["seconds"]; req_prompt += piece["prompt_tokens"]
                            emit({"stats": piece}); continue
                        full += piece
                        send(piece)
                        if agent and ('}' in piece or '$' in piece) and find_tool_call(full): break
                finally:
                    gen.close()
                total_chars += len(full)
                if stop_ev.is_set():
                    send(L("\n\n[Geracao parada]", "\n\n[Generation stopped]"))
                    break
                call = find_tool_call(full) if agent else None
                if not call:
                    if agent and corrections < 2 and looks_like_failed_call(full):   # errou o formato: pede para repetir (ate 2 vezes)
                        corrections += 1; failed_pending = True
                        log("AGENTE", "Chamada de ferramenta fora do formato; pedindo para a IA repetir.", COLOR_YELLOW)
                        send(L("\n\n[formato de ferramenta invalido, pedindo para a IA tentar de novo]", "\n\n[invalid tool format, asking the AI to try again]"))
                        messages.append({"role": "assistant", "content": full})
                        messages.append({"role": "user", "content": L(CORRECTION_PT, CORRECTION_EN)})
                        status("Pensando")
                        continue
                    if agent and looks_like_failed_call(full): failed_pending = True   # sem tentativas de correcao sobrando
                    if agent and failed_pending and native_tries < 2:   # plano B: chamada nativa do Ollama
                        native_tries += 1
                        status("Tentando chamada nativa")
                        nc = native_tool_call(model, clean, num_ctx, workdir)
                        if nc:
                            full = "$$[TOOL: %s] %s$$" % (nc[0], json.dumps(nc[1], ensure_ascii=False))
                            log("AGENTE", f"Plano B (chamada nativa do Ollama) funcionou: {nc[0]}", COLOR_GREEN)
                            send(L("\n\n[plano B: chamada nativa de ferramenta]\n", "\n\n[fallback: native tool call]\n") + full)
                            call = (nc[0], nc[1], len(full))
                if not call:
                    if agent and failed_pending:   # a IA pode ter escrito que "executou", mas nada rodou: avisa o usuario
                        log("AGENTE", "A IA nao conseguiu chamar a ferramenta no formato certo; nada foi executado.", COLOR_RED)
                        send(L("\n\n[Nenhuma ferramenta foi executada: a IA nao conseguiu chamar a ferramenta no formato correto. Se ela disse que executou algo, isso nao aconteceu. Modelos pequenos as vezes falham ao usar ferramentas: e so pedir de novo.]",
                               "\n\n[No tool was run: the AI could not call the tool in the correct format. If it said it ran something, that did not happen. Small models sometimes fail when using tools: just ask again.]"))
                    break
                tool_name, tool_args, end = call
                failed_pending = False; corrections = 0; native_tries = 0   # cada passo ganha as suas tentativas
                tool_args = normalize_args(tool_name, tool_args)
                full = full[:end]
                log("TOOL", f"{tool_name} {tool_args}", COLOR_CYAN)
                if needs_permission(tool_name):
                    status("Aguardando permissão")
                    if not ask_permission(describe_tool(tool_name, tool_args)):
                        send(L("\n\n[Acao negada pelo usuario]", "\n\n[Action denied by the user]"))
                        break
                status(f"Executando: {tool_name}")
                if tool_name == "search_web":   # emite as fontes para a interface mostrar os cartoes
                    results, src = search_web_results(tool_args.get("query", ""))
                    result = format_search(results, src) if results else SEARCH_UNAVAILABLE
                    if results: emit({"sources": [{"title": t, "url": u} for t, _, u in results], "provider": src})
                elif tool_name == "read_url":
                    try:
                        page_title, page = read_url_text(tool_args.get("url", ""))
                        result = truncate(f"{page_title}\n\n{page}")
                        emit({"sources": [{"title": page_title, "url": tool_args.get("url", "")}], "provider": "read_url"})
                    except Exception as e:
                        result = f"Erro: {e}"
                else:
                    result = execute_tool(tool_name, tool_args, workdir, lang)
                log("TOOL", f"resultado de {tool_name}: {len(result)} caracteres", COLOR_GREEN if not result.startswith("Erro") else COLOR_RED)
                send(L(f"\n\n[resultado de {tool_name}]\n{result}\n[/resultado]\n\n", f"\n\n[result of {tool_name}]\n{result}\n[/result]\n\n"))
                pair = [{"role": "assistant", "content": full},
                        {"role": "user", "content": L(f"Resultado da ferramenta {tool_name}:\n{result}", f"Tool result for {tool_name}:\n{result}")}]
                messages.extend(pair); clean.extend(pair)
                status("Pensando")
            else:
                if agent:
                    send(L(f"\n\n[Limite de {MAX_AGENT_STEPS} chamadas de ferramenta atingido]", f"\n\n[Limit of {MAX_AGENT_STEPS} tool calls reached]"))
                    log("AGENTE", "Limite de passos atingido", COLOR_YELLOW)

            if model.startswith("groq"):
                cfg = load_config()
                cfg["usage"]["groq"] += total_chars
                save_config(cfg)
            record_event({"type": "chat", **({"user": gid} if gid else {}), "model": model, "cloud": model.startswith("groq"), "tab": "code" if agent else "chat",
                          "tokens": req_tokens or total_chars // 4, "seconds": req_seconds or (time.time() - started), "prompt_tokens": req_prompt, "chars": total_chars})
            u = model_usage.setdefault(model, {"uses": 0, "chars": 0})
            u["uses"] += 1; u["chars"] += total_chars; u["last_used"] = time.time()
            log("CHAT", f"concluido: {total_chars} caracteres em {time.time() - started:.1f}s", COLOR_GREEN)
        except Exception as e:
            log("ERRO", f"{type(e).__name__}: {e}", COLOR_RED)
            try: send(L(f"\n[Erro: {localize_error(e, lang)}]", f"\n[Error: {localize_error(e, lang)}]"))
            except Exception: pass
        finally:
            if gid:
                with guest_lock: guest_active[gid] = max(0, guest_active.get(gid, 1) - 1)
            else: generation_active = False

def start_server():
    global httpd
    handler = functools.partial(AppHandler, directory=BASE_DIR)
    host = "0.0.0.0" if load_config().get("remote_enabled") else "127.0.0.1"
    srv = None
    for attempt in range(8):   # na troca de modo o socket antigo pode demorar um instante para liberar a porta
        try:
            srv = ThreadingServer((host, PORT), handler); break
        except OSError as e:
            if attempt == 7:
                log("SERVIDOR", f"Nao foi possivel usar a porta {PORT}: {e}. Ja tem outra copia aberta?", COLOR_RED)
                return
            time.sleep(0.5)
    httpd = srv
    if host == "0.0.0.0" and tls is not None and tls.HAS_CRYPTO:
        try: srv.sniff_context = tls.server_context(CERTS_DIR, lan_ips())
        except Exception as e: log("HTTPS", f"A porta {PORT} ficou so em HTTP: {e}", COLOR_YELLOW)
    if host == "0.0.0.0": threading.Thread(target=start_https_server, daemon=True).start()
    if host == "0.0.0.0":
        log("SERVIDOR", f"ACESSO REMOTO LIGADO na porta {PORT}. Enderecos: " + ", ".join(f"http://{ip}:{PORT}" for ip in lan_ips()), COLOR_YELLOW)
    else:
        log("SERVIDOR", f"Rodando em http://127.0.0.1:{PORT} (somente neste PC)", COLOR_GREEN)
    try:
        srv.serve_forever()
    finally:
        srv.server_close()

def custom_icon_ico():
    """Converte icons/qwen.png em .ico (o Windows aceita PNG dentro do .ico) para o icone da janela. None se nao houver."""
    if not os.path.isfile(CUSTOM_ICON): return None
    try:
        data = open(CUSTOM_ICON, "rb").read()
        if data[:8] != b"\x89PNG\r\n\x1a\n": return None
        w, hgt = struct.unpack(">II", data[16:24])
        out = os.path.join(BASE_DIR, "webview_data", "app.ico"); os.makedirs(os.path.dirname(out), exist_ok=True)
        entry = struct.pack("<BBBBHHII", w if w < 256 else 0, hgt if hgt < 256 else 0, 0, 0, 1, 32, len(data), 22)
        with open(out, "wb") as f: f.write(struct.pack("<HHH", 0, 1, 1) + entry + data)
        return out
    except Exception as e:
        log("ICONE", f"Nao consegui usar icons/qwen.png: {e}", COLOR_YELLOW); return None

# ---------------- atualizacoes (GitHub) ----------------
DEFAULT_REPO = "marioondc9426/ai-thing-idk"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

def _git(*args, timeout=60):
    r = subprocess.run(["git", *args], cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", creationflags=NOWIN)
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()

def github_repo():
    try:
        code, out, _ = _git("remote", "get-url", "origin")
        m = re.search(r"github\.com[:/]+([^/]+/[^/]+?)(?:\.git)?/?$", out) if code == 0 else None
        if m: return m.group(1)
    except Exception: pass
    return DEFAULT_REPO

def check_update():
    """Compara a versao deste PC com o main do GitHub. status: uptodate | available | ahead | diverged | unknown | error."""
    try:
        code, local, _ = _git("rev-parse", "HEAD")
        if code != 0: return {"status": "error", "error": "no_git"}
        _, when, _ = _git("log", "-1", "--format=%cd", "--date=short")
        _, subj, _ = _git("log", "-1", "--format=%s")
        info = {"local": local[:7], "local_date": when, "local_subject": subj, "version": VERSION}
        req = urllib.request.Request(f"https://api.github.com/repos/{github_repo()}/compare/{local}...main",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "ai-thing-updater"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r: d = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404: return {**info, "status": "unknown"}   # commit local que o GitHub nao conhece
            raise
        remote_version = ""
        try:   # a versao que esta no GitHub (linha VERSION = "..." do app.py)
            rq = urllib.request.Request(f"https://raw.githubusercontent.com/{github_repo()}/main/app.py", headers={"Range": "bytes=0-6000", "User-Agent": "ai-thing-updater"})
            with urllib.request.urlopen(rq, timeout=8) as r2: mv = re.search(r'^VERSION = "([^"]+)"', r2.read().decode("utf-8", "replace"), re.M)
            remote_version = mv.group(1) if mv else ""
        except Exception: pass
        info["remote_version"] = remote_version
        status = {"identical": "uptodate", "ahead": "available", "behind": "ahead", "diverged": "diverged"}.get(d.get("status"), "unknown")
        commits = [{"sha": c["sha"][:7], "msg": c["commit"]["message"].split("\n")[0]} for c in d.get("commits", [])][-15:]
        return {**info, "status": status, "behind_by": d.get("ahead_by", 0) if status == "available" else 0, "commits": commits[::-1]}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}

update_lock = threading.Lock()

def apply_update():
    """git pull --ff-only (recusa se houver arquivos do programa alterados a mao) e instala dependencias novas."""
    if not update_lock.acquire(blocking=False): return {"ok": False, "error": "busy"}
    try:
        code, dirty, _ = _git("status", "--porcelain", "--untracked-files=no")
        if code != 0: return {"ok": False, "error": "no_git"}
        if dirty: return {"ok": False, "error": "dirty", "files": dirty.splitlines()[:10]}
        code, out, err = _git("pull", "--ff-only", timeout=180)
        if code != 0: return {"ok": False, "error": "pull", "detail": (err or out)[-400:]}
        log("UPDATE", "Atualizado: " + (out.splitlines()[-1] if out else "ok"), COLOR_GREEN)
        req = os.path.join(BASE_DIR, "requirements.txt")
        if os.path.isfile(req):
            try: subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", req], cwd=BASE_DIR, timeout=300, creationflags=NOWIN)
            except Exception as e: log("UPDATE", f"pip falhou (ignorado): {e}", COLOR_YELLOW)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": "pull", "detail": str(e)[:300]}
    finally:
        update_lock.release()

window_api = None

def restart_app():
    """Fecha este app e abre outro depois de alguns segundos (a porta precisa ser liberada primeiro)."""
    subprocess.Popen(f'cmd /c "ping -n 4 127.0.0.1 >nul & "{sys.executable}" app.py"', cwd=BASE_DIR, shell=True,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    if window_api and window_api._window: window_api._window.destroy()

def restart_server():
    """Reinicia o servidor HTTP (troca entre 'so neste PC' e 'rede local') sem fechar o app."""
    def work():
        old, old_tls = httpd, https_httpd
        if old_tls: old_tls.shutdown()
        if old: old.shutdown()
        time.sleep(0.3)
        threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=work, daemon=True).start()

WINDOW_TITLE = APP_NAME

# ---------------------------------------------------------------- tunel para acessar de fora de casa
tunnel_state = {"running": False, "url": "", "error": "", "tool": ""}
_tunnel_proc = None

def find_cloudflared():
    return shutil.which("cloudflared") or next((p for p in (os.path.join(BASE_DIR, "tools", "cloudflared.exe"), os.path.join(os.environ.get("ProgramFiles", ""), "cloudflared", "cloudflared.exe")) if os.path.isfile(p)), None)

CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

def install_cloudflared(dest=None):
    """Baixa o cloudflared portatil para a pasta tools (nao precisa de administrador) e confere a assinatura digital da Cloudflare."""
    dest = dest or os.path.join(BASE_DIR, "tools", "cloudflared.exe"); os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".download"
    try:
        req = urllib.request.Request(CLOUDFLARED_URL, headers={"User-Agent": "qwen-app"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f: shutil.copyfileobj(r, f)
        ps = subprocess.run(["powershell", "-NoProfile", "-Command", f"$s = Get-AuthenticodeSignature -LiteralPath '{tmp}'; Write-Output ($s.Status.ToString() + '|' + $s.SignerCertificate.Subject)"],
                            capture_output=True, text=True, timeout=60, creationflags=NOWIN).stdout.strip()
        if not ps.startswith("Valid|") or "Cloudflare, Inc." not in ps: raise Exception("assinatura digital invalida: " + ps[:120])
        os.replace(tmp, dest); log("TUNEL", "cloudflared instalado em " + dest, COLOR_GREEN)
        return {"ok": True}
    except Exception as e:
        try: os.remove(tmp)
        except OSError: pass
        return {"ok": False, "error": f"Nao consegui baixar o cloudflared: {e}"}

def stop_tunnel():
    global _tunnel_proc
    if _tunnel_proc and _tunnel_proc.poll() is None:
        try: _tunnel_proc.terminate()
        except OSError: pass
    _tunnel_proc = None; tunnel_state.update(running=False, url="", error="")

def start_tunnel():
    """Abre um tunel do Cloudflare (gratis, sem conta): o endereco https://algo.trycloudflare.com muda toda vez que e aberto."""
    global _tunnel_proc
    exe = find_cloudflared()
    if not exe: return {"ok": False, "error": "cloudflared nao encontrado. Clique em \"Baixar cloudflared (sem administrador)\"."}
    stop_tunnel(); tunnel_state.update(running=True, url="", error="", tool="cloudflared")
    try:
        _tunnel_proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{PORT}"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    except OSError as e:
        tunnel_state.update(running=False, error=str(e)); return {"ok": False, "error": str(e)}
    proc = _tunnel_proc
    def reader():
        for line in proc.stderr:
            m = re.search(r"https://[a-z0-9\-]+\.trycloudflare\.com", line)
            if m and not tunnel_state["url"]: tunnel_state["url"] = m.group(0); log("TUNEL", f"Endereco publico: {m.group(0)}", COLOR_YELLOW)
        if _tunnel_proc is proc: tunnel_state.update(running=False, url="", error=tunnel_state["error"] or "O tunel foi encerrado.")
    threading.Thread(target=reader, daemon=True).start()
    return {"ok": True}

class WindowApi:
    """Botoes da barra de titulo propria (a janela nao tem a borda do Windows)."""
    def __init__(self):
        self._window = None   # com "_" o pywebview nao expoe ao JavaScript
        self._maximized = False
    def minimize(self): self._window.minimize()
    def set_geom(self, x, y, w, h):
        """Usada pelas alcas de redimensionar da pagina (a janela nao tem a borda do Windows)."""
        win = self._window
        if (int(w), int(h)) != (win.width, win.height): win.resize(int(w), int(h))
        if (int(x), int(y)) != (win.x, win.y): win.move(int(x), int(y))
    def toggle_maximize(self):
        """Maximiza na area de trabalho (sem cobrir a barra de tarefas) e anima a troca de tamanho."""
        try:
            u = ctypes.windll.user32
            hwnd = u.FindWindowW(None, WINDOW_TITLE)
            if not hwnd: raise OSError("janela nao encontrada")
            r = wintypes.RECT(); u.GetWindowRect(hwnd, ctypes.byref(r))
            cur = (r.left, r.top, r.right - r.left, r.bottom - r.top)
            if not self._maximized:
                self._restore = cur
                class MI(ctypes.Structure): _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
                mi = MI(); mi.cbSize = ctypes.sizeof(mi)
                u.GetMonitorInfoW(u.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))   # 2 = monitor mais proximo
                w = mi.rcWork; target = (w.left, w.top, w.right - w.left, w.bottom - w.top)
            else:
                target = getattr(self, "_restore", (cur[0] + 60, cur[1] + 40, 1100, 800))
            steps = 14
            for i in range(1, steps + 1):
                k = 1 - (1 - i / steps) ** 3   # comeca rapido e freia no fim
                x, y, wd, ht = (round(cur[j] + (target[j] - cur[j]) * k) for j in range(4))
                u.SetWindowPos(hwnd, 0, x, y, wd, ht, 0x0014)   # SWP_NOZORDER | SWP_NOACTIVATE
                time.sleep(0.011)
        except Exception as e:
            log("JANELA", f"Maximizar com animacao falhou ({e}); usando o modo padrao.", COLOR_YELLOW)
            if self._maximized: self._window.restore()
            else: self._window.maximize()
        self._maximized = not self._maximized
        return self._maximized
    def close(self): self._window.destroy()

if __name__ == '__main__':
    log("INICIO", f"Pasta do programa: {BASE_DIR}", COLOR_BLUE)
    PORT = int(load_config().get("port", PORT))
    log("INICIO", "Groq: " + ("biblioteca ok" if HAS_GROQ else "biblioteca NAO instalada (pip install groq)"), COLOR_GREEN if HAS_GROQ else COLOR_YELLOW)
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=start_ollama, daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()
    start_gpu_stream(gpu_interval_ms)
    time.sleep(1)
    log("INICIO", "Abrindo janela...", COLOR_BLUE)
    api = WindowApi()
    api._window = webview.create_window(WINDOW_TITLE, f'http://127.0.0.1:{PORT}/index.html', width=1100, height=800, min_size=(800, 520), frameless=True, easy_drag=False, js_api=api)
    # private_mode=False: sem isso o localStorage some toda vez que o app fecha
    window_api = api
    webview.start(private_mode=False, storage_path=os.path.join(BASE_DIR, "webview_data"), icon=custom_icon_ico())
    log("SAIDA", "Janela fechada. Desligando as IAs...", COLOR_YELLOW)
    shutdown_all()
    log("SAIDA", "Tudo desligado.", COLOR_GREEN)
