import http.server
import socketserver
import math
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
import traceback
import platform
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
import hashlib
import tempfile
import importlib
import importlib.util
import ctypes
import ast
import shutil
from ctypes import wintypes
import struct
import zipfile
import xml.etree.ElementTree as ET
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
FROZEN = bool(getattr(sys, "frozen", False))   # True quando roda como Lume.exe (PyInstaller)
RES_DIR = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))   # o que vem dentro do programa: paginas e icones
def _env(name): return os.environ.get("LUME_" + name) or os.environ.get("QWEN_" + name)   # QWEN_* ainda vale (nome antigo do app)
# Seus dados (conversas, chaves, certificados...): na pasta do projeto; no .exe ficam em %LOCALAPPDATA%\Lume (ou na pasta indicada em LUME_DATA_DIR)
_data_root = os.environ.get("LOCALAPPDATA") or (os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share") if sys.platform.startswith("linux") else os.path.dirname(sys.executable))   # Windows: %LOCALAPPDATA%; Linux: ~/.local/share
OWNER_ONLY = os.path.exists(os.path.join(RES_DIR, "owner_only.flag")) or bool(_env("OWNER_ONLY"))   # versao so para o dono: nunca abre a porta para a rede (sem acesso remoto, amigos nem tunel)
if sys.platform.startswith("linux") and not os.environ.get("PYWEBVIEW_GUI"): os.environ["PYWEBVIEW_GUI"] = "qt"   # o Linux usa a janela Qt (vem junto no binario)
if sys.platform.startswith("linux") and os.environ.get("DISPLAY") and not os.environ.get("QT_QPA_PLATFORM"): os.environ["QT_QPA_PLATFORM"] = "xcb"   # janela X11 (o Wayland puro nao deixa o app mover nem redimensionar a propria janela sem moldura: arrastar a barra de titulo nao funcionava)
if sys.platform.startswith("linux") and FROZEN and not _env("GPU"):   # binario empacotado: o Qt WebEngine embutido nao acha o EGL do sistema e aborta; sem GPU a janela abre em qualquer maquina (LUME_GPU=1 desliga isto)
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    _qf = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu" not in _qf: os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (_qf + " --disable-gpu").strip()
BASE_DIR = _env("DATA_DIR") or (os.path.join(_data_root, "Lume") if FROZEN else RES_DIR)
if FROZEN and not _env("DATA_DIR") and not os.path.exists(BASE_DIR) and os.path.isdir(os.path.join(_data_root, "Qwen")):   # o app se chamava Qwen: traz as conversas e configuracoes junto
    try: os.rename(os.path.join(_data_root, "Qwen"), BASE_DIR)
    except OSError: BASE_DIR = os.path.join(_data_root, "Qwen")
sys.path.insert(0, RES_DIR)
if FROZEN:
    os.makedirs(BASE_DIR, exist_ok=True)
    if not _env("CONSOLE"):   # o .exe nao tem janela de console: o que seria impresso vai para o lume.log (LUME_CONSOLE=1 deixa no terminal)
        _lp = os.path.join(BASE_DIR, "lume.log")
        try:
            if os.path.exists(_lp) and os.path.getsize(_lp) > 2_000_000: os.replace(_lp, _lp + ".old")
        except OSError: pass
        sys.stdout = sys.stderr = open(_lp, "a", encoding="utf-8", buffering=1)
try: import tls   # HTTPS local (precisa do pacote "cryptography")
except Exception: tls = None
try: import vcomp   # controle do computador em segundo plano (varios programas, mouse virtual)
except Exception: vcomp = None
try: import lumemcp   # cliente MCP (servidores de ferramentas externos, por stdio)
except Exception: lumemcp = None
try: import lumebrowser   # ponte com a extensao do navegador (a IA usa as abas do navegador do dono)
except Exception: lumebrowser = None
CERTS_DIR = os.path.join(BASE_DIR, "certs")
HTTPS_PORT = 8443
APP_NAME = "Lume"
import guests as guests_mod   # contas de amigos (/share) e painel (/dashboard)
# Provedores compativeis com a API da OpenAI que o Lume usa so com os modelos gratis: prefixo -> (campo da chave, endereco, nome, segundos entre testes de saude)
AC_URL = "https://www.aichixia.xyz/api/v1"; AH_URL = "https://aihubmix.com/v1"; LR_URL = "https://api.literouter.com/v1"; PX_URL = "https://api.paxsenix.org/v1"; VD_URL = "https://api.voidai.app/v1"; TK_URL = "https://api.tokenreply.com/v1"
def _load_provider_registry():
    """Os provedores extras ficam em libs/providers.js (o mesmo arquivo que o iPhone e a interface leem): {codigo: (campo da chave, url, nome, espacamento)} e o resto das opcoes."""
    try:
        txt = open(os.path.join(RES_DIR, "libs", "providers.js"), encoding="utf-8").read()
        return json.loads(re.search(r"window\.LUME_PROVIDERS\s*=\s*(\[.*\])\s*;", txt, re.S).group(1))
    except Exception as e:
        print("Nao consegui ler libs/providers.js:", e); return []
PROVIDER_REGISTRY = _load_provider_registry()
X_PROVIDERS = {p["id"]: (p["field"], p["url"], p["name"], float(p.get("spacing", 1.5))) for p in PROVIDER_REGISTRY}   # um lugar so para colocar outro provedor extra: libs/providers.js
X_KIND = {p["id"]: p.get("kind", "openai") for p in PROVIDER_REGISTRY}
X_LIMIT = {p["id"]: int(p["dailyLimit"]) for p in PROVIDER_REGISTRY if p.get("dailyLimit")}   # pedidos gratis por dia (so os que informam)
X_KEY_FIELDS = tuple(f for f, _u, _n, _s in X_PROVIDERS.values()) + tuple(f + "_backup" for f, _u, _n, _s in X_PROVIDERS.values())   # campos de chave dos provedores extras (aceitos ao salvar as configuracoes)
CLOUD_PREFIXES = ("groq", "or:", "cf:", "pol:", "tdc:", "vc:", "l7:") + tuple(p + ":" for p in X_PROVIDERS)
ACCOUNTS_DIR = os.path.join(BASE_DIR, "accounts")   # uma pasta por conta, com o nome dela (a do dono e a dos amigos)
def _find_owner_name():
    """O nome da conta do dono e o da pasta de accounts/ cujo account.json tem "role": "owner". Se voce renomear a pasta (e o "name" dentro dela), o app segue o novo nome."""
    default = "owner"   # nome da conta do dono numa instalacao nova (renomeie a pasta em accounts/ e o "name" dentro dela para trocar)
    try:
        cands = []
        for n in sorted(os.listdir(ACCOUNTS_DIR)):
            try:
                with open(os.path.join(ACCOUNTS_DIR, n, "account.json"), encoding="utf-8") as f: meta = json.load(f)
            except (OSError, ValueError): continue
            if isinstance(meta, dict) and meta.get("role") == "owner": cands.append((n, meta.get("name")))
        for n, nm in cands:
            if nm == n: return n   # a pasta com o mesmo nome que esta dentro do account.json
        if cands: return cands[0][0]
    except OSError: pass
    return default
OWNER_NAME = _find_owner_name()
guests = guests_mod.Guests(os.path.join(BASE_DIR, "guests.json"), ACCOUNTS_DIR, os.path.join(BASE_DIR, "guest_data"))
guests.reserved = {OWNER_NAME.lower()}   # um amigo nao pode cadastrar o nome do dono
stop_events = {}        # id do amigo -> Event (parar so a geracao dele)
guest_active = {}       # id do amigo -> geracoes em andamento
guest_recent = {}       # id do amigo -> horarios das ultimas respostas (limite por minuto)
guest_lock = threading.Lock()
login_recent_fails = []  # horarios das senhas erradas de qualquer IP (trava global contra tentativas pela internet)
# Versao: "1.2" = versao nova com novidades (o numero depois do ponto sobe); "1.2.01", "1.2.02"... = correcoes (patches) dessa versao.
VERSION = "3.1.01"
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")     # chaves de API, pasta de trabalho, uso
def _owner_dir():
    """accounts/<dono>/: conversas e preferencias do dono. Na primeira vez COPIA (nao move) os history.json/state.json antigos da pasta do app."""
    d = os.path.join(ACCOUNTS_DIR, OWNER_NAME)
    try:
        os.makedirs(d, exist_ok=True)
        meta = os.path.join(d, "account.json")
        if not os.path.exists(meta):
            with open(meta, "w", encoding="utf-8") as f: json.dump({"name": OWNER_NAME, "role": "owner", "note": "Conta do dono: usa as chaves e as configuracoes do app (config.json). Os history.json e state.json antigos da pasta do app foram copiados para ca."}, f, ensure_ascii=False, indent=1)
        for fn in ("history.json", "state.json"):
            old, new = os.path.join(BASE_DIR, fn), os.path.join(d, fn)
            if os.path.exists(old) and not os.path.exists(new): shutil.copy2(old, new)
    except OSError: return BASE_DIR   # sem permissao de escrita: continua nos arquivos de sempre
    return d
OWNER_DIR = _owner_dir()
HISTORY_FILE = os.path.join(OWNER_DIR, "history.json")  # chats do dono
STATE_FILE = os.path.join(OWNER_DIR, "state.json")      # preferencias da interface + memorias do dono
STATS_FILE = os.path.join(BASE_DIR, "stats.json")       # uso: tokens/s por modelo, gasto do Exa
UNDO_DIR = os.path.join(BASE_DIR, "undo")               # copias dos arquivos que a IA sobrescreveu (botao Desfazer)
MAX_BODY_BYTES = 60 * 1024 * 1024   # tamanho maximo de uma requisicao (anexos)
MAX_FILE_CHARS = 60000              # texto maximo extraido de um arquivo anexado
THEMES_DIR = os.path.join(BASE_DIR, "custom themes")    # temas criados no editor de temas
MAX_AGENT_STEPS = 25       # limite PADRAO de chamadas de ferramenta por mensagem (vale a opcao "max_agent_steps" das configuracoes)
MAX_TOOL_OUTPUT = 8000     # caracteres devolvidos a IA por ferramenta
TOOL_TIMEOUT = 60          # segundos para cmd/powershell

MONITOR_EVERY_S = 2.5     # de quanto em quanto tempo a memoria da GPU e conferida
VRAM_ALERT_EVERY_S = 2.5 # a cada quantos segundos o aviso de VRAM alta (terminal) se repete
VRAM_WARN_MB = 7144        # aviso de VRAM alta (7 GB)
ollama_process = None
pending_command = {"cmd": "", "resolve": None, "rule": "", "detail": ""}
stop_generation_flag = threading.Event()   # so para as esperas de permissao e o desligamento do app; cada geracao do dono tem o seu proprio "parar"
gens_active = {}           # id do pedido -> modelo (geracoes do dono em andamento; pode haver varias, uma por chat)
req_stops = {}             # id do pedido -> Event (parar so aquela geracao)
model_usage = {}           # modelo -> {"last_used": ts, "uses": n, "chars": n}
started_at = time.time()

COLOR_RESET = "\033[0m"; COLOR_GREEN = "\033[92m"; COLOR_YELLOW = "\033[93m"; COLOR_RED = "\033[91m"; COLOR_BLUE = "\033[94m"; COLOR_CYAN = "\033[96m"; COLOR_GRAY = "\033[90m"
if os.name == 'nt':
    os.system("")  # habilita cores ANSI no terminal do Windows

_ANSI = re.compile(r"\033\[[0-9;]*m")
# ---- o terminal acompanha o idioma do app: com o app em ingles, as mensagens conhecidas saem em ingles (as que nao estao na lista ficam como estao)
UI_LANG = "pt"
LOG_TAGS_EN = {"AGENTE": "AGENT", "PERMISSAO": "PERMISSION", "INICIO": "START", "SAIDA": "EXIT", "HISTORICO": "HISTORY", "ERRO": "ERROR", "ERRO · DETALHES": "ERROR · DETAILS", "USUARIO": "USER", "TOOL · RESULTADO": "TOOL · RESULT",
               "IA · MENSAGEM COMPLETA": "AI · FULL MESSAGE", "IA · RESPOSTA": "AI · RESPONSE", "IA · RACIOCINIO": "AI · REASONING", "SERVIDOR": "SERVER", "SEGURANCA": "SECURITY", "MODELO": "MODEL", "CONFIG": "CONFIG", "CODIGO": "CODE",
               "AMIGOS": "FRIENDS", "CONTA": "ACCOUNT", "TUNEL": "TUNNEL", "BANDEJA": "TRAY", "JANELA": "WINDOW", "MEMORIA": "MEMORY", "ARQUIVO": "FILE", "CHAVES": "KEYS", "ESFORCO": "EFFORT", "SAUDE": "HEALTH", "TEMA": "THEME", "DESFAZER": "UNDO", "EXPORTAR": "EXPORT", "STATS": "STATS"}
LOG_EN = [(re.compile(p), r) for p, r in [
    (r"^concluido: (\d+) caracteres em ([\d.]+)s$", r"done: \1 characters in \2s"),
    (r"^modelo=", "model="), (r" modo=agente", " mode=agent"), (r" modo=chat", " mode=chat"), (r" mensagens=", " messages="), (r" imagens=", " images="), (r" contexto=", " context="), (r"=padrao", "=default"), (r" pensar=", " think="), (r" origem=", " origin="),
    (r"^resultado de (.+): (\d+) caracteres$", r"result of \1: \2 characters"),
    (r"^Limite de passos atingido$", "Step limit reached"),
    (r"^A IA nao conseguiu chamar a ferramenta no formato certo; nada foi executado\.", "The AI could not call the tool in the right format; nothing was run."),
    (r"A IA INVENTOU o resultado de uma ferramenta", "The AI MADE UP a tool result"), (r"A IA disse que ia agir mas nao chamou nenhuma ferramenta", "The AI said it would act but called no tool"), (r"A IA errou o formato da chamada", "The AI got the call format wrong"),
    (r"; chamando a atencao dela\. Mensagem COMPLETA dela, sem filtro:", "; getting its attention. Its FULL message, unfiltered:"),
    (r"^Plano B \(chamada nativa do Ollama\) funcionou: ", "Fallback (native Ollama call) worked: "), (r"^Plano B falhou: ", "Fallback failed: "),
    (r"^Aguardando o usuario: ", "Waiting for the user: "), (r"^Aprovado pelo usuario$", "Approved by the user"), (r"^MCP permitido sozinho: ", "MCP auto-allowed: "), (r"^Permitido sozinho: ", "Auto-allowed: "), (r"^Bloqueado \(", "Blocked ("),
    (r"^(\d+) tokens em ([\d.]+)s = ([\d.]+) t/s \| prompt (\d+) tokens \((\d+) t/s\) \| carga do modelo ([\d.]+)s \| total ([\d.]+)s$", r"\1 tokens in \2s = \3 t/s | prompt \4 tokens (\5 t/s) | model load \6s | total \7s"),
    (r"^(\d+) chat\(s\) salvos$", r"\1 chat(s) saved"), (r"^Parada solicitada pelo usuario$", "Stop requested by the user"),
    (r"^Interface carregada", "Interface loaded"), (r"^Pagina (.+) aberta", r"Page \1 opened"), (r" por (\d+\.)", r" by \1"),
    (r"^Abrindo janela\.\.\.$", "Opening window..."), (r"^Pasta do programa: ", "Program folder: "), (r"^Aceleracao de hardware: ", "Hardware acceleration: "), (r"^Groq: biblioteca ok$", "Groq: library ok"), (r"^Groq: biblioteca NAO instalada", "Groq: library NOT installed"),
    (r"^Janela fechada\. Desligando as IAs\.\.\.$", "Window closed. Shutting down the AIs..."), (r"^Tudo desligado\.$", "Everything is off."), (r"^Modelo (.+) desligado\.$", r"Model \1 unloaded."),
    (r"^Rodando em (.+) \(somente neste PC\)$", r"Running at \1 (this PC only)"), (r"^ACESSO REMOTO LIGADO na porta (\d+)\. Enderecos: ", r"REMOTE ACCESS ON at port \1. Addresses: "),
    (r"^Senha do servidor gerada \(veja em Configuracoes > Servidor\)\.$", "Server password generated (see Settings > Server)."), (r"^Dispositivo conectado: ", "Device connected: "), (r"^Dispositivo desconectado\.?$", "Device disconnected"),
    (r"^Ollama nao esta rodando\. Iniciando\.\.\.$", "Ollama is not running. Starting..."), (r"^Ollama pronto\.$", "Ollama ready."), (r"^Comando 'ollama' nao encontrado\.", "'ollama' command not found."),
    (r"^Carregando (.+)\.\.\.$", r"Loading \1..."), (r"^(.+) carregado em ([\d.]+)s$", r"\1 loaded in \2s"), (r"^(.+) desligado\.$", r"\1 unloaded."), (r"^Baixando (.+)\.\.\.$", r"Downloading \1..."), (r"^(.+) pronto\.$", r"\1 ready."), (r"^(.+) apagado\.$", r"\1 deleted."),
    (r"^Conferindo atualizacoes de (\d+) modelo\(s\)\.\.\.$", r"Checking updates for \1 model(s)..."), (r"^Falha ao carregar (.+): ", r"Failed to load \1: "),
    (r"^(\d+) resultado\(s\) via (.+)$", r"\1 result(s) via \2"), (r"^Resultado reaproveitado do cache \(busca repetida, sem custo\)\.$", "Result reused from cache (repeated search, no cost)."), (r"^Pesquisa falhou em todas as fontes", "Search failed in every source"),
    (r"^Configuracoes salvas", "Settings saved"), (r"^Criando config padrao", "Creating default config"), (r"^Leitura de GPU a cada (\d+) ms$", r"GPU read every \1 ms"), (r"^nvidia-smi nao encontrado: sem metricas de GPU\.$", "nvidia-smi not found: no GPU metrics."),
    (r"^Rodando (\w+): ", r"Running \1: "), (r"^Instalando: ", "Installing: "), (r"^Arquivo restaurado para a versao anterior\.", "File restored to the previous version."),
    (r"^Estatisticas apagadas\.$", "Statistics cleared."), (r"^Terminal do log aberto", "Log terminal opened"), (r"^Icone da bandeja ligado\.$", "Tray icon on."),
]]
def _log_en(tag, msg):
    tag = LOG_TAGS_EN.get(tag, tag)
    for rx, rp in LOG_EN: msg = rx.sub(rp, msg)
    return tag, msg

def set_ui_lang(l):
    """Guarda o idioma do app (vem da interface) para o terminal e as mensagens do servidor."""
    global UI_LANG
    l = "en" if l == "en" else "pt"
    if l == UI_LANG: return
    UI_LANG = l
    try:
        cfg = load_config()
        if cfg.get("ui_lang") != l: cfg["ui_lang"] = l; save_config(cfg)
    except Exception: pass

# ---- streaming no terminal: a resposta (e o raciocinio) da IA aparece AO VIVO, pedaco por pedaco, em vez de so no fim
_term = {"owner": None, "tag": None}; _term_lock = threading.RLock()
def term_stream_end():
    """Fecha a linha que esta sendo escrita ao vivo (chamado antes de qualquer outro log e no fim da resposta)."""
    with _term_lock:
        if _term["tag"] is None: return
        _term["tag"] = _term["owner"] = None
        try: sys.stdout.write("\n"); sys.stdout.flush()
        except Exception: pass
def term_stream(owner, tag, text, color=COLOR_RESET, model=""):
    if not text: return
    with _term_lock:
        try:
            if _term["tag"] != tag or _term["owner"] != owner:   # comecou outra coisa (ou outra conversa): fecha a linha anterior e poe um cabecalho novo
                term_stream_end(); t2 = (LOG_TAGS_EN.get(tag, tag) if UI_LANG == "en" else tag) + (" · " + model if model else "")   # cabecalho com o modelo que esta respondendo
                head = f"{COLOR_GRAY}{time.strftime('%H:%M:%S')}{COLOR_RESET} {color}[{t2}]{COLOR_RESET} "
                sys.stdout.write(head if sys.stdout.isatty() else _ANSI.sub("", head)); _term["tag"], _term["owner"] = tag, owner
            sys.stdout.write(f"{color}{text}{COLOR_RESET}" if sys.stdout.isatty() else text); sys.stdout.flush()
        except Exception: pass

def log(tag, msg, color=COLOR_RESET):
    if _term["tag"] is not None: term_stream_end()
    if UI_LANG == "en":
        try: tag, msg = _log_en(tag, str(msg))
        except Exception: pass
    line = f"{COLOR_GRAY}{time.strftime('%H:%M:%S')}{COLOR_RESET} {color}[{tag}]{COLOR_RESET} {msg}"
    try:
        if not sys.stdout.isatty(): line = _ANSI.sub("", line)   # arquivo de log sem codigos de cor
        print(line, flush=True)
    except Exception: pass

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
        with open(path, 'r', encoding='utf-8-sig') as f: return json.load(f)   # utf-8-sig: aceita arquivos salvos com BOM (Bloco de Notas, PowerShell)
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
            with open(CONFIG_FILE, 'r', encoding='utf-8-sig') as f: cfg = json.load(f)
        except Exception as e:
            log("CONFIG", f"config.json invalido ({e}). Usando padrao.", COLOR_RED)
    else:
        log("CONFIG", "Criando config padrao", COLOR_YELLOW)
    cfg.setdefault("groq_api_key", "")
    cfg.setdefault("openrouter_api_key", "")     # chave do OpenRouter (so modelos gratis)
    cfg.setdefault("cloudflare_api_token", "")   # Cloudflare Workers AI: token + id da conta
    cfg.setdefault("cloudflare_account_id", "")
    cfg.setdefault("quick_style", "mica")         # fundo da caixinha: solid | mica | aero | acrylic
    cfg.setdefault("quick_hotkey", True)         # Alt+Espaco abre a caixinha rapida (janela flutuante)
    cfg.setdefault("pet_desktop", False)         # o mascote na area de trabalho (da para jogar; quica nas bordas da tela como uma gelatina)
    cfg.setdefault("pet_size", 200)              # tamanho do pet em % (100% = 80 px)
    cfg.setdefault("pet_snap", True)             # grudar na borda da tela quando soltar perto dela
    cfg.setdefault("quick_sel_hotkey", True)     # Ctrl+Alt+Espaco: abre a caixinha com o texto selecionado no app da frente (explicar, traduzir, resumir, corrigir)
    cfg.setdefault("log_full", True)              # o terminal mostra cada mensagem crua da IA, o raciocinio e os resultados (desligue em Configuracoes se for muito)
    cfg.setdefault("ui_lang", "pt")
    cfg.setdefault("mcp_auto_allow", False)      # aceitar sozinho as ferramentas MCP (sem perguntar)
    cfg.setdefault("max_agent_steps", MAX_AGENT_STEPS)   # chamadas de ferramenta por mensagem (aba Code)
    cfg.setdefault("mcp_servers", {})            # servidores MCP: {nome: {command, args, env, enabled}}
    cfg.setdefault("pollinations_api_key", "")   # Pollinations: modelos que gastam pollen
    cfg.setdefault("vercel_api_key", "")         # Vercel AI Gateway (modelos "-free")
    for _f, _u, _n, _s in X_PROVIDERS.values(): cfg.setdefault(_f, "")
    cfg.setdefault("aihubmix_api_key", ""); cfg.setdefault("literouter_api_key", "")   # Aichixia, AIHubMix e LiteRouter (so os modelos gratis)
    cfg.setdefault("llm7_api_key", "")           # LLM7 (modelos do plano "turbo", sem saldo)
    cfg.setdefault("tomdacat_api_key", "")       # tomdacat (ai.tomdacat.com): gateway de modelos cobrado em creditos
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
    cfg.setdefault("feedback_url", ""); cfg.setdefault("feedback_key", "")   # servidor do lume-feedback (Enviar feedback)
    cfg.setdefault("exa_api_key", "")            # pesquisa feita para IAs (exa.ai); vazio = usa DuckDuckGo
    cfg.setdefault("search_provider", "auto")    # auto | exa | duckduckgo
    cfg.setdefault("exa_type", "lite")           # lite (US$ 0,004/busca) | auto (US$ 0,007) | deep-lite
    cfg.setdefault("search_results", 8)          # maximo de resultados por busca (a IA escolhe quantos, ate aqui; 1 a 25)
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

# ---------------------------------------------------------------- contas no PC + aparelhos confiaveis
ACTIVE_ACCOUNT = ""   # "" = a conta do dono

def safe_account_name(raw):
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', str(raw or "")).strip(" .")[:40]
    if not name or name.upper() in ("CON", "PRN", "AUX", "NUL") or re.fullmatch(r"(COM|LPT)\d", name.upper()): return ""
    return name

def list_accounts():
    """Contas em que o PC pode entrar: a do dono e as criadas pelo iPhone/PC (as de amigos do /share ficam de fora)."""
    out = []
    try:
        for n in sorted(os.listdir(ACCOUNTS_DIR)):
            meta = _read_json(os.path.join(ACCOUNTS_DIR, n, "account.json"), {})
            if n != OWNER_NAME and isinstance(meta, dict) and meta.get("role") in ("iphone", "account"): out.append(n)
    except OSError: pass
    return out

def use_account(name):
    """Troca as conversas e memorias que o PC usa para accounts/<nome>/ ('' = a conta do dono)."""
    global HISTORY_FILE, STATE_FILE, ACTIVE_ACCOUNT
    name = "" if (not name or name == OWNER_NAME) else safe_account_name(name)
    if not name: d = OWNER_DIR
    else:
        d = os.path.join(ACCOUNTS_DIR, name); meta = os.path.join(d, "account.json")
        try:
            os.makedirs(d, exist_ok=True)
            if not os.path.exists(meta): _write_json(meta, {"name": name, "role": "account", "created": time.time(), "note": "Conta criada no PC."})
            else:
                role = (_read_json(meta, {}) or {}).get("role")
                if role not in ("iphone", "account"): return False   # conta de amigo: o PC nao entra
        except OSError: return False
    HISTORY_FILE, STATE_FILE = os.path.join(d, "history.json"), os.path.join(d, "state.json"); ACTIVE_ACCOUNT = name
    return True

def account_folder(name):
    return OWNER_DIR if (not name or name == OWNER_NAME) else os.path.join(ACCOUNTS_DIR, name)

# ---------------------------------------------------------------- importar o seu config.json (chaves e opcoes)
CONFIG_IMPORT_DENY = re.compile(r"password|^tokens$|owner|remote|^port$|https_port|active_account|guest|cloudflare_blocked|_neurons|_probe|cert", re.I)   # nunca vem de um arquivo: senha, sessoes, portas, acesso remoto, contas

def import_config(new, cfg):
    """Junta o config.json de outra instalacao nesta: so campos que ja existem aqui e com o mesmo tipo (texto, numero, lista...), menos os de seguranca.
    Devolve (config novo, quantos entraram, nomes ignorados). Nunca devolve valores."""
    if not isinstance(new, dict): raise ValueError("Esse arquivo nao e um config.json do Lume.")
    out, done, skipped = dict(cfg), 0, []
    for k, v in new.items():
        if CONFIG_IMPORT_DENY.search(k) or k not in cfg or type(v) is not type(cfg[k]) or v in ("", None): skipped.append(k); continue
        if out.get(k) != v: out[k] = v; done += 1
    return out, done, skipped

def export_accounts(all_accounts):
    names = ([""] + list_accounts()) if all_accounts else [ACTIVE_ACCOUNT]
    out = []
    for n in names:
        d = account_folder(n)
        out.append({"name": n or OWNER_NAME, "owner": not n, "history": _read_json(os.path.join(d, "history.json"), {}), "state": _read_json(os.path.join(d, "state.json"), {})})
    return {"format": "lume-accounts", "version": 1, "exported": time.time(), "accounts": out}

def import_accounts(data):
    """Junta as contas de um arquivo exportado nas contas daqui (conversas por id, memorias sem repetir). Devolve o resumo."""
    if not isinstance(data, dict) or data.get("format") != "lume-accounts" or not isinstance(data.get("accounts"), list): raise ValueError("Esse arquivo nao e uma exportacao de contas do Lume.")
    done = []
    for a in data["accounts"][:50]:
        if not isinstance(a, dict): continue
        name = "" if (a.get("owner") or str(a.get("name")) == OWNER_NAME) else safe_account_name(a.get("name"))
        if a.get("owner") is False and not name: continue
        d = account_folder(name)
        meta = _read_json(os.path.join(d, "account.json"), None) if name else {"role": "owner"}
        if name and meta is not None and (meta or {}).get("role") not in ("iphone", "account"): continue   # nao mexe em conta de amigo
        os.makedirs(d, exist_ok=True)
        if name and meta is None: _write_json(os.path.join(d, "account.json"), {"name": name, "role": "account", "created": time.time(), "note": "Conta importada de um arquivo."})
        hp, sp = os.path.join(d, "history.json"), os.path.join(d, "state.json")
        h = merge_history(_read_json(hp, {}), a.get("history") if isinstance(a.get("history"), dict) else {}); _write_json(hp, h)
        s = merge_state(_read_json(sp, {}), a.get("state") if isinstance(a.get("state"), dict) else {}); _write_json(sp, s)
        done.append({"name": name or OWNER_NAME, "chats": len(h)})
    return done

def merge_history(a, b):
    """Uniao das conversas (id -> conversa); na mesma conversa vale a que tem mais mensagens (empate: a segunda)."""
    out = dict(a) if isinstance(a, dict) else {}
    for cid, chat in (b.items() if isinstance(b, dict) else []):
        old = out.get(cid)
        if not isinstance(old, dict) or len((chat or {}).get("messages", [])) >= len(old.get("messages", [])): out[cid] = chat
    return out

def merge_state(a, b):
    out = dict(a) if isinstance(a, dict) else {}; b = b if isinstance(b, dict) else {}
    for k, v in b.items():
        if k == "memories" and isinstance(v, list):
            seen = {json.dumps(m, sort_keys=True, ensure_ascii=False) for m in out.get("memories", [])}
            out["memories"] = list(out.get("memories", [])) + [m for m in v if json.dumps(m, sort_keys=True, ensure_ascii=False) not in seen]
        elif k not in out: out[k] = v
    return out

# (a conta ativa e carregada em start_server: aqui a config ainda nao pode ser lida)

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
MAX_SEARCH_RESULTS = 8   # padrao; o valor real vem da configuracao "search_results"
_res_override = threading.local()   # quantos resultados a IA pediu nesta busca (nunca passa do maximo das configuracoes)

def max_results():
    try: cap = max(1, min(25, int(load_config().get("search_results", MAX_SEARCH_RESULTS))))
    except (TypeError, ValueError): cap = MAX_SEARCH_RESULTS
    n = getattr(_res_override, "n", None)
    return max(1, min(cap, n)) if n else cap


def _clean_html(text):
    return re.sub(r'\s+', ' ', html_mod.unescape(re.sub(r'<[^>]+>', '', text))).strip()

def _fetch(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers={**SEARCH_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=10) as r: return r.read(2_000_000).decode('utf-8', 'replace')

# ---------------------------------------------------------------- estatisticas de uso
_stats_lock = threading.Lock()

def pol_cost(model, ptok, otok):
    """Pollen gasto numa resposta do Pollinations (precos por milhao de tokens do catalogo; os gratis custam 0)."""
    if not str(model).startswith("pol:"): return 0.0
    slug = model[4:]; ex = dict(POL_MODELS).get(slug, {})
    if ex.get("free"): return 0.0
    try: m = pollinations_catalog(load_config().get("pollinations_api_key") or "").get(slug)
    except Exception: m = None
    pin, pout = _pol_price(m) if (m and m.get("pricing")) else (ex.get("pin", 0.0), ex.get("pout", 0.0))
    return (ptok * pin + otok * pout) / 1e6

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
        if e.get("type") != "chat" or str(e.get("model", "")).startswith(CLOUD_PREFIXES) or e.get("ts", 0) < now - 30 * 86400: continue
        sec, tk, age = e.get("seconds", 0.0), e.get("tokens", 0), now - e["ts"]
        if is_ollama_cloud(e.get("model")):
            if age <= 5 * 3600: oll["h5"]["requests"] += 1; oll["h5"]["seconds"] += sec; oll["h5"]["tokens"] += tk
            if age <= 7 * 86400: oll["d7"]["requests"] += 1; oll["d7"]["seconds"] += sec; oll["d7"]["tokens"] += tk
            mm = oll["month"].setdefault(e["model"], {"requests": 0, "seconds": 0.0, "tokens": 0}); mm["requests"] += 1; mm["seconds"] += sec; mm["tokens"] += tk
        elif age <= days * 86400:
            oll["local"]["requests"] += 1; oll["local"]["seconds"] += sec; oll["local"]["tokens"] += tk
    models, daily = {}, {}
    exa = {"searches": 0, "reads": 0, "cost": 0.0}
    tot = {"requests": 0, "tokens": 0, "seconds": 0.0, "pollen": 0.0}
    for e in evs:
        d = daily.setdefault(time.strftime("%Y-%m-%d", time.localtime(e["ts"])), {"requests": 0, "tokens": 0, "exa_cost": 0.0, "pollen": 0.0})
        if e.get("type") == "chat":
            m = models.setdefault(e.get("model", "?"), {"requests": 0, "tokens": 0, "seconds": 0.0, "best_tps": 0.0, "cloud": bool(e.get("cloud"))})
            tk, sec = e.get("tokens", 0), e.get("seconds", 0.0)
            m["requests"] += 1; m["tokens"] += tk; m["seconds"] += sec
            if sec > 0.2 and tk: m["best_tps"] = max(m["best_tps"], tk / sec)
            d["requests"] += 1; d["tokens"] += tk
            pl = e.get("pollen") or 0.0; d["pollen"] += pl; m["pollen"] = m.get("pollen", 0.0) + pl; tot["pollen"] += pl
            tot["requests"] += 1; tot["tokens"] += tk; tot["seconds"] += sec
        elif e.get("type") == "exa":
            exa["reads" if e.get("kind") == "contents" else "searches"] += 1
            exa["cost"] += e.get("cost") or 0.0; d["exa_cost"] += e.get("cost") or 0.0
    for m in models.values(): m["avg_tps"] = m["tokens"] / m["seconds"] if m["seconds"] > 0 else 0.0
    series = []
    for i in range(min(days, 14) - 1, -1, -1):
        day = time.strftime("%Y-%m-%d", time.localtime(now - i * 86400))
        series.append({"day": day, **daily.get(day, {"requests": 0, "tokens": 0, "exa_cost": 0.0, "pollen": 0.0})})
    return {"days": days, "totals": tot, "models": models, "exa": exa, "series": series, "since": min((e["ts"] for e in evs), default=None), "ollama": oll}

# ---------------------------------------------------------------- rodar codigo dos blocos
def python_exe():
    """O Python que roda os blocos de codigo: este mesmo (rodando pelo fonte) ou o Python instalado no PC (rodando como .exe)."""
    return (shutil.which("python") or shutil.which("py")) if FROZEN else sys.executable

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
    if FROZEN:   # no .exe o import acontece no Python instalado, entao e ele que diz o que falta
        py = python_exe()
        if not py: return [], bool(mods & GUI_MODULES)
        probe = "import sys, json, importlib.util\nstd = sys.stdlib_module_names\nprint(json.dumps([m for m in sys.argv[1:] if m not in std and m != '__future__' and importlib.util.find_spec(m) is None]))"
        try:
            r = subprocess.run([py, "-c", probe, *sorted(mods)], capture_output=True, text=True, timeout=30, creationflags=NOWIN, env=dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (PKG_DIR, os.environ.get("PYTHONPATH", "")) if p)))
            absent = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else []
        except Exception: absent = []
        for m in absent:
            pkg = PIP_NAMES.get(m, m.replace("_", "-"))
            if PIP_SPEC_RE.match(pkg) and pkg not in missing: missing.append(pkg)
        return missing, bool(mods & GUI_MODULES)
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

code_procs = {}; code_stopped = set()   # blocos de codigo rodando agora (rid -> processo) e os que o usuario mandou parar

def kill_tree(p):
    try:
        if os.name == "nt": subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NOWIN)
        else: p.kill()
    except Exception: pass

def stop_code(rid):
    p = code_procs.get(rid)
    if not p: return False
    code_stopped.add(rid); kill_tree(p); return True

def run_code(lang, code, analyze=False, install=False, rid=None):
    lang = (lang or "").lower()
    if lang not in RUN_LANGS: return {"error": "Linguagem sem botao de rodar."}
    if not isinstance(code, str) or not code.strip() or len(code) > 200000: return {"error": "Codigo vazio ou grande demais."}
    exe, args, missing, gui = None, [], [], False
    if lang == "python":
        exe = python_exe(); missing, gui = missing_python_packages(code)
        if not exe: return {"error": "Python nao encontrado neste PC (instale em python.org para rodar blocos Python)."}
    elif lang == "javascript": exe = shutil.which("node")
    elif lang == "powershell": exe = shutil.which("powershell")
    elif lang == "bat": exe = shutil.which("cmd")
    elif lang == "bash": exe = shutil.which("bash")
    if not exe: return {"error": {"javascript": "Node.js nao encontrado neste PC (instale em nodejs.org).", "bash": "Bash nao encontrado neste PC (instale o Git for Windows)."}.get(lang, "Interpretador nao encontrado.")}
    if analyze: return {"ok": True, "missing": missing, "gui": gui, "rule": dangerous_reason("cmd", {"command": code}) or ""}   # "rule": o que a lista de comandos perigosos achou (a bolinha usa)
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
            r = subprocess.run([python_exe(), "-m", "pip", "install", "--disable-pip-version-check", "--target", PKG_DIR, *missing], capture_output=True, text=True, timeout=600, creationflags=NOWIN, encoding="utf-8", errors="replace")
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
        if rid: code_procs[rid] = p
        try:
            outb, _ = p.communicate(timeout=3)
            if rid in code_stopped: return {"ok": False, "stopped": True, "output": out_install + outb.decode("utf-8", "replace")[-20000:], "seconds": round(time.time() - t0, 2)}
            return {"ok": p.returncode == 0, "exit": p.returncode, "output": out_install + outb.decode("utf-8", "replace")[-20000:], "seconds": round(time.time() - t0, 2)}
        except subprocess.TimeoutExpired:
            return {"ok": True, "detached": True, "output": out_install + "O programa abriu uma janela e continua rodando. Feche a janela dele quando terminar.", "seconds": 3}
        finally:
            code_procs.pop(rid, None); code_stopped.discard(rid)
    p = subprocess.Popen(cmd, cwd=RUN_DIR, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NOWIN)
    if rid: code_procs[rid] = p
    try:
        try:
            so, se = p.communicate(timeout=RUN_TIMEOUT); timed = False
        except subprocess.TimeoutExpired:
            kill_tree(p); so, se = p.communicate(); timed = True
        out = (so.decode("utf-8", "replace") + (("\n" if so else "") + se.decode("utf-8", "replace") if se else "")).strip()
        if rid in code_stopped: return {"ok": False, "stopped": True, "output": out_install + out[-20000:], "seconds": round(time.time() - t0, 2)}
        if timed: return {"ok": False, "exit": None, "timeout": True, "output": out_install + out[-20000:] + f"\n\n(parado: passou de {RUN_TIMEOUT} s)", "seconds": RUN_TIMEOUT}
        return {"ok": p.returncode == 0, "exit": p.returncode, "output": out_install + out[-20000:], "seconds": round(time.time() - t0, 2)}
    finally:
        code_procs.pop(rid, None); code_stopped.discard(rid)

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
def sniff_kind(data):
    """Descobre o tipo pelo CONTEUDO (nao pela extensao): pdf | image | docx | xlsx | pptx | odf | zip | text | binary."""
    h = data[:12]
    if h.startswith(b"%PDF"): return "pdf"
    if h.startswith(b"\x89PNG") or h[:3] == b"\xff\xd8\xff" or h[:4] == b"GIF8" or (h[:4] == b"RIFF" and data[8:12] == b"WEBP") or h[:2] == b"BM": return "image"
    if h[:2] == b"PK":
        try: names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except Exception: return "binary"
        if "word/document.xml" in names: return "docx"
        if "xl/workbook.xml" in names: return "xlsx"
        if "ppt/presentation.xml" in names: return "pptx"
        if "content.xml" in names and "mimetype" in names: return "odf"
        return "zip"
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"): return "text"   # UTF-16 com BOM
    if not data: return "text"
    sample = data[:8000]
    if b"\x00" in sample: return "binary"
    txt = sample.decode("utf-8", "replace")
    bad = sum(1 for c in txt if (ord(c) < 32 and c not in "\r\n\t\f\b") or c == "\ufffd")
    return "text" if bad <= max(2, len(txt) // 50) else "binary"

def decode_text(data):
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"): return data.decode("utf-16", "replace")
    try: return data.decode("utf-8-sig")
    except UnicodeDecodeError: return data.decode("latin-1")

def _local(tag): return tag.rsplit("}", 1)[-1]

def _runs_text(el):
    out = []
    for n in el.iter():
        t = _local(n.tag)
        if t == "t" and n.text: out.append(n.text)
        elif t == "tab": out.append("\t")
        elif t in ("br", "cr"): out.append("\n")
    return "".join(out)

def _zip_xml(z, name, limit=60 * 1048576):
    if z.getinfo(name).file_size > limit: raise Exception("O arquivo e grande demais para ler.")
    return ET.fromstring(z.read(name))

def docx_text(z):
    root = _zip_xml(z, "word/document.xml"); lines = []
    def walk(parent):
        for c in parent:
            t = _local(c.tag)
            if t == "p": lines.append(_runs_text(c))
            elif t == "tbl":
                for tr in c:
                    if _local(tr.tag) == "tr": lines.append(" | ".join(" ".join(_runs_text(p) for p in tc.iter() if _local(p.tag) == "p") for tc in tr if _local(tc.tag) == "tc"))
            elif t in ("sdt", "sdtContent"): walk(c)
    walk(next((c for c in root if _local(c.tag) == "body"), root))
    return "\n".join(lines)

def _col_index(ref):
    n = 0
    for ch in re.match(r"[A-Za-z]*", ref or "").group(0).upper(): n = n * 26 + ord(ch) - 64
    return max(0, n - 1)

def xlsx_text(z, limit):
    names = set(z.namelist()); shared = []
    if "xl/sharedStrings.xml" in names:
        shared = ["".join(x.text or "" for x in si.iter() if _local(x.tag) == "t") for si in _zip_xml(z, "xl/sharedStrings.xml")]
    wb = _zip_xml(z, "xl/workbook.xml"); relmap = {}
    if "xl/_rels/workbook.xml.rels" in names: relmap = {r.get("Id"): r.get("Target", "") for r in _zip_xml(z, "xl/_rels/workbook.xml.rels")}
    rid_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    sheets = []
    for sh in wb.iter():
        if _local(sh.tag) == "sheet":
            tgt = relmap.get(sh.get(rid_key), ""); path = tgt.lstrip("/") if tgt.startswith("/") else "xl/" + tgt
            if path in names: sheets.append((sh.get("name") or "?", path))
    parts, total = [], 0
    for name, path in sheets:
        parts.append(f"--- planilha: {name} ---")
        for row in _zip_xml(z, path).iter():
            if _local(row.tag) != "row": continue
            cells = {}
            for c in row:
                if _local(c.tag) != "c": continue
                typ = c.get("t"); v = next((x.text for x in c if _local(x.tag) == "v"), None)
                if typ == "s": val = shared[int(v)] if v is not None and int(v) < len(shared) else ""
                elif typ == "inlineStr": val = "".join(x.text or "" for x in c.iter() if _local(x.tag) == "t")
                elif typ == "b": val = "VERDADEIRO" if v == "1" else "FALSO"
                else: val = v or ""
                if val != "": cells[_col_index(c.get("r"))] = val.replace("\n", " ")
            if cells:
                line = "\t".join(cells.get(i, "") for i in range(max(cells) + 1)); parts.append(line); total += len(line)
            if total > limit: return "\n".join(parts)
    return "\n".join(parts)

def pptx_text(z):
    slides = sorted((n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)), key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)))
    parts = []
    for i, n in enumerate(slides, 1):
        paras = [x for x in (_runs_text(p).strip() for p in _zip_xml(z, n).iter() if _local(p.tag) == "p") if x]
        parts.append(f"--- slide {i} ---\n" + "\n".join(paras))
    return "\n\n".join(parts)

def odf_text(z):
    return "\n".join(x for x in ("".join(e.itertext()).strip() for e in _zip_xml(z, "content.xml").iter() if _local(e.tag) in ("p", "h")) if x)

def extract_file_text(filename, data):
    """Retorna (texto, cortado?, paginas). O tipo vem do CONTEUDO: texto/codigo (qualquer codificacao comum), PDF, Word, Excel, PowerPoint e LibreOffice."""
    kind = sniff_kind(data); pages = None
    if kind == "pdf":
        try: from pypdf import PdfReader
        except ImportError: raise Exception("Para ler PDF instale o pypdf: pip install pypdf")
        reader = PdfReader(io.BytesIO(data)); pages = len(reader.pages); parts = []; total = 0
        for i, page in enumerate(reader.pages, 1):
            t = (page.extract_text() or "").strip()
            if t: parts.append(f"--- pagina {i} ---\n{t}"); total += len(t)
            if total > MAX_FILE_CHARS: break
        text = "\n\n".join(parts)
        if not text.strip(): raise Exception("Este PDF nao tem texto selecionavel (talvez seja escaneado).")
    elif kind in ("docx", "xlsx", "pptx", "odf"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                text = docx_text(z) if kind == "docx" else xlsx_text(z, MAX_FILE_CHARS) if kind == "xlsx" else pptx_text(z) if kind == "pptx" else odf_text(z)
        except zipfile.BadZipFile: raise Exception("O arquivo esta corrompido.")
        except ET.ParseError: raise Exception("Nao consegui ler o conteudo do arquivo (XML invalido).")
        if not text.strip(): raise Exception("Nao encontrei texto neste arquivo.")
    elif kind == "text": text = decode_text(data)
    elif kind == "image": raise Exception("Este arquivo e uma imagem: anexe como imagem.")
    else: raise Exception("Arquivo binario nao suportado (use texto, codigo, PDF, Word, Excel ou PowerPoint).")
    return text[:MAX_FILE_CHARS], len(text) > MAX_FILE_CHARS, pages

if lumebrowser: lumebrowser.PDF_TEXT = lambda data: extract_file_text("pagina.pdf", data)   # a ponte do navegador le o PDF da pagina com o mesmo leitor dos anexos

def suggest_ext(kind, data):
    """Extensao certa para o tipo reconhecido pelo conteudo (usada quando o arquivo veio com uma extensao que ninguem conhece)."""
    if kind == "image":
        h = data[:12]
        return ".png" if h.startswith(b"\x89PNG") else ".jpg" if h[:3] == b"\xff\xd8\xff" else ".gif" if h[:4] == b"GIF8" else ".webp" if h[:4] == b"RIFF" else ".bmp"
    if kind == "odf":
        try: mt = zipfile.ZipFile(io.BytesIO(data)).read("mimetype").decode("ascii", "ignore")
        except Exception: mt = ""
        return ".ods" if "spreadsheet" in mt else ".odp" if "presentation" in mt else ".odt"
    return {"text": ".txt", "pdf": ".pdf", "docx": ".docx", "xlsx": ".xlsx", "pptx": ".pptx"}.get(kind, "")

def extract_api(data):
    """Corpo e status HTTP de /api/extract_text. Com "sniff", um arquivo de extensao desconhecida e identificado pelo conteudo."""
    try:
        raw = base64.b64decode(data.get("b64", "")); kind = sniff_kind(raw)
        if kind == "image" and data.get("sniff"): return {"kind": "image", "ext": suggest_ext(kind, raw)}, 200
        text, truncated, pages = extract_file_text(str(data.get("filename", "")), raw)
        return {"text": text, "truncated": truncated, "chars": len(text), "pages": pages, "kind": kind, "ext": suggest_ext(kind, raw)}, 200
    except Exception as e:
        return {"error": str(e)}, 400

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

def _to_int(v):
    try: return int(float(v))
    except (TypeError, ValueError): return None

def search_web_results(query, guest=False, n=None):
    """Pesquisa com no maximo n resultados (n vem da IA; o teto e o das configuracoes)."""
    _res_override.n = _to_int(n)
    try: return _search_web_results(query, guest, _to_int(n))
    finally: _res_override.n = None

def _search_web_results(query, guest=False, n=None):
    """Exa (se houver chave e limite diario), depois DuckDuckGo, depois Wikipedia. Retorna ([(titulo, trecho, link)], fonte) ou ([], None)."""
    cfg = load_config(); key = exa_api_key(cfg); provider = cfg.get("search_provider", "auto")
    if guest: key, provider = "", "duckduckgo"   # amigos nunca gastam o Exa
    ck = ("g:" if guest else "") + re.sub(r"\s+", " ", (query or "").strip().lower()) + (f"#{max_results()}" if n else "")
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

def search_web(query, n=None):
    results, source = search_web_results(query, n=n)
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
- write_file {"path": "arquivo.txt", "content": "texto"} : cria ou sobrescreve um arquivo INTEIRO (pede permissao)
- edit_file {"path": "arquivo.txt", "old": "trecho exato", "new": "trecho novo"} : troca SO um trecho do arquivo (pede permissao). Prefira esta para mudancas pequenas: leia o arquivo antes e copie o trecho "old" exatamente como esta; ele precisa aparecer uma unica vez (inclua linhas ao redor se precisar). Opcional: "replace_all": true
- cmd {"command": "dir"} : executa no CMD (pede permissao)
- powershell {"command": "Get-Date"} : executa no PowerShell (pede permissao)
- search_web {"query": "texto"} : pesquisa na web
- read_url {"url": "https://..."} : le o texto de uma pagina da web (use depois de search_web para ler uma fonte)
Faca UMA chamada por vez; o resultado volta na proxima mensagem. Quando terminar, responda normalmente, sem ferramentas.
"""

WEB_TOOL_PROMPT = """

PESQUISA NA WEB (ferramenta): voce pode pesquisar na internet quando precisar de informacao atual ou que voce nao sabe. Quem decide e voce: NAO pesquise em cumprimentos, conversa comum, ou o que voce ja sabe.
Para pesquisar, responda SO com isto e pare de escrever (a busca e feita com as palavras-chave que VOCE escolher):
$$[TOOL: search_web] {"query": "palavras-chave da busca", "results": 5}$$
"results" e quantos resultados voce quer (1 a 25; 3 a 5 bastam para perguntas simples, use mais so para pesquisas amplas: menos resultados = mais rapido e mais barato).
Para ler uma pagina de uma fonte: $$[TOOL: read_url] {"url": "https://..."}$$
Depois de receber os resultados, responda ao usuario citando os links usados. Se os resultados nao ajudarem, diga isso.
"""

WEB_TOOL_PROMPT_EN = """

WEB SEARCH (tool): you can search the internet when you need current information or something you do not know. YOU decide: do NOT search for greetings, small talk, or things you already know.
To search, reply ONLY with this and stop writing (the search uses the keywords YOU choose):
$$[TOOL: search_web] {"query": "search keywords", "results": 5}$$
"results" is how many results you want (1-25; 3 to 5 is enough for simple questions, use more only for broad research: fewer results = faster and cheaper).
To read a page from a source: $$[TOOL: read_url] {"url": "https://..."}$$
After you receive the results, answer the user citing the links you used. If the results do not help, say so.
"""

TOOL_PROMPT_EN = """

[AGENT MODE]
You can use tools on the user's computer. Working folder: {workdir}
To call a tool, write EXACTLY this format and STOP writing right after it:
$$[TOOL: name] {"argument": "value"}$$
Tools:
- list_files {"path": "."} : list the files in a folder
- read_file {"path": "file.txt"} : read a file
- write_file {"path": "file.txt", "content": "text"} : create or overwrite a WHOLE file (asks permission)
- edit_file {"path": "file.txt", "old": "exact snippet", "new": "new snippet"} : replace ONLY a part of the file (asks permission). Prefer this for small changes: read the file first and copy "old" exactly as it is; it must appear exactly once (include surrounding lines if needed). Optional: "replace_all": true
- cmd {"command": "dir"} : run in CMD (asks permission)
- powershell {"command": "Get-Date"} : run in PowerShell (asks permission)
- search_web {"query": "text"} : search the web
- read_url {"url": "https://..."} : read the text of a web page (use after search_web to read a source)
Make ONE call at a time; the result comes back in the next message. When you are done, answer normally, without tools.
"""

PATH_TOOLS = ("list_files", "read_file", "write_file", "edit_file")

def normalize_args(name, args):
    """Aceita argumentos mal formados (chave errada) pegando o primeiro valor."""
    if not isinstance(args, dict): args = {}
    key = "command" if name in ("cmd", "powershell") else "query" if name == "search_web" else "url" if name == "read_url" else "path" if name in PATH_TOOLS else None
    if key and key not in args and args:
        args[key] = list(args.values())[0]
    return args

def describe_tool(name, args):
    if name in COMPUTER_TOOLS: return describe_computer(name, args)
    if name in ("cmd", "powershell"): return f"{name}: {args.get('command', '')}"
    if name == "write_file": return f"Escrever arquivo: {args.get('path', '')} ({len(args.get('content', ''))} caracteres)"
    if str(name).startswith("mcp__"):
        d = lumemcp.find_tool(name) if lumemcp else None
        if d and d.get("kind") == "browser": return f"Navegador: {d['tool']} {json.dumps(args, ensure_ascii=False)[:300]}"
        return f"Ferramenta MCP \"{d['tool'] if d else name}\" do servidor \"{d['server'] if d else '?'}\" com: {json.dumps(args, ensure_ascii=False)[:300]}"
    if name == "edit_file": return f"Editar arquivo: {args.get('path', '')} (trocar {len(str(args.get('old', '')))} por {len(str(args.get('new', '')))} caracteres)"
    return f"{name} {args}"

def needs_permission(name):
    return name in ("cmd", "powershell", "write_file", "edit_file") or name in COMPUTER_TOOLS or str(name).startswith("mcp__")

# ---- "permitir sozinho": com o botao ligado, comandos comuns rodam sem perguntar, mas estes NUNCA rodam (nem perguntando)
_ROOTS = r"(?:[a-z]:[\\/]?(?:\*|\s|$|[\"'])|%(?:systemroot|windir|systemdrive|programfiles|userprofile|appdata|homepath)%|[a-z]:[\\/](?:windows|program files|program files \(x86\)|programdata|users)(?:[\\/]?\s|[\\/]?$|[\\/]?[\"'])|[a-z]:[\\/]users[\\/][^\\/\s\"']+[\\/]?(?:\s|$|[\"'])|~[\\/]?(?:\s|$)|(?:^|[\s\x22'])/(?:\s|$)|\$env:(?:systemroot|windir|userprofile|appdata|programfiles))"
DANGEROUS = [
    (r"\bdiskpart\b", "diskpart (mexe em discos e particoes)"),
    (r"(^|[\s;&|(])format(?:\.com)?\s+(?:[a-z]:|/)", "format (apaga um disco)"),
    (r"\b(?:format-volume|clear-disk|initialize-disk|remove-partition|set-disk|new-partition|reset-physicaldisk|resize-partition)\b", "comando de disco do PowerShell"),
    (r"\bmkfs(?:\.\w+)?\b|\b(?:s?fdisk|parted|wipefs|mkswap)\b", "formatar/particionar disco"),
    (r"\bdd\b[^|;&]*\bof=", "dd gravando em disco"),
    (r"\b(?:bcdedit|bootrec|diskshadow|mountvol)\b", "configuracao de boot/disco do Windows"),
    (r"\bcipher\b[^|;&]*/w", "cipher /w (apaga o espaco livre)"),
    (r"\b(?:vssadmin|wbadmin|wmic\s+shadowcopy)\b[^|;&]*\bdelete\b", "apagar copias de seguranca do Windows"),
    (r"\bshutdown(?:\.exe)?\s+[/-]|\b(?:restart-computer|stop-computer)\b", "desligar/reiniciar o PC"),
    (r"\breg(?:\.exe)?\s+(?:delete|add|import|load|restore|unload)\b", "mexer no registro do Windows"),
    (r"\b(?:remove-item|set-itemproperty|new-itemproperty|clear-item)\b[^|;&]*\bhk(?:lm|cu|cr|u):", "mexer no registro do Windows"),
    (r"\bnet(?:1)?\s+(?:user|localgroup|accounts)\b", "mexer em contas de usuario"),
    (r"\b(?:takeown|set-executionpolicy)\b|\bicacls\b[^|;&]*/(?:grant|reset|setowner|deny)", "mudar permissoes do sistema"),
    (r"\bsc(?:\.exe)?\s+(?:delete|create|config|stop)\b|\b(?:remove-service|new-service)\b", "mexer em servicos do Windows"),
    (r"\bschtasks(?:\.exe)?\b[^|;&]*/(?:create|delete|change)\b|\b(?:register-scheduledtask|unregister-scheduledtask)\b", "mexer em tarefas agendadas"),
    (r"\b(?:iwr|invoke-webrequest|irm|invoke-restmethod|curl|wget)\b[^\n]*\|\s*(?:iex|invoke-expression|sh|bash|cmd|powershell|pwsh|python)\b|\b(?:iex|invoke-expression)\b[^\n]*\b(?:downloadstring|invoke-webrequest|iwr|irm)\b", "baixar e executar codigo da internet"),
    (r"\b(?:stop-process|taskkill)\b[^|;&]*\b(?:winlogon|csrss|lsass|svchost|explorer|wininit|services)\b", "encerrar processo do sistema"),
]
_DANGEROUS_RE = [(re.compile(p, re.I), why) for p, why in DANGEROUS]
_DELETE_RE = re.compile(r"\b(?:rd|rmdir|del|erase|rm|remove-item|ri)\b", re.I)
_RECURSIVE_RE = re.compile(r"(?:^|\s)(?:/s|-r|-rf|-fr|-recurse|-force)\b", re.I)
_ROOTS_RE = re.compile(_ROOTS, re.I)
_SYSTEM_PATH_RE = re.compile(r"^[a-z]:[\\/](?:windows|program files|program files \(x86\)|programdata)(?:[\\/]|$)|[\\/]start menu[\\/]programs[\\/]startup", re.I)

def dangerous_reason(name, args):
    """Motivo (texto) se esta chamada nunca deve rodar no modo "permitir sozinho"; None se pode."""
    if name in ("write_file", "edit_file"):
        path = str(args.get("path", "")).replace("/", "\\")
        full = path if os.path.isabs(path) else ""
        if full and _SYSTEM_PATH_RE.search(full): return "gravar em pasta do sistema"
        return None
    cmd = str(args.get("command", ""))
    for rx, why in _DANGEROUS_RE:
        if rx.search(cmd): return why
    for part in re.split(r"[;&|\n]+", cmd):
        if _DELETE_RE.search(part) and _RECURSIVE_RE.search(part) and _ROOTS_RE.search(part): return "apagar uma pasta inteira do sistema ou do seu usuario"
    return None

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
        if tool_name == "edit_file":
            path = full(tool_args["path"]); old = str(tool_args.get("old", "")); new = str(tool_args.get("new", ""))
            if not os.path.isfile(path): return L("Erro: o arquivo nao existe. Para criar um arquivo novo use write_file.", "Error: the file does not exist. To create a new file use write_file.")
            if not old: return L("Erro: \"old\" esta vazio. Passe o trecho exato que deve ser trocado.", "Error: \"old\" is empty. Pass the exact snippet to replace.")
            with open(path, "rb") as f: raw = f.read()
            if b"\x00" in raw[:8000]: return L("Erro: esse arquivo e binario; nao da para editar um trecho.", "Error: this file is binary; a snippet cannot be edited.")
            text = raw.decode("utf-8", "replace"); crlf = "\r\n" in text; work = text.replace("\r\n", "\n")   # compara com quebras de linha iguais; CRLF volta ao gravar
            o = old.replace("\r\n", "\n"); n = new.replace("\r\n", "\n"); count = work.count(o)
            if count == 0:
                first = next((ln.strip() for ln in o.split("\n") if ln.strip()), "")
                hint = L(f" A primeira linha do trecho (\"{first[:60]}\") ", f" The first line of the snippet (\"{first[:60]}\") ") + (L("existe no arquivo: confira espacos e linhas em volta.", "exists in the file: check the spaces and surrounding lines.") if first and first in work else L("nao aparece no arquivo.", "does not appear in the file."))
                return L("Erro: o trecho \"old\" nao foi encontrado no arquivo. Leia o arquivo de novo e copie o trecho exatamente.", "Error: the \"old\" snippet was not found in the file. Read the file again and copy the snippet exactly.") + hint
            if count > 1 and not tool_args.get("replace_all"): return L(f"Erro: o trecho aparece {count} vezes. Inclua mais linhas em volta para ele ser unico, ou use \"replace_all\": true.", f"Error: the snippet appears {count} times. Include more surrounding lines to make it unique, or use \"replace_all\": true.")
            out = work.replace(o, n) if tool_args.get("replace_all") else work.replace(o, n, 1)
            if crlf: out = out.replace("\n", "\r\n")
            with open(path, "w", encoding="utf-8", newline="") as f: f.write(out)
            uid = save_undo(path, True, raw)
            diff = list(difflib.unified_diff(work.splitlines(), out.replace("\r\n", "\n").splitlines(), L("antes", "before"), L("depois", "after"), lineterm="", n=2))
            shown = ("\n".join(diff[:120]) + (L(f"\n... (+{len(diff) - 120} linhas)", f"\n... (+{len(diff) - 120} lines)") if len(diff) > 120 else "")) or L("(sem alteracoes)", "(no changes)")
            return f"{L('Trecho trocado com sucesso', 'Snippet replaced successfully')}{L(f' ({count} lugares)', f' ({count} places)') if count > 1 and tool_args.get('replace_all') else ''}. [undo:{uid}]\n```diff\n{shown}\n```"
        if tool_name in ("cmd", "powershell"):
            cmd = tool_args["command"]
            argv = cmd if tool_name == "cmd" else ["powershell", "-NoProfile", "-Command", cmd]
            r = subprocess.run(argv, shell=(tool_name == "cmd"), capture_output=True, text=True, errors="replace", timeout=TOOL_TIMEOUT, cwd=workdir)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0: out += L(f"\n[codigo de saida {r.returncode}]", f"\n[exit code {r.returncode}]")
            return truncate(out.strip() or L("(sem saida)", "(no output)"))
        if tool_name == "search_web":
            return truncate(search_web(tool_args.get("query", ""), tool_args.get("results")))
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


# ---------------------------------------------------------------- controle do computador (aba Code): ver a tela, mexer no mouse e no teclado (so Windows, e so se ligado nas opcoes)
COMPUTER_TOOLS = ("take_screenshot", "list_windows", "use_apps", "launch_app", "close_app", "screenshot", "mouse_move", "mouse_click", "scroll", "type_text", "press_key")
COMPUTER_GRANT_SECS = 600      # depois de aprovar uma vez, a IA pode agir por 10 minutos sem perguntar de novo (renova a cada uso)
COMPUTER_USER_WAIT = 1.0       # se o dono estiver mexendo no mouse/teclado, a IA espera ele ficar parado 1 segundo
_mcp_grant = {}   # servidor MCP -> ate quando o dono liberou sem perguntar de novo
_comp = {"grant": 0.0, "scale": 1.0, "origin": (0, 0), "shot": False, "ai_tick": 0}
_VK = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "windows": 0x5B, "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "backspace": 0x08, "delete": 0x2E, "del": 0x2E,
       "space": 0x20, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "insert": 0x2D, **{f"f{i}": 0x6F + i for i in range(1, 13)}}

def computer_supported(): return sys.platform == "win32"

def _user_last_input_age_ms():
    """Ha quantos ms o DONO mexeu no mouse/teclado (ignora o que a propria IA fez)."""
    import ctypes
    class LII(ctypes.Structure): _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LII(); li.cbSize = ctypes.sizeof(LII)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)): return 10**9
    now = ctypes.windll.kernel32.GetTickCount()
    if li.dwTime <= _comp["ai_tick"] + 60: return 10**9      # a ultima entrada foi a nossa (ou mais antiga): o dono esta parado
    return (now - li.dwTime) & 0xFFFFFFFF

def _wait_for_user(stop_check=None, max_wait=30):
    """Espera o dono ficar 1 s sem mexer no mouse/teclado (no maximo 30 s)."""
    t0 = time.time()
    while _user_last_input_age_ms() < COMPUTER_USER_WAIT * 1000:
        if stop_check and stop_check(): raise RuntimeError("parado pelo usuario")
        if time.time() - t0 > max_wait: raise RuntimeError("o usuario esta usando o computador; tente de novo")
        time.sleep(0.1)

def _failsafe():
    import ctypes
    class PT(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    p = PT(); ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    if p.x <= 1 and p.y <= 1: raise RuntimeError("parado: o mouse esta no canto superior esquerdo da tela (parada de emergencia)")

def _mark_ai():
    import ctypes
    _comp["ai_tick"] = ctypes.windll.kernel32.GetTickCount()

def _key_event(vk, up=False, unicode_char=None):
    import ctypes
    from ctypes import wintypes
    class KI(ctypes.Structure): _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
    class MI(ctypes.Structure): _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
    class U(ctypes.Union): _fields_ = [("ki", KI), ("mi", MI)]
    class INP(ctypes.Structure): _fields_ = [("type", wintypes.DWORD), ("u", U)]
    flags = (0x0002 if up else 0) | (0x0004 if unicode_char is not None else 0)
    inp = INP(1, U(ki=KI(0 if unicode_char is not None else vk, ord(unicode_char) if unicode_char is not None else 0, flags, 0, 0)))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INP))

def _to_screen(x, y):
    """Coordenadas da ULTIMA captura (reduzida) -> coordenadas reais da tela."""
    if not _comp["shot"]: raise RuntimeError("tire um screenshot antes (as coordenadas vem dele)")
    ox, oy = _comp["origin"]; return int(ox + float(x) / _comp["scale"]), int(oy + float(y) / _comp["scale"])

def _find_window(title):
    import ctypes
    from ctypes import wintypes
    found = []
    EP = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        if not ctypes.windll.user32.IsWindowVisible(h): return True
        n = ctypes.windll.user32.GetWindowTextLengthW(h)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1); ctypes.windll.user32.GetWindowTextW(h, buf, n + 1)
            if title.lower() in buf.value.lower():
                r = wintypes.RECT(); ctypes.windll.user32.GetWindowRect(h, ctypes.byref(r))
                if r.right - r.left > 50 and r.bottom - r.top > 50: found.append((h, buf.value, (r.left, r.top, r.right, r.bottom)))
        return True
    ctypes.windll.user32.EnumWindows(EP(cb), 0); return found

# ---- a caixinha do Alt+Espaco (janela flutuante): o print da tela pode esconde-la por um instante, ou incluir
QUICK = {"win": None, "visible": False}
def quick_hide():
    w = QUICK["win"]
    if w and QUICK["visible"]:
        try:
            QUICK["visible"] = False   # ja conta como fechada: um segundo Alt+Espaco durante a animacao abre de novo
            try: w.evaluate_js("window.qhiding && qhiding()"); time.sleep(0.13)   # a caixinha some com um fade curto (a janela so esconde depois)
            except Exception: pass
            if not QUICK["visible"]: w.hide()
            return True
        except Exception: QUICK["visible"] = True
    return False
def quick_show():
    w = QUICK["win"]
    if w:
        try: w.show(); QUICK["visible"] = True
        except Exception: pass

def _virtual_wanted(name, args):
    """True quando a acao vai para um programa especifico (segundo plano, mouse virtual); False = a tela inteira com o mouse de verdade (modo antigo)."""
    if not vcomp: return False
    if name in ("take_screenshot", "list_windows", "use_apps", "launch_app", "close_app"): return True
    app = args.get("app"); apps = args.get("apps")
    if str(app or "").strip().lower() in ("screen", "tela", "full", "fullscreen"): return False
    return bool(apps) or str(app if app is not None else "").strip() != "" or bool(vcomp.workspace())

def computer_execute(name, args, stop_check=None):
    """Roda uma acao de controle do computador. Devolve (texto, imagem_base64 | lista de imagens | None)."""
    if not computer_supported(): return "Erro: o controle do computador so funciona no Windows por enquanto.", None
    import ctypes
    u = ctypes.windll.user32
    try:
        _focus_real = False
        if vcomp and args.get("focus") and name in ("mouse_move", "mouse_click", "scroll", "type_text", "press_key") and (args.get("app") not in (None, "") or vcomp.workspace()):
            # modo "focus": para programas que ignoram o controle em segundo plano. Traz o programa para a frente e usa o mouse/teclado de VERDADE (espera o dono parar de mexer)
            if stop_check and stop_check(): raise RuntimeError("parado pelo usuario")
            _failsafe(); _wait_for_user(stop_check); vcomp.activate(args.get("app"))
            if name != "type_text" and name != "press_key":
                _sx, _sy = vcomp.screen_point(args.get("app"), args.get("x"), args.get("y")); _comp.update(origin=(_sx - int(float(args.get('x'))), _sy - int(float(args.get('y')))), scale=1.0, shot=True)   # escala 1: _to_screen(x, y) cai no ponto certo e a mensagem mostra o x,y original
            _focus_real = True
        if not _focus_real and _virtual_wanted(name, args):   # segundo plano: o mouse e o teclado do dono ficam livres (nao espera nem mexe neles)
            if stop_check and stop_check(): raise RuntimeError("parado pelo usuario")
            if name != "screenshot": _failsafe()
            if name == "list_windows": return vcomp.windows_text(), None
            if name == "take_screenshot":   # print de UM alvo: app, titulo, .exe, PID ou "desktop" (o Lume usa o mais parecido e avisa se o nome exato nao existe)
                _tg = next((args.get(k) for k in ("target", "app", "name", "exe", "pid", "title", "window") if args.get(k) not in (None, "")), "desktop")
                _t, _imgs = vcomp.take_screenshot(_tg, bool(args.get("include_overlay")), quick_hide, quick_show); return _t, (_imgs or None)
            if name == "use_apps": return vcomp.use_apps(args.get("apps") or args.get("app")), None
            if name == "launch_app": return vcomp.launch(args.get("path") or args.get("app") or args.get("exe"), args.get("args") if isinstance(args.get("args"), list) else ([args["args"]] if args.get("args") else []), args.get("wait") or 15), None
            if name == "close_app": return vcomp.close(args.get("app"), bool(args.get("force"))), None
            if name == "screenshot":
                _t, _imgs = vcomp.screenshot(args.get("apps") or args.get("app") or "all"); return _t, (_imgs or None)
            if name in ("mouse_move", "mouse_click", "scroll"):
                if args.get("x") is None or args.get("y") is None: return "Erro: faltam x e y.", None
                return vcomp.mouse(name, args.get("app"), args.get("x"), args.get("y"), args.get("button"), bool(args.get("double")), args.get("amount") or -3), None
            if name in ("type_text", "press_key"): return vcomp.keyboard(name, args.get("app"), args.get("text") or "", args.get("key") or ""), None
        if name in ("list_windows", "use_apps", "launch_app", "close_app"): return "Erro: esta ferramenta precisa do modulo de segundo plano.", None
        if name != "screenshot": _failsafe(); _wait_for_user(stop_check)
        elif stop_check and stop_check(): raise RuntimeError("parado pelo usuario")
        if name == "screenshot":
            from PIL import ImageGrab
            app = str(args.get("app") or "").strip(); where = "tela inteira"; box = None
            if app.lower() in ("screen", "tela", "full", "fullscreen"): app = ""
            if app:
                wins = _find_window(app)
                if not wins: return f"Erro: nenhuma janela com \"{app}\" no titulo. Abra o app e tente de novo.", None
                h, title, box = max(wins, key=lambda w: (w[2][2] - w[2][0]) * (w[2][3] - w[2][1])); where = "janela \"" + title[:60] + "\""
                u.ShowWindow(h, 9); u.SetForegroundWindow(h); time.sleep(0.4)
            img = ImageGrab.grab(bbox=box) if box else ImageGrab.grab()
            if box: _comp["origin"] = (max(0, box[0]), max(0, box[1]))
            else: _comp["origin"] = (0, 0)
            W, H = img.size; k = min(1.0, 1280 / max(W, H)); _comp["scale"] = k; _comp["shot"] = True
            if k < 1: img = img.resize((int(W * k), int(H * k)))
            buf = io.BytesIO(); img.convert("RGB").save(buf, "JPEG", quality=70)
            return f"Captura de {where}: {img.size[0]}x{img.size[1]} pixels. As coordenadas x,y dos proximos cliques sao medidas nesta imagem (canto superior esquerdo = 0,0).", base64.b64encode(buf.getvalue()).decode()
        if name in ("mouse_move", "mouse_click", "scroll"):
            sx, sy = _to_screen(args.get("x"), args.get("y")); u.SetCursorPos(sx, sy); time.sleep(0.05)
            if name == "mouse_click":
                b = str(args.get("button") or "left").lower(); down, up = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40)}.get(b, (0x2, 0x4))
                for _ in range(2 if args.get("double") else 1): u.mouse_event(down, 0, 0, 0, 0); u.mouse_event(up, 0, 0, 0, 0); time.sleep(0.06)
                _mark_ai(); return f"Cliquei ({b}{', duplo' if args.get('double') else ''}) em {args.get('x')},{args.get('y')}.", None
            if name == "scroll":
                amt = int(args.get("amount") or -3); u.mouse_event(0x0800, 0, 0, amt * 120, 0); _mark_ai(); return f"Rolei {amt} em {args.get('x')},{args.get('y')}.", None
            _mark_ai(); return f"Mouse movido para {args.get('x')},{args.get('y')}.", None
        if name == "type_text":
            text = str(args.get("text") or "")[:2000]
            for ch in text:
                _failsafe()
                if ch == "\n": _key_event(0x0D); _key_event(0x0D, up=True)
                else: _key_event(0, unicode_char=ch); _key_event(0, up=True, unicode_char=ch)
                time.sleep(0.01)
            _mark_ai(); return f"Digitei {len(text)} caracteres.", None
        if name == "press_key":
            keys = [k.strip().lower() for k in str(args.get("key") or "").replace(" ", "").split("+") if k.strip()]
            if not keys: return "Erro: diga a tecla em \"key\" (ex.: \"enter\", \"ctrl+c\").", None
            vks = []
            for k in keys:
                if k in _VK: vks.append(_VK[k])
                elif len(k) == 1:
                    v = ctypes.windll.user32.VkKeyScanW(ord(k)) & 0xFF
                    if v == 0xFF: return f"Erro: tecla desconhecida: {k}", None
                    vks.append(v)
                else: return f"Erro: tecla desconhecida: {k}", None
            for v in vks: _key_event(v)
            for v in reversed(vks): _key_event(v, up=True)
            _mark_ai(); return "Apertei " + "+".join(keys) + ".", None
        return f"Ferramenta desconhecida: {name}", None
    except Exception as e:
        return f"Erro: {e}", None

def describe_computer(name, args):
    _ap = f" [app {args.get('app')}]" if args.get("app") not in (None, "") else ""
    if name == "list_windows": return "Ver quais programas estao abertos (so os titulos das janelas)"
    if name == "take_screenshot": return "TIRAR UM PRINT de: " + str(next((args.get(k) for k in ("target", "app", "name", "exe", "pid", "title", "window") if args.get(k) not in (None, "")), "a tela inteira")) + (" (incluindo a caixa do Alt+Espaco)" if args.get("include_overlay") else "")
    if name == "launch_app": return "ABRIR O PROGRAMA: " + str(args.get("path") or args.get("app") or args.get("exe") or "?") + ((" " + " ".join(str(a) for a in args["args"])) if isinstance(args.get("args"), list) and args["args"] else "")
    if name == "close_app": return "Fechar o programa" + _ap + (" (encerrando o processo se nao fechar)" if args.get("force") else "")
    if name == "use_apps": return "Usar estes programas em segundo plano: " + ", ".join(str(a) for a in (args.get("apps") if isinstance(args.get("apps"), list) else [args.get("apps") or args.get("app")]))
    if name == "screenshot": return "Ver " + (("o(s) programa(s): " + ", ".join(str(a) for a in (args.get("apps") if isinstance(args.get("apps"), list) else [args.get("apps")])) ) if args.get("apps") else f"o programa {args.get('app')}" if args.get("app") not in (None, "") else "a tela inteira")
    if name in ("mouse_move", "mouse_click", "scroll"): return f"{name} em ({args.get('x')}, {args.get('y')})" + _ap
    if name == "type_text": return "Digitar: " + str(args.get("text", ""))[:80] + _ap
    return f"Apertar a tecla: {args.get('key', '')}" + _ap

COMPUTER_PROMPT_PT = """- take_screenshot {"target": "Roblox.exe", "include_overlay": false} : tira UM print (so a imagem) do alvo: nome do app, parte do titulo da janela, nome do .exe, PID (numero) ou "desktop" (a tela toda), ou uma CATEGORIA: "browser", "terminal", "editor", "explorer", "chat" (tira um print de cada janela aberta da categoria, ate 3). Se o nome exato nao existir, o Lume usa o mais parecido (ex.: Roblox.exe -> RobloxPlayerBeta.exe) e avisa o dono. Navegador pedido que nao esta aberto mas e da mesma familia de outro que esta (ex.: "chrome" com so o Comet aberto) devolve o que esta aberto: diga SEMPRE o nome que o resultado informa (ex.: Comet), nunca o que voce pediu. include_overlay=true inclui a caixinha do Alt+Espaco no print do desktop (padrao: ela some por um instante)
- list_windows {} : lista os programas abertos (titulos das janelas)
- use_apps {"apps": ["titulo1", "titulo2", "titulo3"]} : escolhe ate 3 programas para usar AO MESMO TEMPO, em segundo plano (parte do titulo da janela)
- launch_app {"path": "C:\\caminho\\programa.exe", "args": ["arg1"], "wait": 15} : ABRE um programa (.exe, .bat) e espera a janela; ja o poe entre os usados (jogos, DOSBox com um programa de DOS, VirtualBox...). Pede permissao
- close_app {"app": 1, "force": false} : fecha o programa (force encerra o processo se ele nao fechar)
- screenshot {"app": "all"} ou {"app": 2} ou {"apps": [1, 3]} : foto de todos os programas escolhidos, de um ou de alguns (so a imagem; sem app = a tela inteira)
- mouse_click {"app": 1, "x": 100, "y": 200, "button": "left", "double": false} : clica no programa 1 (x e y medidos na ultima foto DELE)
  Em mouse_click, mouse_move, scroll, type_text e press_key voce pode somar "focus": true: traz o programa para a frente e usa o mouse e o teclado de VERDADE (espera o dono parar de mexer). Use so quando o modo normal nao funcionar: jogos, DOSBox, janelas que ignoram o controle em segundo plano.
- mouse_move {"app": 1, "x": 100, "y": 200} : move o mouse virtual
- scroll {"app": 1, "x": 100, "y": 200, "amount": -3} : rola (negativo = para baixo)
- type_text {"app": 1, "text": "texto"} : digita no campo que estiver com o foco dentro do programa
- press_key {"app": 1, "key": "enter"} : aperta uma tecla (enter, tab, esc, setas...). Atalhos com ctrl/alt podem nao funcionar em segundo plano
Controle do computador: voce usa um MOUSE VIRTUAL (uma bolinha) que nao mexe no mouse nem no teclado do dono: ele continua usando o PC normalmente. Voce pode VER ate 3 programas de uma vez, mas so CONTROLA UM por chamada (diga sempre "app": numero). SEMPRE tire um screenshot do programa antes de clicar nele e confira o resultado com outro depois. Se a foto vier preta ou o clique nao fizer nada, o programa nao aceita controle em segundo plano: diga isso ao dono. Ele para tudo movendo o mouse para o canto superior esquerdo.
"""
COMPUTER_PROMPT_EN = """- take_screenshot {"target": "Roblox.exe", "include_overlay": false} : takes ONE screenshot (image only) of the target: app name, part of a window title, .exe name, PID (number) or "desktop" (the whole screen), or a CATEGORY: "browser", "terminal", "editor", "explorer", "chat" (one screenshot of each open window in the category, up to 3). If the exact name does not exist, Lume uses the closest one (e.g. Roblox.exe -> RobloxPlayerBeta.exe) and tells the owner. A browser you ask for that is not open but shares an engine with one that is (e.g. "chrome" when only Comet is open) returns the one that is open: ALWAYS use the name the result gives (e.g. Comet), never the one you asked for. include_overlay=true includes the Alt+Space box in the desktop screenshot (default: it disappears for a moment)
- list_windows {} : list the open programs (window titles)
- use_apps {"apps": ["title1", "title2", "title3"]} : pick up to 3 programs to use AT THE SAME TIME, in the background (part of the window title)
- launch_app {"path": "C:\\path\\program.exe", "args": ["arg1"], "wait": 15} : OPENS a program (.exe, .bat) and waits for its window; it is added to the ones in use (games, DOSBox with a DOS program, VirtualBox...). Asks permission
- close_app {"app": 1, "force": false} : closes the program (force kills the process if it will not close)
- screenshot {"app": "all"} or {"app": 2} or {"apps": [1, 3]} : picture of all the chosen programs, one, or some (image only; no app = the whole screen)
- mouse_click {"app": 1, "x": 100, "y": 200, "button": "left", "double": false} : click in program 1 (x and y measured on ITS last picture)
  On mouse_click, mouse_move, scroll, type_text and press_key you can add "focus": true: it brings the program to the front and uses the REAL mouse and keyboard (waits for the owner to stop). Use it only when the normal mode does not work: games, DOSBox, windows that ignore background control.
- mouse_move {"app": 1, "x": 100, "y": 200} : move the virtual mouse
- scroll {"app": 1, "x": 100, "y": 200, "amount": -3} : scroll (negative = down)
- type_text {"app": 1, "text": "text"} : type into the focused field inside the program
- press_key {"app": 1, "key": "enter"} : press a key (enter, tab, esc, arrows...). Ctrl/Alt shortcuts may not work in the background
Computer control: you use a VIRTUAL MOUSE (a ball) that does not move the owner's mouse or keyboard: they keep using the PC normally. You can SEE up to 3 programs at once but only CONTROL ONE per call (always say "app": number). ALWAYS take a screenshot of the program before clicking in it and check the result with another afterwards. If the picture is black or a click does nothing, the program does not accept background control: tell the owner. They stop everything by moving the mouse to the top-left corner of the screen.
"""

COMPUTER_CHAT_PT = """

CONTROLE DO COMPUTADOR (ferramenta): voce pode ver a tela do dono e mexer no mouse e no teclado, MAS SO quando ele pedir isso (ver a tela, abrir algo, clicar, digitar). NAO use em conversa comum.
Para chamar uma ferramenta, escreva EXATAMENTE neste formato e PARE de escrever logo depois: $$[TOOL: nome] {"argumento": "valor"}$$
Ferramentas:
""" + COMPUTER_PROMPT_PT + """Faca UMA chamada por vez; o resultado volta na proxima mensagem. Quando terminar, responda normalmente, sem ferramentas.
"""
COMPUTER_CHAT_EN = """

COMPUTER CONTROL (tool): you can see the owner's screen and use the mouse and keyboard, BUT ONLY when they ask for it (look at the screen, open something, click, type). Do NOT use it in normal conversation.
To call a tool, write EXACTLY this format and STOP writing right after it: $$[TOOL: name] {"argument": "value"}$$
Tools:
""" + COMPUTER_PROMPT_EN + """Make ONE call at a time; the result comes back in the next message. When you are done, answer normally, without tools.
"""

TOOL_NAMES = ("list_files", "read_file", "write_file", "edit_file", "cmd", "powershell", "search_web", "read_url") + COMPUTER_TOOLS
TOOL_MARK = re.compile(r'(?:\$\$\s*)?\[\s*TOOL\s*[:\s]\s*(\w+)[^\]]*\]', re.IGNORECASE)   # "$$" na frente e opcional
TOOL_MARK_SHORT = re.compile(r'\$\$\s*\[\s*(' + "|".join(TOOL_NAMES) + r')\s*\]', re.IGNORECASE)   # "$$[cmd] {...}$$" (sem a palavra TOOL)
TOOL_INLINE = re.compile(r'\$\$\s*\[\s*(cmd|powershell|search_web|read_url|read_file|list_files)\s*[:=]\s*(.+?)\s*\]\s*\$\$', re.IGNORECASE | re.DOTALL)   # "$$[cmd: "dir"]$$"
INLINE_KEY = {"cmd": "command", "powershell": "command", "search_web": "query", "read_url": "url", "read_file": "path", "list_files": "path"}   # write_file nunca (precisa do conteudo)
FENCE_MARK = re.compile(r'```[ \t]*(' + "|".join(TOOL_NAMES) + r')\b', re.IGNORECASE)    # modelos pequenos as vezes usam ```powershell {...}```
ARG_KEYS = {"command", "path", "content", "query", "url", "old", "new", "replace_all"}

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

ANNOUNCE_RE = re.compile(r"(?i)\b(vou|vamos|irei|farei|i'?ll|i will|let me)\s+(agora\s+)?(atualizar|criar|escrever|editar|rodar|executar|salvar|gravar|ler|abrir|instalar|update|create|write|edit|run|save|read|open|install)\b[^?]{0,200}$")
# "i'm rewriting the whole thing", "estou reescrevendo tudo", "give it a sec", "um segundo": o modelo diz que esta agindo e para sem chamar nada
ANNOUNCE_ING_RE = re.compile(r"(?i)\b(i'?m|i am|im|estou|t[oô])\s+(gonna\s+|going to\s+|now\s+|agora\s+)?(re)?(writ|patch|updat|fix|edit|creat|build|redo|read|run|sav|rewrit|criand|escrevend|reescrevend|atualizand|corrigind|salvand|lendo|rodand|execut|ajustand|refazend|mexend)\w*")
ANNOUNCE_WAIT_RE = re.compile(r"(?i)(give (it|me) a (sec|second|moment|minute)|one (sec|moment|second)\b|hold on\b|bear with me|working on it|\bbrb\b|um (segundo|momento|instante|instantinho)|j[aá] volto|s[oó] um (segundo|momento)|aguarde)")
ANNOUNCE_LEMME_RE = re.compile(r"(?i)\b(lemme|let me|let'?s|gimme|i'?ll|i will|i'?m gonna|gonna|deixa eu|deixe-me|me deixa|vou|vamos|primeiro vou)\s+(just\s+|first\s+|now\s+|quickly\s+|s[oó]\s+|primeiro\s+|agora\s+)?(see|check|look|read|peek|grab|take|open|view|print|show|find|inspect|fix|patch|try|get|ver|olhar|checar|conferir|verificar|abrir|pegar|mostrar|achar|procurar|tentar|consertar|corrigir)\b")
INVENTED_RE = re.compile(r"(?i)(\[\s*(?:resultado de|result of)\s+\w+\s*\]|[\u2713\u2717]\s*(?:result of|resultado de)\b|tool result missing|oops,? tool|\[\s*/(?:resultado|result)\s*\])")
def invented_result(text):
    """A IA escreveu um \"resultado\" de ferramenta por conta propria (nada rodou de verdade)."""
    return bool(INVENTED_RE.search(text or ""))

def announces_action(text):
    """O modelo disse que ia fazer algo (\"vou atualizar o arquivo\") mas terminou sem chamar nenhuma ferramenta."""
    tail = (text or "").strip()[-300:]
    if tail.endswith("?"): return False   # terminou perguntando: nao e uma promessa
    if tail.endswith(":") and not tail.endswith("::"): return True   # "...pra eu escolher a ancora certa:" e para: prometeu mostrar/fazer algo e nao chamou nada
    if ANNOUNCE_LEMME_RE.search(tail) and not re.search(r"(?i)\b(let me know|lemme know|me avise|me diga|me fala)\b", tail): return True
    return bool(ANNOUNCE_RE.search(tail) or ANNOUNCE_ING_RE.search(tail) or ANNOUNCE_WAIT_RE.search(tail) or re.search(r"(?i)need (a |the )?tool call", tail))   # alguns modelos vazam "need tool call" no texto em vez de chamar

def looks_like_failed_call(text):
    """A IA tentou chamar uma ferramenta mas errou o formato (nada foi reconhecido)."""
    return bool(re.search(r'\[\s*TOOL|\$\$\s*\[', text, re.I) or re.search(r'\{\s*"(command|path|query|content)"\s*:', text))

CORRECTION_PT = 'Formato invalido: nenhuma ferramenta foi executada. Para usar uma ferramenta escreva EXATAMENTE $$[TOOL: nome] {"argumento": "valor"}$$ (sem bloco de codigo) e pare de escrever. Tente de novo.'
CORRECTION_EN = 'Invalid format: no tool was run. To use a tool write EXACTLY $$[TOOL: name] {"argument": "value"}$$ (no code block) and stop writing. Try again.'
SCOLD_PT = 'PARE. Voce acabou de INVENTAR o resultado de uma ferramenta: nada disso rodou de verdade, voce escreveu um resultado falso. NUNCA escreva "[resultado de ...]", "result of", "(no output)" nem nada parecido: quem devolve resultado e o Lume, so DEPOIS que voce fizer a chamada e PARAR de escrever. Refaca agora: escreva so a chamada, EXATAMENTE $$[TOOL: nome] {"argumento": "valor"}$$ (sem bloco de codigo), e pare.'
SCOLD_EN = 'STOP. You just MADE UP a tool result: none of that actually ran, you wrote a fake result. NEVER write "[result of ...]", "result of", "(no output)" or anything like it: the result is returned by Lume, only AFTER you make the call and STOP writing. Redo it now: write only the call, EXACTLY $$[TOOL: name] {"argument": "value"}$$ (no code block), and stop.'
NUDGE_PT = 'Voce disse que ia agir, mas nenhuma ferramenta foi chamada e a tarefa NAO foi feita. Faca a chamada AGORA, escrevendo EXATAMENTE $$[TOOL: nome] {"argumento": "valor"}$$ (sem bloco de codigo) e pare. Se ja terminou, responda ao usuario sem prometer mais nada.'
NUDGE_EN = 'You said you were going to act, but no tool was called and the task was NOT done. Make the call NOW, writing EXACTLY $$[TOOL: name] {"argument": "value"}$$ (no code block) and stop. If you are already done, answer the user without promising anything else.'

def _schema(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": required}}}

def browser_chat_prompt(lang="pt"):
    """Aba Chat com a extensao do navegador conectada: as ferramentas mcp__browser__* (o texto vem de lumebrowser)."""
    if not (lumebrowser and lumemcp): return ""
    names = [d for d in lumebrowser.defs()]
    if not names: return ""
    head = ("\nVoce tambem controla o NAVEGADOR do dono (as abas dele, com os logins dele) por estas ferramentas. Chame UMA por vez no formato $$[TOOL: nome] {json}$$. Comece com read_page para ver a pagina; use o numero dos elementos em click e type; depois de cada acao leia a pagina de novo. Diga ao dono o nome REAL do navegador que o resultado informar. Nao clique em comprar/pagar/enviar sem o dono pedir.\n" if lang != "en" else
            "\nYou also control the owner's BROWSER (their tabs, with their logins) through these tools. Call ONE at a time as $$[TOOL: name] {json}$$. Start with read_page to see the page; use the element numbers in click and type; read the page again after each action. Tell the owner the REAL browser name the result gives. Do not click buy/pay/send unless the owner asked.\n")
    return head + "\n".join(f"- {x['full']} {lumemcp.signature(x['schema'])} : {x['description'][len(lumebrowser.DESC_PREFIX):][:200]}" for x in names) + "\n"

NATIVE_TOOLS_ALL = [
    _schema("list_files", "List the files in a folder", {"path": {"type": "string"}}, []),
    _schema("read_file", "Read a text file", {"path": {"type": "string"}}, ["path"]),
    _schema("write_file", "Create or overwrite a WHOLE file", {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _schema("edit_file", "Replace ONLY a snippet of an existing file: copy 'old' exactly as it is in the file (it must appear once; add surrounding lines if needed) and give the 'new' text. Prefer this to write_file for small changes", {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}, "replace_all": {"type": "boolean"}}, ["path", "old", "new"]),
    _schema("cmd", "Run a command in the Windows CMD", {"command": {"type": "string"}}, ["command"]),
    _schema("powershell", "Run a command in PowerShell", {"command": {"type": "string"}}, ["command"]),
    _schema("search_web", "Search the web. Choose how many results you need (fewer = cheaper and faster)", {"query": {"type": "string"}, "results": {"type": "integer", "description": "how many results (1-25); 3 to 5 is enough for simple questions"}}, ["query"]),
    _schema("read_url", "Read the text of a web page", {"url": {"type": "string"}}, ["url"]),
]
NATIVE_TOOLS_ALL += [
    _schema("take_screenshot", "Take ONE screenshot (image only) of a target: app name, part of a window title, .exe name, PID (a number) or 'desktop' (the whole screen), or a category: 'browser', 'terminal', 'editor', 'explorer', 'chat' (one screenshot per open window, up to 3). If the exact name does not exist Lume uses the closest match and tells the owner. Always name the app the result says (e.g. Comet), not the one requested", {"target": {"type": "string", "description": "app name, window title, .exe name, PID, or 'desktop'"}, "include_overlay": {"type": "boolean", "description": "include the Alt+Space box in a desktop screenshot (default false)"}}, ["target"]),
    _schema("list_windows", "List the open programs (window titles)", {}, []),
    _schema("launch_app", "OPEN a program (.exe/.bat) and wait for its window; it becomes one of the programs in use (up to 3). Use for games, DOSBox with a DOS program, VirtualBox, etc.", {"path": {"type": "string", "description": "full path to the .exe or a name on PATH"}, "args": {"type": "array", "items": {"type": "string"}}, "wait": {"type": "integer", "description": "seconds to wait for the window (default 15)"}}, ["path"]),
    _schema("close_app", "Close one of the programs in use (force=true kills the process if it will not close)", {"app": {"type": "string"}, "force": {"type": "boolean"}}, ["app"]),
    _schema("use_apps", "Choose up to 3 programs to use at the same time in the background (part of each window title)", {"apps": {"type": "array", "items": {"type": "string"}}}, ["apps"]),
    _schema("screenshot", "Take a picture of the chosen programs in the background: app 'all', a number (1-3) or a title; apps = a list of numbers. Without app it takes the whole screen", {"app": {"type": "string", "description": "'all', 1-3, or part of a window title (optional)"}, "apps": {"type": "array", "items": {"type": "string"}}}, []),
    _schema("mouse_click", "Click in ONE program at x,y measured on that program's last screenshot (virtual mouse; the user's mouse does not move)", {"app": {"type": "string", "description": "program number 1-3"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string"}, "double": {"type": "boolean"}}, ["app", "x", "y"]),
    _schema("mouse_move", "Move the virtual mouse in ONE program to x,y of its last screenshot", {"app": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}}, ["app", "x", "y"]),
    _schema("scroll", "Scroll in ONE program at x,y (negative = down)", {"app": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "amount": {"type": "integer"}}, ["app", "x", "y"]),
    _schema("type_text", "Type text into the focused field of ONE program", {"app": {"type": "string"}, "text": {"type": "string"}}, ["app", "text"]),
    _schema("press_key", "Press a key such as enter or tab in ONE program (Ctrl/Alt shortcuts may not work in the background)", {"app": {"type": "string"}, "key": {"type": "string"}}, ["app", "key"]),
]
NATIVE_TOOLS = NATIVE_TOOLS_ALL
NATIVE_TOOLS_WEB = [t for t in NATIVE_TOOLS_ALL if t["function"]["name"] in ("search_web", "read_url")]   # aba Chat: so a pesquisa
NATIVE_TOOLS_COMP = [t for t in NATIVE_TOOLS_ALL if t["function"]["name"] in ("search_web", "read_url") + COMPUTER_TOOLS]   # aba Chat com o controle do computador ligado

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
        if (name in TOOL_NAMES or str(name).startswith("mcp__")) and isinstance(args, dict):
            return name, {k: (_clean_arg(v) if k not in ("content", "old", "new") and not str(name).startswith("mcp__") else v) for k, v in args.items()}
    c = find_tool_call(msg.get("content") or "")   # alguns modelos respondem com o formato de texto mesmo assim
    return (c[0], c[1]) if c else None

def ask_permission(description, stop_check=None, call=None):
    """Bloqueia ate o usuario aprovar/negar no popup (ou parar a geracao)."""
    event = threading.Event()
    result = {"ok": False}
    def resolve(val): result["ok"] = bool(val); event.set()
    pending_command["cmd"] = description
    pending_command["rule"] = ""; pending_command["detail"] = ""
    if call:   # o que a bolinha analisa: a regra de comandos perigosos e o conteudo (do comando ou do arquivo a escrever)
        try: pending_command["rule"] = dangerous_reason(call[0], call[1]) or ""
        except Exception: pass
        pending_command["detail"] = str(call[1].get("content") if call[0] == "write_file" else call[1].get("new") if call[0] == "edit_file" else call[1].get("command", ""))[:6000]
    pending_command["resolve"] = resolve
    log("PERMISSAO", f"Aguardando o usuario: {description}", COLOR_YELLOW)
    while not event.wait(1):
        if stop_generation_flag.is_set() or (stop_check and stop_check()): resolve(False)
    pending_command["cmd"] = ""; pending_command["rule"] = ""; pending_command["detail"] = ""
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
    for ev in list(req_stops.values()): ev.set()
    try: lumemcp and lumemcp.stop_all()   # fecha os servidores MCP
    except Exception: pass
    tray_stop()
    stop_tunnel()
    try: set_terminal(False)   # fecha o terminal do log, se estiver aberto
    except Exception: pass
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
        if name in gens_active.values(): continue   # nao sugere desligar quem esta respondendo
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
        t_first = None
        with response:
            for raw in response:
                if not raw.strip(): continue
                data = json.loads(raw)
                if data.get("error"): raise Exception(data["error"])
                msg = data.get("message", {})
                if (msg.get("thinking") or msg.get("content")) and t_first is None: t_first = time.time()
                if msg.get("thinking"): yield "thinking", msg["thinking"]
                if msg.get("content"): yield "content", msg["content"]
                if data.get("done") and data.get("eval_count") and not data.get("eval_duration") and t_first:   # a nuvem do Ollama nao informa o tempo de geracao: mede pelo relogio
                    yield "stats", {"tokens": data["eval_count"], "seconds": max(0.001, time.time() - t_first), "prompt_tokens": data.get("prompt_eval_count", 0), "prompt_seconds": 0,
                                    "load_seconds": 0, "total_seconds": data.get("total_duration", 0) / 1e9}
                if data.get("done") and data.get("eval_count") and data.get("eval_duration"):
                    yield "stats", {"tokens": data["eval_count"], "seconds": data["eval_duration"] / 1e9,
                                    "prompt_tokens": data.get("prompt_eval_count", 0),
                                    "prompt_seconds": data.get("prompt_eval_duration", 0) / 1e9,
                                    "load_seconds": data.get("load_duration", 0) / 1e9,
                                    "total_seconds": data.get("total_duration", 0) / 1e9}
        return

GROQ_URL = "https://api.groq.com/openai/v1"
GROQ_EXCLUDE = re.compile(r"whisper|orpheus|guard|safeguard|allam|tts|embed", re.I)
_groq_cache = {"t": 0, "models": []}

def groq_models(cfg, force=False):
    """Modelos de conversa do Groq ([{id, ctx, max_out}]); em cache por 1 h."""
    key = (cfg.get("groq_api_key") or "").strip()
    if not key: return []
    if not force and _groq_cache["models"] and time.time() - _groq_cache["t"] < 3600: return _groq_cache["models"]
    req = urllib.request.Request(GROQ_URL + "/models", headers={"Authorization": "Bearer " + key, "User-Agent": "lume-app"})
    with urllib.request.urlopen(req, timeout=20) as r: data = json.load(r).get("data", [])
    out = [{"id": m["id"], "ctx": m.get("context_window") or 0, "max_out": m.get("max_completion_tokens") or 0} for m in data if m.get("id") and m.get("active", True) and not GROQ_EXCLUDE.search(m["id"])]
    out.sort(key=lambda m: m["id"]); _groq_cache.update(t=time.time(), models=out)
    return out

def stream_groq(model, messages, cfg, max_tokens=None):
    key = (cfg.get("groq_api_key") or "").strip()
    if not key: raise Exception("Chave do Groq nao configurada. Abra Configuracoes e cole sua chave.")
    msgs = [{"role": m["role"], "content": m["content"]} for m in messages]   # Groq nao aceita o campo "images"
    payload = {"model": model.replace("groq-", "", 1), "messages": msgs, "stream": True, "stream_options": {"include_usage": True}}
    if max_tokens: payload["max_tokens"] = int(max_tokens)
    req = urllib.request.Request(GROQ_URL + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"})
    t0 = time.time()
    try: response = _cloud_open(req, "O Groq")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace"); msg = body[:300]
        try: msg = str((json.loads(body).get("error") or {}).get("message") or msg)[:300]
        except (ValueError, AttributeError): pass
        wait = e.headers.get("retry-after")
        if e.code == 429: raise Exception(f"Limite do Groq atingido (tokens por minuto ou pedidos por dia){f'. Tente de novo em {wait} s' if wait else ''}. {msg}")
        if e.code in (401, 403): raise Exception("Chave do Groq invalida ou sem permissao. Confira em Configuracoes.")
        raise Exception(f"Groq respondeu {e.code}: {msg}")
    yield from _sse_chat(response, t0, {})

# ---------------------------------------------------------------- Vercel AI Gateway e LLM7 (interface compativel com a da OpenAI)
VERCEL_URL = "https://ai-gateway.vercel.sh/v1"
LLM7_URL = "https://api.llm7.io/v1"
AC_URL = "https://www.aichixia.xyz/api/v1"   # Aichixia: so os modelos do plano "free" (os premium nao funcionam)
AH_URL = "https://aihubmix.com/v1"           # AIHubMix: so os que terminam em "free"
LR_URL = "https://api.literouter.com/v1"     # LiteRouter: so os ":free" (1 pedido a cada 7 s no plano gratis)
LR_BLOCKED = {"kimi-k3-cheap:free", "muse-spark-1.2-contributor:free"}   # a API responde "model is not available" (o resto dos ":free" respondeu num teste com 1024 tokens; com 16 os modelos que pensam davam 502 por resposta vazia)
NX_BRANDS = re.compile(r"(gemma|gemini|claude|gpt|kimi|mistral|nemotron|qwen|deepseek|minimax|mimo|mercury)", re.I)   # Nexus: modelos de marcas que o Lume ja tem
X_NONCHAT = re.compile(r"safety|guard|embed|whisper|tts|image", re.I)   # VoidAI, Paxsenix e LiteRouter trazem TODOS os modelos de chat; so sai o que nao e conversa
X_SHOW_ALL = {p["id"] for p in PROVIDER_REGISTRY if p.get("showAll")}   # sem teste de saude e sem filtro de plano: aparecem todos (os que o plano nao cobrir respondem com erro na hora de usar)
AH_EXCLUDE = re.compile(r"phi-|north-|mythomax|intern-|dots-|lfm|xing|flint|agents-a|step-|command-|compound|sarvam|nova-|seed-|hy4|gpt-3\.5|grok|safety|guard|embed|whisper|tts|image", re.I)   # sem Llama nem Grok, e sem modelos "aleatorios" que ninguem pediu
_x_cache = {p: [0, []] for p in X_PROVIDERS}
USAGE_FILE = os.path.join(BASE_DIR, "provider_usage.json"); _usage_lock = threading.Lock()   # quantos pedidos o Lume mandou a cada provedor extra HOJE: {"ft": {"day": "2026-10-30", "n": 12}}
def quota_hit(prov):
    with _usage_lock:
        d = _read_json(USAGE_FILE, {}); d = d if isinstance(d, dict) else {}; today = time.strftime("%Y-%m-%d"); u = d.get(prov) or {}
        d[prov] = {"day": today, "n": (u.get("n", 0) if u.get("day") == today else 0) + 1}
        try: _write_json(USAGE_FILE, d)
        except OSError: pass
def quota_today(prov):
    u = (_read_json(USAGE_FILE, {}) or {}).get(prov) or {}; return u.get("n", 0) if u.get("day") == time.strftime("%Y-%m-%d") else 0
# Vercel: so os gratis que pediu. Eles so funcionam com um cartao cadastrado na conta Vercel (a Vercel exige, mesmo para os "-free").
VERCEL_MODELS = [("poolside/laguna-s-2.1-free", "Laguna S 2.1"), ("nvidia/nemotron-3.5-lightning-free", "Nemotron 3.5 Lightning"), ("reflection/beam-free", "Beam")]
_vc_cache = {"t": 0, "models": []}; _l7_cache = {"t": 0, "models": []}

def _openai_models(url, key):
    req = urllib.request.Request(url + "/models", headers={"Authorization": "Bearer " + key, "User-Agent": "lume-app"})
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r).get("data", [])

def vercel_models(cfg, force=False):
    key = (cfg.get("vercel_api_key") or "").strip()
    if not key: return []
    if not force and _vc_cache["models"] and time.time() - _vc_cache["t"] < 3600: return _vc_cache["models"]
    have = {m.get("id"): m for m in _openai_models(VERCEL_URL, key)}
    out = [{"id": mid, "name": name, "ctx": (have[mid].get("context_window") or 128000)} for mid, name in VERCEL_MODELS if mid in have]
    _vc_cache.update(t=time.time(), models=out); return out

LAST_FILE = os.path.join(BASE_DIR, "provider_models_last.json")   # ultima lista de modelos que cada provedor devolveu: {"ft": [...]}; vale quando o /models falha
HEALTH_FILE = os.path.join(BASE_DIR, "provider_health.json")   # resultado do ultimo teste de cada modelo: {"lr:id": {ok, ts, ms, err}}
HEALTH_EVERY = 600     # a cada 10 minutos
HEALTH_BATCH = 12      # alem dos que falharam, quantos modelos "bons" conferir por rodada (assim todos passam pelo teste de tempos em tempos sem encher o limite gratis)
HEALTH_SPACING = {p: v[3] for p, v in X_PROVIDERS.items()}   # segundos entre testes (o LiteRouter so aceita 1 pedido a cada 7 s)
_health = {}; _health_started = False

def _health_load():
    global _health
    d = _read_json(HEALTH_FILE, {}); _health = d if isinstance(d, dict) else {}

# FreeTheAI: cada modelo vem de um "provedor" que voce precisa SEGUIR no site deles (freetheai.org/providers/NOME) para usar; sem seguir, o pedido volta 403
# ("You don't follow X"). O Lume aprende com o erro (nao gasta pedidos testando): esconde os modelos desse provedor por 12 h e explica como seguir.
FOLLOW_FILE = os.path.join(BASE_DIR, "provider_follow.json"); FOLLOW_TTL = 12 * 3600
def _follow_state(): d = _read_json(FOLLOW_FILE, {}); return d if isinstance(d, dict) else {}
def follow_learn(kind, name):
    """kind: 'owner' (provedor que nao segue) ou 'model' (nenhum provedor seguido tem este modelo)."""
    try: d = _follow_state(); d.setdefault(kind, {})[str(name).lower()] = time.time(); _write_json(FOLLOW_FILE, d); _x_cache["ft"] = [0, []]   # a proxima lista ja vem sem eles
    except OSError: pass
def follow_hidden(mid):
    d = _follow_state(); now = time.time(); owner = mid.split("/")[0].lower() if "/" in mid else ""
    return now - (d.get("model") or {}).get(mid.lower(), 0) < FOLLOW_TTL or bool(owner and now - (d.get("owner") or {}).get(owner, 0) < FOLLOW_TTL)

def model_is_healthy(prov, mid):
    """Modelo que falhou no ultimo teste (duas tentativas seguidas) some da lista; sem teste ainda = aparece."""
    if prov == "ft" and follow_hidden(mid): return False
    if prov in X_SHOW_ALL: return True
    h = _health.get(prov + ":" + mid); return h is None or bool(h.get("ok", True))

def health_test(prov, mid, cfg):
    """1 pedido de verdade: responde se vier texto (modelos que pensam precisam de bastante espaco: 512 tokens). Devolve (ok, ms, erro)."""
    field, base = X_PROVIDERS[prov][:2]
    key = (cfg.get(field) or "").strip()
    body = json.dumps({"model": mid, "messages": [{"role": "user", "content": "Responda so a palavra: ok"}], "max_tokens": 512, "stream": False}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body, headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=90) as r: j = json.load(r)
        m = ((j.get("choices") or [{}])[0].get("message") or {})
        txt = (m.get("content") or m.get("reasoning_content") or m.get("reasoning") or "").strip()
        if re.match(r"\[Error", txt): return False, int((time.time() - t0) * 1000), txt[:100]   # gateway que devolve o erro do provedor como se fosse a resposta (ex.: Nexus/GLM: "[Error: Z.ai returned 403")
        if txt: return True, int((time.time() - t0) * 1000), ""
        return False, int((time.time() - t0) * 1000), "resposta vazia"
    except urllib.error.HTTPError as e:
        body = e.read()[:160].decode("utf-8", "replace")
        if e.code == 429 or (e.code == 403 and re.search(r"ate limit|oncurrent", body)): return None, 0, "limite de pedidos"   # limite do plano, nao defeito do modelo: nao conta
        return False, int((time.time() - t0) * 1000), f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, int((time.time() - t0) * 1000), str(e)[:100]

_health_state = {"on": False}   # True enquanto um teste esta rodando (a interface consulta a lista com mais frequencia nesse tempo)
_health_lock = threading.Lock()
HEALTH_WORKERS = 4     # modelos testados ao mesmo tempo (provedores com limite de 1 pedido a cada poucos segundos, como o LiteRouter, continuam um por vez)

def health_cycle():
    """Reconfere os modelos que falharam (para voltarem quando melhorarem) e um grupo dos outros, VARIOS AO MESMO TEMPO; cada resultado e gravado na hora (quem falha duas vezes seguidas some da lista)."""
    cfg = load_config(); changed = False; _health_state["on"] = True
    try:
        for prov in X_PROVIDERS:
            if not cfg.get(X_PROVIDERS[prov][0]) or prov in X_SHOW_ALL: continue   # os que mostram tudo nao gastam pedidos (nem creditos) em teste de saude
            try: ids = [m["id"] for m in extra_models(prov, cfg, force=True, raw=True)]
            except Exception: continue
            failed = [i for i in ids if not model_is_healthy(prov, i)]
            rest = sorted([i for i in ids if i not in failed], key=lambda i: (_health.get(prov + ":" + i) or {}).get("ts", 0))[:HEALTH_BATCH]
            def one(mid, prov=prov):
                if gens_active: return mid, "skip", 0, ""   # o dono esta conversando: nao disputa o limite de pedidos, tenta na proxima rodada
                ok, ms, err = health_test(prov, mid, cfg)
                if ok is False:
                    time.sleep(HEALTH_SPACING[prov]); ok, ms, err = health_test(prov, mid, cfg)   # confirma antes de esconder
                if ok is None: time.sleep(HEALTH_SPACING[prov] + 4)
                return mid, ok, ms, err
            workers = 1 if HEALTH_SPACING[prov] >= 5 else HEALTH_WORKERS
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                for fut in concurrent.futures.as_completed([ex.submit(one, m) for m in failed + rest]):
                    mid, ok, ms, err = fut.result()
                    if ok is None or ok == "skip": continue
                    with _health_lock:   # o resultado ja vale e e salvo na hora: o modelo aparece (ou some) sem esperar o fim da rodada
                        was = model_is_healthy(prov, mid); _health[prov + ":" + mid] = {"ok": bool(ok), "ts": time.time(), "ms": ms, "err": err}
                        if was != bool(ok): changed = True; log("SAUDE", f"{prov}:{mid} " + ("voltou a funcionar" if ok else f"saiu da lista ({err[:60]})"), COLOR_GREEN if ok else COLOR_YELLOW)
                        try: _write_json(HEALTH_FILE, _health)
                        except OSError: pass
            _x_cache[prov] = [0, []]
    finally: _health_state["on"] = False
    return changed

def health_loop():
    time.sleep(25)
    while True:
        try: health_cycle()
        except Exception as e: log("SAUDE", f"Erro no teste dos modelos: {e}", COLOR_RED)
        time.sleep(HEALTH_EVERY)

_vd_plan = {"t": 0, "plan": ""}
def voidai_plan(key):
    """Plano da conta VoidAI (GET /v1/credits -> plan); so entram os modelos que esse plano cobre."""
    if time.time() - _vd_plan["t"] < 3600 and _vd_plan["plan"]: return _vd_plan["plan"]
    try:
        with urllib.request.urlopen(urllib.request.Request(VD_URL + "/credits", headers={"Authorization": "Bearer " + key, "User-Agent": "lume-app"}), timeout=15) as r: p = str(json.load(r).get("plan") or "").strip().lower()
    except Exception: p = _vd_plan["plan"]
    _vd_plan.update(t=time.time(), plan=p); return p

_tk_cache = {"t": 0, "free": set(), "price": {}}
def tokenreply_free():
    """TokenReply: os do nivel gratis (model_ratio 0) e os "semanais em destaque" (gastam o credito gratis da conta); os "Plus" respondem 403 plus_required. A tabela de precos e publica (nao leva a chave)."""
    if time.time() - _tk_cache["t"] < 3600 and _tk_cache["free"]: return _tk_cache["free"]
    try:
        with urllib.request.urlopen(urllib.request.Request(TK_URL[:-3] + "/api/pricing", headers={"User-Agent": "lume-app"}), timeout=20) as r: d = json.load(r)
        ok = [x for x in d.get("data", []) if x.get("access_tier") in ("free", "weekly_featured")]
        # US$ por token: model_ratio x 0,002 / 1000 na entrada; x completion_ratio na saida (confere com o painel deles: 4111 + 11 tokens no sonnet-4-5 = US$ 0,0125)
        _tk_cache.update(t=time.time(), free={x["model_name"] for x in ok}, price={x["model_name"]: (float(x.get("model_ratio") or 0) * 2e-6, float(x.get("model_ratio") or 0) * float(x.get("completion_ratio") or 1) * 2e-6) for x in ok})   # free = ratio 0; weekly_featured gasta do credito gratis da conta (US$ 1)
    except Exception: pass
    return _tk_cache["free"]

def extra_models(prov, cfg, force=False, raw=False):
    """Modelos gratis de Aichixia (ac), AIHubMix (ah) e LiteRouter (lr): [{id, name, ctx, vision}]; em cache por 1 h. Os que falharam no teste de saude ficam de fora (raw=True traz todos)."""
    field, base = X_PROVIDERS[prov][:2]
    key = (cfg.get(field) or "").strip()
    if not key: return []
    t, cached = _x_cache[prov]
    if not force and cached and time.time() - t < 3600: return cached if raw else [m for m in cached if model_is_healthy(prov, m["id"])]
    data = _openai_models(base, key); out = []
    for m in data:
        mid = str(m.get("id") or "")
        if not mid or re.search(r"mythomax|celeris|isign|lfm", mid, re.I): continue
        kind = X_KIND.get(prov, "openai")
        if kind == "ac":
            caps = m.get("capabilities") or []
            if m.get("tier") != "free" or "chat" not in caps or AH_EXCLUDE.search(mid): continue
            out.append({"id": mid, "name": mid.split("/")[-1], "ctx": m.get("context_window") or 128000, "vision": "multimodal" in caps})
        elif kind == "ah":
            if not re.search(r"(^|[-:/])free$", mid) or AH_EXCLUDE.search(mid): continue
            out.append({"id": mid, "name": mid.split("/")[-1], "ctx": 128000, "vision": False})
        elif kind == "vd":   # VoidAI: todos os de chat (menos Gemma 4); os que o plano nao cobre caem no teste de saude e somem
            if "/v1/chat/completions" not in (m.get("endpoints") or []) or "free" not in (m.get("plan_requirements") or ["free"]) or re.search(r"gemma", mid, re.I) or X_NONCHAT.search(mid): continue
            if m.get("supports_streaming") is False: _NO_STREAM.add((base, mid))
            out.append({"id": mid, "name": mid, "ctx": m.get("max_context_tokens") or 128000, "vision": False, "cin": m.get("input_multiplier") or 0, "cout": m.get("output_multiplier") or 0, "cbase": m.get("base_cost") or 0})   # creditos = base + entrada x cin + saida x cout (docs.voidai.app/guides/credits)
        elif kind == "tk":   # TokenReply: so os gratis (ratio 0)
            if mid not in tokenreply_free() or X_NONCHAT.search(mid) or re.search(r"grok", mid, re.I): continue
            pin, pout = _tk_cache["price"].get(mid, (0, 0))
            out.append({"id": mid, "name": mid.split("/")[-1], "ctx": 128000, "vision": False, "cin": pin, "cout": pout})   # cin/cout em US$ por token
        elif kind == "px":   # Paxsenix: so o plano free (os "High Engine" nao entram) e sem os "(Provider N)" repetidos
            if m.get("type") != "chat.completions" or X_NONCHAT.search(mid): continue
            out.append({"id": mid, "name": m.get("name") or mid, "ctx": m.get("max_context_tokens") or 128000, "vision": bool(m.get("supports_vision"))})
        elif kind != "lr":   # provedor novo no formato da OpenAI: todos os modelos de chat que o /models lista
            if prov == "nx" and not NX_BRANDS.match(mid): continue   # Nexus: so marcas que o Lume ja tem (sem GLM: a conta do Z.ai deles esta bloqueada)
            if X_NONCHAT.search(mid) or m.get("type") not in (None, "chat", "chat.completions", "language"): continue
            out.append({"id": mid, "name": m.get("name") or m.get("display_name") or mid.split("/")[-1], "ctx": m.get("context_window") or m.get("max_context_tokens") or m.get("context_length") or 128000, "vision": False})
        else:   # lr: so os ":free"
            if not mid.endswith(":free") or m.get("type") != "chat" or X_NONCHAT.search(mid): continue
            caps = m.get("capabilities") or {}
            out.append({"id": mid, "name": m.get("display_name") or mid, "ctx": m.get("context_window") or 128000, "vision": bool(caps.get("vision"))})
    out.sort(key=lambda x: x["id"]); _x_cache[prov] = [time.time(), out]
    if out:
        try: last = _read_json(LAST_FILE, {}); last = last if isinstance(last, dict) else {}; last[prov] = out; _write_json(LAST_FILE, last)
        except OSError: pass
    return out if raw else [m for m in out if model_is_healthy(prov, m["id"])]

def llm7_models(cfg, force=False):
    """So os do plano "turbo" (usage_based_only falso): funcionam com saldo zero. Os outros cobram por uso."""
    key = (cfg.get("llm7_api_key") or "").strip()
    if not key: return []
    if not force and _l7_cache["models"] and time.time() - _l7_cache["t"] < 3600: return _l7_cache["models"]
    out = []
    for m in _openai_models(LLM7_URL, key):
        mo = m.get("modalities") or {}
        if m.get("usage_based_only") is not False or mo.get("output") != ["text"] or "whisper" in m.get("id", "") or "Voxtral" in m.get("id", ""): continue
        out.append({"id": m["id"], "ctx": m.get("context_window") or 32768, "tools": bool(m.get("tools_calling")), "vision": "image" in (mo.get("input") or [])})
    out.sort(key=lambda m: m["id"]); _l7_cache.update(t=time.time(), models=out); return out

_NO_STREAM = set()   # (endereco, modelo) que respondeu "streaming nao suportado": dai em diante a resposta vem inteira de uma vez

def _oai_nonstream(model, msgs, base, key, label, max_tokens, t0):
    """Pedido sem streaming (alguns modelos, como o Claude Haiku da Aichixia, nao aceitam): a resposta chega inteira e sai como um pedaco so."""
    payload = {"model": model, "messages": msgs, "stream": False}
    if max_tokens: payload["max_tokens"] = int(max_tokens)
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"})
    try:
        with _cloud_open(req, label, timeout=CLOUD_FIRST_TIMEOUT * 2) as r: j = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace"); msg = body[:250]
        try: msg = str((json.loads(body).get("error") or {}).get("message") or msg)[:250]
        except (ValueError, AttributeError): pass
        _oai_fail(label, e.code, body, msg, model)
    m = ((j.get("choices") or [{}])[0].get("message") or {}); think = m.get("reasoning_content") or m.get("reasoning"); text = m.get("content") or ""
    if think: yield "thinking", str(think)
    if text: yield "content", str(text)
    u = j.get("usage") or {}; total = max(0.001, time.time() - t0)
    if u.get("completion_tokens"): yield "stats", {"tokens": u["completion_tokens"], "seconds": total, "buffered": True, "limits": None, "prompt_tokens": u.get("prompt_tokens", 0), "prompt_seconds": 0, "load_seconds": 0, "total_seconds": total}

def stream_openai_compat(model, messages, base, key, label, max_tokens=None):
    key = (key or "").strip()
    if not key: raise Exception(f"{label} sem chave. Abra Configuracoes e cole a chave.")
    msgs = []
    for m in messages:
        imgs = m.get("images") or []
        if imgs and m["role"] == "user": msgs.append({"role": "user", "content": [{"type": "text", "text": m["content"]}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in imgs]})
        else: msgs.append({"role": m["role"], "content": m["content"]})
    payload = {"model": model, "messages": msgs, "stream": True, "stream_options": {"include_usage": True}}
    if max_tokens: payload["max_tokens"] = int(max_tokens)
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"})
    t0 = time.time()
    if (base, model) in _NO_STREAM: yield from _oai_nonstream(model, msgs, base, key, label, max_tokens, t0); return
    for attempt in range(3):
        try: response = _cloud_open(req, label); break
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace"); msg = body[:250]
            try: msg = str((json.loads(body).get("error") or {}).get("message") or msg)[:250]
            except (ValueError, AttributeError): pass
            if e.code == 400 and re.search(r"treaming is not supported", body):   # o provedor so entrega o texto inteiro: pede sem streaming
                _NO_STREAM.add((base, model)); yield "status", "Este modelo nao aceita streaming: a resposta chega inteira"; yield from _oai_nonstream(model, msgs, base, key, label, max_tokens, t0); return
            if (e.code == 429 or (e.code == 403 and re.search(r"ate limit|oncurrent", body))) and attempt < 2:   # limite de pedidos por segundo (LLM7 pede 1 s; o LiteRouter responde 403 e pede 7 s): espera o que o provedor pede e tenta de novo
                try: wait = float(e.headers.get("Retry-After") or (re.search(r"[Rr]etry after (\d+(?:\.\d+)?)", msg) or re.search(r"\((\d+(?:\.\d+)?) seconds", msg) or [0, 1])[1])
                except (TypeError, ValueError): wait = 1.0
                yield "status", f"Limite de pedidos; esperando {min(wait, 8):.0f} s"; time.sleep(min(wait, 8) + 0.3); continue
            _oai_fail(label, e.code, body, msg, model)
    else: raise Exception(f"{label}: nao respondeu")
    yield from _sse_chat(response, t0, {})

def _oai_fail(label, code, body, msg, model=""):
    if True:
        mf = re.search(r"You don't follow (\w+)\. Follow it at (\S+) to use", msg)
        if code == 403 and mf:   # FreeTheAI: precisa seguir o provedor no site
            follow_learn("owner", mf.group(1)); raise Exception(f"{label}: voce nao segue o provedor {mf.group(1)} no FreeTheAI, entao nao pode usar este modelo. Siga (e de graca) em {mf.group(2)} e tente de novo. Escondi os modelos desse provedor da lista por 12 h; os outros continuam.")
        if code == 403 and re.search(r"No provider you follow serves", msg):
            if model: follow_learn("model", model)
            raise Exception(f"{label}: nenhum provedor que voce segue tem este modelo. Siga um em https://freetheai.org/providers (ou adicione o modelo a sua chave em https://freetheai.org/dashboard/api-keys). Escondi este modelo da lista por 12 h.")
        if code == 404 and model and "freetheai" in label.lower() and re.search(r"was not found|not found", msg):   # a lista do FreeTheAI traz modelos que o pedido nao acha: esconde por 12 h
            follow_learn("model", model); raise Exception(f"{label}: o FreeTheAI listou o modelo {model}, mas na hora de usar respondeu que ele nao existe (404). Escondi este modelo da lista por 12 h.")
        if "credit card" in body or "customer_verification_required" in body: raise Exception("A Vercel exige um cartao cadastrado na conta para usar o AI Gateway (mesmo nos modelos gratis). Adicione em vercel.com > AI Gateway.")
        if code == 403 and re.search(r"ate limit|oncurrent", body): raise Exception(f"{label}: limite de pedidos. {msg}")
        if code in (401, 403): raise Exception(f"{label}: chave invalida ou sem permissao ({code}). {msg}")
        if code == 402: raise Exception(f"{label}: sem saldo (402).")
        if code == 429: raise Exception(f"{label}: limite de pedidos (429). {msg}")
        raise Exception(f"{label} respondeu {code}: {msg}")

# ---------------------------------------------------------------- tomdacat (gateway com creditos; a interface e compativel com a da OpenAI)
TDC_URL = "https://ai.tomdacat.com"
TDC_MAX_CR = 100   # so entram modelos de ate 100 creditos por milhao de tokens (entrada e saida)
# so os que testei e funcionam, e que o Lume ainda nao tinha por outro provedor; (id, nome, ferramentas, aviso). Para colocar outro, e so juntar aqui.
TDC_MODELS = [
    ("gpt-5-mini", "GPT-5 Mini", True, ""), ("mimo-v2.5", "MiMo V2.5", True, ""), ("mercury-2", "Mercury 2", True, ""), ("celeris-1", "Celeris 1", True, ""),
    ("diffusiongemma-4-26b", "DiffusionGemma 4 26B", True, "Este modelo e lento (uns 50 s para a primeira palavra)."),
    ("nemotron-3-nano-omni-reasoning", "Nemotron 3 Nano Omni", False, "Este modelo e lento (uns 40 s para a primeira palavra) e nao usa ferramentas."),
]
_tdc_cache = {"t": 0, "models": []}

def tomdacat_models(cfg, force=False):
    """[{id, name, tools, warn, cr_in, cr_out}] dos modelos da lista acima que o tomdacat oferece agora e custam ate 100 creditos/M; em cache por 30 min."""
    key = (cfg.get("tomdacat_api_key") or "").strip()
    if not key: return []
    if not force and _tdc_cache["models"] and time.time() - _tdc_cache["t"] < 1800: return _tdc_cache["models"]
    req = urllib.request.Request(TDC_URL + "/api/models", headers={"Authorization": "Bearer " + key, "User-Agent": "lume-app"})
    with urllib.request.urlopen(req, timeout=20) as r: data = {m["id"]: m for m in json.load(r).get("data", []) if m.get("id")}
    out = []
    for mid, name, tools, warn in TDC_MODELS:
        m = data.get(mid)
        if not m: continue
        pr = m.get("pricing") or {}; cin, cout = pr.get("credits_per_million_input") or 0, pr.get("credits_per_million_output") or 0
        if pr.get("paid_only") or max(cin, cout) > TDC_MAX_CR: continue
        out.append({"id": mid, "name": name, "tools": tools, "warn": warn, "cr_in": cin, "cr_out": cout})
    _tdc_cache.update(t=time.time(), models=out)
    return out

def stream_tomdacat(model, messages, cfg, max_tokens=None):
    key = (cfg.get("tomdacat_api_key") or "").strip()
    if not key: raise Exception("Chave do tomdacat nao configurada. Abra Configuracoes e cole sua chave.")
    msgs = []
    for m in messages:
        imgs = m.get("images") or []
        if imgs and m["role"] == "user": msgs.append({"role": "user", "content": [{"type": "text", "text": m["content"]}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in imgs]})
        else: msgs.append({"role": m["role"], "content": m["content"]})
    payload = {"model": model[4:], "messages": msgs, "stream": True, "stream_options": {"include_usage": True}}
    if max_tokens: payload["max_tokens"] = int(max_tokens)
    req = urllib.request.Request(TDC_URL + "/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"})
    t0 = time.time()
    try: response = _cloud_open(req, "O tomdacat")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace"); msg = body[:200]
        try: msg = str((json.loads(body).get("error") or {}).get("message") or msg)[:200]
        except (ValueError, AttributeError): pass
        if e.code in (401, 403): raise Exception("Chave do tomdacat invalida ou sem permissao. Confira em Configuracoes.")
        if e.code == 402: raise Exception("Os creditos do tomdacat acabaram (402).")
        if e.code == 429: raise Exception(f"Limite de pedidos do tomdacat (429){': ' + msg if msg else ''}")
        raise Exception(f"O tomdacat respondeu {e.code}: {msg}")
    yield from _sse_chat(response, t0, {})

# ---------------------------------------------------------------- OpenRouter (so modelos GRATIS)
OR_URL = "https://openrouter.ai/api/v1"
# Tempos maximos das APIs na nuvem (OpenRouter, Cloudflare, Pollinations): sem isso um provedor travado deixava o "Conectando..." para sempre.
CLOUD_CONNECT_TIMEOUT = 45   # segundos para conectar e o provedor comecar a responder
CLOUD_FIRST_TIMEOUT = 60     # segundos ate chegar o primeiro dado da resposta (modelos que pensam demoram)
CLOUD_IDLE_TIMEOUT = 60      # segundos sem nenhum dado no meio da resposta

def _cloud_open(req, label, timeout=None):
    """urlopen com tempo maximo e erros em portugues (o erro de rede cru era "timed out")."""
    try: return urllib.request.urlopen(req, timeout=timeout or CLOUD_CONNECT_TIMEOUT)
    except urllib.error.HTTPError: raise
    except Exception as e:
        if "timed out" in str(e).lower(): raise Exception(f"{label} nao respondeu em {timeout or CLOUD_CONNECT_TIMEOUT} s (sem conexao ou fora do ar).") from None
        raise Exception(f"Sem conexao com {label}: {str(e)[:100]}") from None
# Fora das listas (OpenRouter e Cloudflare): Llama, MiniMax, Krea, Z.ai/GLM e a Cloudflare em si; modelos de moderacao (nao conversam); LoRA (precisam de adaptador); e os pouco conhecidos / fracos.
MODEL_EXCLUDE = re.compile(r"^openrouter/|llama|minimax|krea|zai|glm|cloudflare/|safety|guard|lora|phonellm|sea-lion|granite|apertus|eurollm|dots-studio|recursive/|xingchen|liquid/|lfm|mistral|cohere|north-mini|poolside|laguna|thinkingmachines|inkling", re.I)
_or_cache = {"t": 0, "models": []}

def openrouter_free_models(force=False):
    """Modelos de texto 100% gratis (preco 0 na entrada e na saida) do catalogo do OpenRouter; em cache por 1 h."""
    if not force and _or_cache["models"] and time.time() - _or_cache["t"] < 3600: return _or_cache["models"]
    with urllib.request.urlopen(urllib.request.Request(OR_URL + "/models", headers={"User-Agent": "lume-app"}), timeout=15) as r: data = json.load(r).get("data", [])
    out = []
    for m in data:
        pr = m.get("pricing") or {}
        try: free = all(float(pr.get(k) or 0) == 0 for k in ("prompt", "completion", "request", "image")) and pr.get("prompt") is not None
        except (TypeError, ValueError): free = False
        arch = m.get("architecture") or {}; outm, inm = arch.get("output_modalities") or ["text"], arch.get("input_modalities") or ["text"]
        if not free or list(outm) != ["text"] or not m.get("id") or MODEL_EXCLUDE.search(m["id"]): continue   # so os que respondem apenas texto (sai musica, imagem, audio)
        out.append({"id": m["id"], "name": m.get("name") or m["id"], "ctx": m.get("context_length") or 0, "vision": "image" in inm,
                    "think": "reasoning" in (m.get("supported_parameters") or [])})
    out.sort(key=lambda x: x["name"].lower()); _or_cache.update(t=time.time(), models=out)
    return out

OR_HTTP_ERRORS = {401: "Chave do OpenRouter invalida (401). Confira a chave em Configuracoes.", 402: "O OpenRouter pediu credito (402): este modelo nao e gratis para a sua conta.",
                  429: "Limite do plano gratis do OpenRouter atingido (429). Espere um pouco ou tente amanha.", 404: "O OpenRouter nao achou esse modelo (404): talvez ele saiu da lista gratis."}

def stream_openrouter(model, messages, think, cfg, max_tokens=None):
    """Gera ('content'|'thinking'|'stats', valor) pela API compativel com OpenAI do OpenRouter. Recusa qualquer modelo que nao seja gratis."""
    key = cfg.get("openrouter_api_key") or ""
    if not key: raise Exception("Chave do OpenRouter nao configurada. Abra Configuracoes e cole sua chave.")
    slug = model[3:]
    if not slug.endswith(":free"):
        try: ok = any(m["id"] == slug for m in openrouter_free_models())
        except Exception: ok = False
        if not ok: raise Exception("Este modelo do OpenRouter nao e gratis: o Lume so usa modelos gratis.")
    msgs = []
    for m in messages:
        imgs = m.get("images") or []
        if imgs and m["role"] == "user": msgs.append({"role": "user", "content": [{"type": "text", "text": m["content"]}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in imgs]})
        else: msgs.append({"role": m["role"], "content": m["content"]})
    payload = {"model": slug, "messages": msgs, "stream": True, "stream_options": {"include_usage": True}}
    if max_tokens: payload["max_tokens"] = int(max_tokens)
    if think: payload["reasoning"] = {"enabled": True}
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "HTTP-Referer": "https://github.com/marioondc9426/Lume", "X-Title": "Lume"}
    t0 = time.time()
    for attempt in range(2):
        req = urllib.request.Request(OR_URL + "/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers)
        try: response = _cloud_open(req, "O OpenRouter")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if attempt == 0 and payload.get("reasoning") and e.code == 400: payload.pop("reasoning"); continue   # o modelo nao aceita "pensar": tenta sem
            raise Exception(OR_HTTP_ERRORS.get(e.code) or f"OpenRouter respondeu {e.code}: {body[:200]}")
        break
    yield from _sse_chat(response, t0, OR_HTTP_ERRORS)

# ---------------------------------------------------------------- Cloudflare Workers AI (plano gratis: 10.000 "neuronios" por dia)
CF_API = "https://api.cloudflare.com/client/v4"
_cf_cache = {"t": 0, "acc": "", "models": []}

def _kill_response(response):
    """Corta a conexao de outra thread (fechar o arquivo travaria junto com a leitura; o shutdown do socket destrava)."""
    try: response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        try: response.close()
        except Exception: pass

def parse_ratelimit(h):
    """Limites que o provedor informa nos cabecalhos (Groq: pedidos por dia e tokens por minuto). None se nao informar."""
    if not h: return None
    def num(k):
        try: return int(float(h.get(k)))
        except (TypeError, ValueError): return None
    out = {"req_limit": num("x-ratelimit-limit-requests"), "req_left": num("x-ratelimit-remaining-requests"), "tok_limit": num("x-ratelimit-limit-tokens"), "tok_left": num("x-ratelimit-remaining-tokens"),
           "req_reset": h.get("x-ratelimit-reset-requests"), "tok_reset": h.get("x-ratelimit-reset-tokens")}
    return out if (out["req_left"] is not None or out["tok_left"] is not None) else None

def _sse_chat(response, t0, err_map, first_timeout=None, idle_timeout=None):
    """Le a resposta em stream (SSE) de uma API compativel com OpenAI e gera ('content'|'thinking'|'stats', valor).
    Se nao chegar nenhum dado dentro do tempo (first_timeout no comeco, idle_timeout depois), a conexao e cortada e vira um erro."""
    first = None; usage = None; cut = False; tcalls = {}; _tc_status = 0.0; limits = parse_ratelimit(getattr(response, "headers", None)); extra = []   # extra: linhas que nao sao SSE (alguns provedores respondem 200 com um JSON de erro ou a resposta inteira)
    first_timeout = first_timeout or CLOUD_FIRST_TIMEOUT; idle_timeout = idle_timeout or CLOUD_IDLE_TIMEOUT
    state = {"timed": False, "limit": first_timeout}
    def arm(secs):
        tm = threading.Timer(secs, lambda: (state.update(timed=True), _kill_response(response))); tm.daemon = True; tm.start(); state["limit"] = secs; return tm
    timer = arm(first_timeout)
    try:
      with response:
        for raw in response:
            timer.cancel(); timer = arm(idle_timeout)
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):   # linhas ": OPENROUTER PROCESSING" sao so para manter a conexao
                if line and not line.startswith(":") and sum(len(x) for x in extra) < 20000: extra.append(line)
                continue
            d = line[5:].strip()
            if d == "[DONE]": break
            try: j = json.loads(d)
            except ValueError: continue
            if j.get("error"):
                e = j["error"] if isinstance(j["error"], dict) else {"message": j["error"]}
                raise Exception(err_map.get(e.get("code")) or str(e.get("message") or e)[:200])
            if j.get("usage"): usage = j["usage"]
            for ch in j.get("choices") or []:
                delta = ch.get("delta") or {}
                # a Cloudflare as vezes manda um trecho que e so numero ("10") ja convertido em int pelo JSON: sempre vira texto
                rs = delta.get("reasoning") or delta.get("reasoning_content")
                if rs not in (None, ""): first = first or time.time(); yield "thinking", str(rs)
                ct = delta.get("content")
                if ct not in (None, ""): first = first or time.time(); yield "content", str(ct)
                for tc in delta.get("tool_calls") or []:   # chamada de ferramenta nativa: o nome e os argumentos chegam em pedacos
                    first = first or time.time(); fn = tc.get("function") or {}; c = tcalls.setdefault(tc.get("index", 0), {"name": "", "args": ""})
                    c["name"] += str(fn.get("name") or ""); c["args"] += str(fn.get("arguments") or "")
                    if time.time() - _tc_status > 0.7 and c["name"]:   # a chamada chega em pedacos e nada aparece no chat ate o fim: mostra o andamento
                        _tc_status = time.time(); yield "status", f"Escrevendo a chamada de {c['name']} ({len(c['args'])} caracteres)"
                if ch.get("finish_reason") == "length": cut = True
    except Exception:
        if state["timed"]: raise Exception(f"O provedor parou de responder (sem dados por {state['limit']} s).") from None
        raise
    finally:
        timer.cancel()
    if state["timed"]: raise Exception(f"O provedor parou de responder (sem dados por {state['limit']} s).")
    if first is None and not usage and not tcalls:   # nada chegou como stream: o corpo e um JSON de erro, a resposta inteira ou vazio
        body = "".join(extra)
        try: j = json.loads(body)
        except ValueError: j = None
        if isinstance(j, dict) and j.get("error"):
            e = j["error"] if isinstance(j["error"], dict) else {"message": j["error"]}
            raise Exception(err_map.get(e.get("code")) or str(e.get("message") or e)[:200])
        m = ((((j or {}).get("choices") or [{}])[0] or {}).get("message") or {}) if isinstance(j, dict) else {}
        if m.get("reasoning_content") or m.get("reasoning"): yield "thinking", str(m.get("reasoning_content") or m.get("reasoning"))
        if m.get("content"): yield "content", str(m["content"]); return
        raise Exception("O provedor respondeu vazio" + (": " + body[:150] if body else " (sem texto)") + ". Tente de novo ou escolha outro modelo.")
    if cut: yield "content", "\n\n[Cortado: o modelo atingiu o limite de tokens da resposta]"
    calls_txt = ["$$[TOOL: %s] %s$$" % (lumemcp.resolve(c["name"]) if (lumemcp and c["name"] not in TOOL_NAMES) else c["name"], c["args"] or "{}") for _, c in sorted(tcalls.items())[:5] if c["name"]]   # nome desconhecido tambem passa: o laco responde "essa ferramenta nao existe" em vez de engolir a chamada
    if calls_txt: yield "content", chr(10).join(calls_txt)   # tudo num pedaco so: o laco do agente le a primeira e depois as outras
    if usage and usage.get("completion_tokens"):
        now = time.time(); win = max(0.001, now - (first or t0)); total = max(0.001, now - t0)
        # alguns provedores (Pollinations) seguram a resposta e soltam tudo de uma vez no fim: o tempo entre o 1o e o ultimo pedaco nao e o de geracao (dava 7.000 t/s).
        # Se quase todo o tempo foi espera antes do 1o dado, ou o resultado e impossivel, vale o tempo total do pedido.
        burst = bool(first) and win < 0.25   # a resposta toda chegou junta: nao da para medir o ritmo; se chegou espalhada (mesmo curta), a janela vale
        gen = total if (burst or usage["completion_tokens"] / win > 2500) else win
        yield "stats", {"tokens": usage["completion_tokens"], "seconds": gen, "buffered": gen == total, "limits": limits, "prompt_tokens": usage.get("prompt_tokens", 0), "prompt_seconds": (first - t0) if first else 0, "load_seconds": 0, "total_seconds": now - t0}

def cf_creds(cfg): return (cfg.get("cloudflare_api_token") or "").strip(), (cfg.get("cloudflare_account_id") or "").strip()

def _cf_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": "lume-app"})
    with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)

def cf_probe_key(cfg):
    token, acc = cf_creds(cfg); return f"{acc}:{hashlib.sha1(token.encode()).hexdigest()[:8]}"

def cloudflare_models(cfg, force=False, raw=False):
    """Modelos de texto do Workers AI disponiveis para a conta ([{id, name, vendor, ctx, vision}]); em cache por 1 h.
    Sem raw, tira os que o plano da conta nao aceita (descobertos por cloudflare_probe ou por um erro ao usar)."""
    token, acc = cf_creds(cfg)
    if not token or not acc: return []
    if not raw and not force and _cf_cache["models"] and _cf_cache["acc"] == acc and time.time() - _cf_cache["t"] < 3600:
        return [m for m in _cf_cache["models"] if m["id"] not in set(cfg.get("cloudflare_blocked") or [])]
    out, page = [], 1
    while page <= 4:
        d = _cf_get(f"{CF_API}/accounts/{urllib.parse.quote(acc)}/ai/models/search?task=Text%20Generation&per_page=100&page={page}", token)
        items = d.get("result") or []
        for m in items:
            name = m.get("name") or ""
            if not name.startswith(("@cf/", "@hf/")) or MODEL_EXCLUDE.search(name): continue
            props = {p.get("property_id"): p.get("value") for p in (m.get("properties") or []) if isinstance(p, dict)}
            try: ctx = int(props.get("context_window") or 0)
            except (TypeError, ValueError): ctx = 0
            parts = name.split("/"); pin = pout = None
            for pr in (props.get("price") or []) if isinstance(props.get("price"), list) else []:
                u = str(pr.get("unit", "")).lower()
                if "cached" in u: continue
                if "input" in u: pin = pr.get("price")
                elif "output" in u: pout = pr.get("price")
            out.append({"id": name, "pin": pin, "pout": pout, "name": parts[-1], "vendor": parts[1] if len(parts) > 2 else "cloudflare", "ctx": ctx,
                        "vision": bool(props.get("vision")) or "vision" in name.lower() or "-vl" in name.lower()})
        if len(items) < 100: break
        page += 1
    out.sort(key=lambda x: (x["vendor"], x["name"])); _cf_cache.update(t=time.time(), acc=acc, models=out)
    return out if raw else [m for m in out if m["id"] not in set(cfg.get("cloudflare_blocked") or [])]

_cf_probe = {"running": False}

def cf_block(model_id):
    cfg = load_config(); bl = set(cfg.get("cloudflare_blocked") or []); bl.add(model_id); cfg["cloudflare_blocked"] = sorted(bl); save_config(cfg)

def cloudflare_probe():
    """Manda um pedido minusculo (6 tokens) a cada modelo para descobrir quais o plano da conta aceita; os que recusam saem da lista. Uma vez por token."""
    if _cf_probe["running"]: return
    _cf_probe["running"] = True
    try:
        cfg = load_config(); token, acc = cf_creds(cfg); blocked = set()
        for m in cloudflare_models(cfg, True, raw=True):
            body = json.dumps({"model": m["id"], "messages": [{"role": "user", "content": "oi"}], "max_tokens": 6}).encode()
            req = urllib.request.Request(f"{CF_API}/accounts/{urllib.parse.quote(acc)}/ai/v1/chat/completions", data=body, headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": "lume-app"})
            try: urllib.request.urlopen(req, timeout=60).read()
            except urllib.error.HTTPError as e:
                if e.code in (401, 429): log("CLOUDFLARE", f"Conferencia dos modelos interrompida ({e.code}).", COLOR_YELLOW); return   # token ruim ou limite do dia: tenta de novo outra hora
                blocked.add(m["id"])
            except Exception: pass
        cfg = load_config(); cfg["cloudflare_blocked"] = sorted(blocked); cfg["cloudflare_probe_acc"] = cf_probe_key(cfg); save_config(cfg)
        log("CLOUDFLARE", f"Conferencia pronta: {len(blocked)} modelo(s) fora do seu plano.", COLOR_GREEN)
    except Exception as e:
        log("CLOUDFLARE", f"Conferencia dos modelos falhou: {e}", COLOR_YELLOW)
    finally:
        _cf_probe["running"] = False

# ---- monitor de neuronios (o plano gratis do Workers AI da 10.000 por dia; zera as 00:00 UTC)
CF_NEURON_LIMIT = 10000
_cf_gql = {"t": 0, "val": None, "fail_until": 0}

def _utc_day(): return time.strftime("%Y-%m-%d", time.gmtime())

def cf_neurons_for(model_id, tin, tout):
    """Estimativa: 1.000 neuronios = US$ 0,011; usa o preco por milhao de tokens do catalogo (se nao souber, supoe 0,5)."""
    pin = pout = 0.5
    for m in _cf_cache["models"]:
        if m["id"] == model_id: pin = m.get("pin") if m.get("pin") is not None else 0.5; pout = m.get("pout") if m.get("pout") is not None else 0.5; break
    return (tin * pin + tout * pout) / 1e6 / 0.000011

def cf_add_neurons(model_id, tin, tout):
    cfg = load_config(); d = cfg.get("cloudflare_neurons") or {}
    if d.get("day") != _utc_day(): d = {"day": _utc_day(), "n": 0.0, "offset": 0.0}
    d["n"] = round(d.get("n", 0.0) + cf_neurons_for(model_id, tin, tout), 3); cfg["cloudflare_neurons"] = d; save_config(cfg)

def cf_gql_neurons(token, acc):
    """Neuronios usados hoje (UTC) segundo a propria Cloudflare. Precisa de um token com a permissao "Account Analytics: Read"."""
    now = time.time()
    if _cf_gql["val"] is not None and now - _cf_gql["t"] < 60: return _cf_gql["val"]
    if now < _cf_gql["fail_until"]: return None
    q = ('query { viewer { accounts(filter:{accountTag:"%s"}) { aiInferenceAdaptiveGroups(limit:100, filter:{datetime_geq:"%sT00:00:00Z", datetime_leq:"%s"}) { sum { totalNeurons } } } } }'
         % (acc, _utc_day(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
    try:
        req = urllib.request.Request(CF_API + "/graphql", data=json.dumps({"query": q}).encode(), headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": "lume-app"})
        with urllib.request.urlopen(req, timeout=15) as r: d = json.load(r)
        if d.get("errors"): raise Exception(d["errors"][0].get("message", "erro"))
        groups = d["data"]["viewer"]["accounts"][0]["aiInferenceAdaptiveGroups"]
        val = sum(float((g.get("sum") or {}).get("totalNeurons") or 0) for g in groups)
    except Exception:
        _cf_gql["fail_until"] = now + 600; return None   # sem permissao de analise: usa a estimativa e tenta de novo daqui a 10 min
    _cf_gql.update(t=now, val=val); return val

def cf_usage():
    cfg = load_config(); token, acc = cf_creds(cfg)
    d = cfg.get("cloudflare_neurons") or {}
    if d.get("day") != _utc_day(): d = {"day": _utc_day(), "n": 0.0, "offset": 0.0}
    real = cf_gql_neurons(token, acc) if token and acc else None
    est = max(0.0, d.get("n", 0.0) + d.get("offset", 0.0))
    return {"neurons": real if real is not None else est, "limit": CF_NEURON_LIMIT, "source": "api" if real is not None else "estimate", "day": d["day"]}

CF_HTTP_ERRORS = {5035: "Este modelo do Cloudflare nao esta disponivel no plano gratuito (so no Workers Paid): ele foi tirado da lista.", 5018: "Esta conta do Cloudflare nao tem acesso a este modelo: ele foi tirado da lista.",
                  5016: "Este modelo do Cloudflare exige aceitar um acordo de licenca no painel da Cloudflare: ele foi tirado da lista.", 401: "Token do Cloudflare invalido (401). Confira o token e o Account ID em Configuracoes.", 403: "O token do Cloudflare nao tem permissao para o Workers AI (403).",
                  429: "Limite diario gratis do Cloudflare atingido (10.000 neuronios). Volta amanha ou espere um pouco.", 4006: "Limite diario gratis do Cloudflare atingido (10.000 neuronios). Volta amanha."}

def stream_cloudflare(model, messages, think, cfg, max_tokens=None):
    """Gera ('content'|'thinking'|'stats', valor) pelo endpoint compativel com OpenAI do Workers AI."""
    token, acc = cf_creds(cfg)
    if not token or not acc: raise Exception("Token do Cloudflare nao configurado. Abra Configuracoes e cole o token e o Account ID.")
    slug = model[3:]
    if not slug.startswith(("@cf/", "@hf/")): raise Exception("Modelo do Cloudflare invalido: so os do Workers AI (@cf/...) sao usados.")
    msgs = []
    for m in messages:
        imgs = m.get("images") or []
        if imgs and m["role"] == "user": msgs.append({"role": "user", "content": [{"type": "text", "text": m["content"]}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in imgs]})
        else: msgs.append({"role": m["role"], "content": m["content"]})
    payload = {"model": slug, "messages": msgs, "stream": True, "stream_options": {"include_usage": True}, "max_tokens": int(max_tokens or 8192)}   # sem isso a Cloudflare corta em 256 tokens e os modelos que pensam (R1) acabavam sem resposta
    req = urllib.request.Request(f"{CF_API}/accounts/{urllib.parse.quote(acc)}/ai/v1/chat/completions", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": "lume-app"})
    t0 = time.time()
    try: response = _cloud_open(req, "A Cloudflare")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace"); code = None; msg = body[:200]
        try: err = (json.loads(body).get("errors") or [{}])[0]; code, msg = err.get("code"), str(err.get("message") or msg)[:200]
        except (ValueError, AttributeError, IndexError): pass
        if code in (5035, 5018, 5016): cf_block(model[3:])   # o plano nao aceita este modelo: some da lista
        raise Exception(CF_HTTP_ERRORS.get(code) or CF_HTTP_ERRORS.get(e.code) or f"Cloudflare respondeu {e.code}: {msg}")
    yield from _sse_chat(response, t0, CF_HTTP_ERRORS)

# ---------------------------------------------------------------- Pollinations (pollen: saldo gratis por missoes; os modelos gastam pollen)
POL_API = "https://gen.pollinations.ai"
# Modelos do Pollinations que o Lume mostra (id, ajustes). Os de "community/" sao feitos por usuarios: preco e saude vem do catalogo quando ele os lista;
# os que ele nao lista mas respondem nos testes entram com preco informado a mao. free = gratis; flaky = instavel (vai para o fim da fila de tentativas).
POL_MODELS = [
    ("openai/gpt-5.4-nano", {}), ("openai/gpt-5.6-luna", {}), ("openai/gpt-5-nano", {}), ("openai/gpt-6-luna", {}),
    ("openai/gpt-5.4", {}), ("openai/gpt-5.4-mini", {}), ("openai/gpt-5.5", {}), ("openai/gpt-5.6-sol", {"keep": True}), ("openai/gpt-5.6-terra", {}),
    ("openai/gpt-6-sol", {}), ("openai/gpt-6.1-sol", {"keep": True}), ("openai/gpt-6.1-terra", {}), ("openai/gpt-6-astra", {}), ("openai/gpt-oss-20b", {}),
    ("community/gggff123/gpt-5-nano", {}), ("community/chirag-gamer/gpt-oss-120b", {}),
    ("community/YoannDev90/qwen3.7-flash", {}), ("community/MarcosFRG/gemini-3.1-flash-lite", {"pin": 0.5, "pout": 1.5, "guess": True}),
    ("deepseek/deepseek-v4.1-flash", {}), ("community/MarcosFRG/deepseek-v4.1-flash", {}), ("community/scriptsnsenses-sys/deepseek-v4.1-flash", {}), ("community/vendouple/deepseek-v4.1-flash", {"pin": 0.06, "pout": 0.5}),
    ("deepseek/deepseek-v4-flash", {}), ("community/vendouple/deepseek-v4-flash", {"pin": 0.02, "pout": 0.10}), ("community/gggff123/deepseek-v4-flash:free", {"free": True, "flaky": True}),
    ("community/gggff123/qwen3.8-27b:free", {"free": True, "flaky": True}),
    ("community/CloudCompile/nvidia-nemotron-3-ultra-550b-a55b:free", {"free": True}), ("community/YoannDev90/vercel-nemotron-3.5-lightning:free", {"free": True}),
    ("community/CloudCompile/reflection-beam-free", {"free": True}), ("community/YoannDev90/vercel-beam:free", {"free": True}),
    # tabs: "code" = so na aba Code; "both" = nas duas. warn = aviso (triangulo) mostrado ao escolher o provedor
    ("community/morriszdweck/glm-5.3-flash-free", {"free": True, "tabs": "both"}), ("community/scriptsnsenses-sys/glm-5.3-flash-free", {"free": True, "tabs": "both"}),
    ("community/MarcosFRG/glm-5.3-flash", {"tabs": "both"}), ("community/Saauf/glm-5.3-flash", {"tabs": "both"}),   # pagos: a reserva dos gratis (o Lume tenta o proximo mais barato se um falhar)
    ("community/MarcosFRG/glm-4.6v-flash", {"free": True, "tabs": "both", "warn": "Limite de 3 pedidos por minuto: pode dar erro de limite se voce mandar varias mensagens seguidas."}),
    ("community/YoannDev90/muse-glimmer-30b:free", {"free": True, "tabs": "code"}),
    ("community/scriptsnsenses-sys/muse-spark-1.3-contributor", {"free": True, "flaky": True, "tabs": "code", "warn": "Este provedor registra (loga) as suas conversas. Nao envie nada privado ou secreto."}),
    ("community/CloudCompile/poolside-laguna-s-2.1:free", {"free": True, "tabs": "code"}),
    ("community/ZapGaming/llama3.1-8b-xturbo", {"free": True, "speed": 2, "tabs": "both"}),
    ("community/Saauf/mistral-large-4", {"tabs": "both"}), ("community/Saauf/laguna-xs-2.1", {"tabs": "code"}),
    ("community/Saauf/minimax-m3.1-flash", {"tabs": "both"}),("community/mikl-shortcuts/ministral-3", {"tabs": "both"}), ("minimax/minimax-m3", {"tabs": "both"}),
    # modelos que ja existiam oficiais: a versao da comunidade (mais barata) vira a padrao e a oficial fica de reserva (o Lume ordena pelo preco)
    ("moonshotai/kimi-k2.6", {"tabs": "both"}), ("moonshotai/kimi-k3", {"tabs": "both", "keep": True}), ("community/vendouple/kimi-k3", {"tabs": "both", "prio": True}),
    ("community/sonofstrange/gpt-6.1-sol-quest", {"tabs": "both", "keep": True}), ("community/JustScriptzz/gpt-5.6-sol", {"tabs": "both", "keep": True}),
    ("community/JustScriptzz/claude-opus-4.6", {"tabs": "both"}), ("community/JustScriptzz/gemini-4-argon", {"tabs": "both"}), ("community/JustScriptzz/mistral-large-4", {"tabs": "both"}), ("community/JustScriptzz/gpt-5.6-terra", {"tabs": "both"}),
    ("community/vendouple/qwen-3.8-max", {"tabs": "both"}), ("qwen/qwen3.8-2.4t-a95b", {"tabs": "both", "keep": True}),   # o oficial (mais caro) e o mesmo Qwen 3.8 Max: fica de reserva
    ("community/scriptsnsenses-sys/deepseek-v4-flash-0731", {"free": True, "tabs": "both"}),
    ("mistralai/mistral-large-3", {"tabs": "both"}),
    ("community/CloudCompile/poolside-laguna-s-2.1:free", {"free": True, "tabs": "code"}),   # o Laguna sem cartao (o da Vercel exige cartao)
    ("community/scriptsnsenses-sys/gemini-3.1-pro-free", {"free": True, "tabs": "both", "warn": "Provedor da comunidade, nao oficial: o Lume nao controla o que ele faz com as suas mensagens."}),
]
_pol_cache = {"t": 0, "key": "", "cat": {}}

def _pol_req(path, key, body=None, timeout=30):
    req = urllib.request.Request(POL_API + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"})
    return urllib.request.urlopen(req, timeout=timeout)

def pollinations_catalog(key, force=False):
    if not force and _pol_cache["cat"] and _pol_cache["key"] == key and time.time() - _pol_cache["t"] < 1800: return _pol_cache["cat"]
    try:
        with _pol_req("/v1/models?reliability=all&limit=500", key) as r: data = json.load(r).get("data", [])   # sem "reliability=all" a lista esconde os modelos instaveis (alguns dos novos nao apareciam)
    except Exception:
        with _pol_req("/v1/models", key) as r: data = json.load(r).get("data", [])
    _pol_cache.update(t=time.time(), key=key, cat={m["id"]: m for m in data if m.get("id")})
    return _pol_cache["cat"]

def pol_caps(slug, key):
    """O que o catalogo diz que o modelo faz: {effort, tools, reasoning, rpm}; None se ele nao esta no catalogo."""
    try: m = pollinations_catalog(key).get(slug)
    except Exception: return None
    if not m: return None
    caps = m.get("capabilities") or []
    return {"effort": "reasoning_effort" in (m.get("supported_parameters") or []), "tools": "tool_calling" in caps or bool(m.get("tools")),
            "reasoning": "reasoning" in caps or bool(m.get("reasoning")), "rpm": m.get("per_user_rpm")}

_pol_status = {"t": 0, "lat": {}}
def pol_latency(key):
    """Latencia tipica (p50, em segundos) de cada modelo de texto, do /models/status da Pollinations; em cache por 10 min."""
    if time.time() - _pol_status["t"] < 600: return _pol_status["lat"]
    lat = {}
    try:
        with _pol_req("/models/status", key, timeout=15) as r: rows = json.load(r).get("data") or []
        for row in rows:
            if str(row.get("event_type", "")).endswith("text") and row.get("model") and row.get("latency_p50_ms"): lat[row["model"]] = round(row["latency_p50_ms"] / 1000, 1)
    except Exception: pass
    _pol_status.update(t=time.time(), lat=lat)
    return lat

EFFORT_ORDER = ["none", "minimal", "low", "medium", "high", "xhigh", "max"]
_pol_effort_ok = {}   # modelo -> niveis de raciocinio que ele aceita (aprendido da mensagem de erro dele)
def _remember_efforts(model, levels):
    """Guarda no config os niveis que o modelo aceita (descobertos pelo erro dele): a lista de esforco mostra so esses."""
    try:
        c = load_config(); c.setdefault("pol_effort_ok", {})[model] = list(levels); save_config(c)
    except Exception: pass

def probe_pol_efforts(slug, cfg):
    """Descobre os niveis de raciocinio que o modelo aceita. 1 pedido de 1 token com um valor invalido: o erro do modelo lista os aceitos; se ele nao listar, testa um por um."""
    key = (cfg.get("pollinations_api_key") or "").strip()
    if not key: raise Exception("Chave do Pollinations nao configurada.")
    if not re.fullmatch(r"[\w.\-/:]+", slug): raise Exception("Modelo invalido.")
    def ask(level):
        body = {"model": slug, "messages": [{"role": "user", "content": "1"}], "max_tokens": 1, "reasoning_effort": level}
        try:
            with _pol_req("/v1/chat/completions", key, body, timeout=60) as r: r.read(); return 200, ""
        except urllib.error.HTTPError as e: return e.code, e.read().decode("utf-8", "replace")
    code, txt = ask("lume_probe")
    if code in (401, 402, 403, 429): raise Exception(POL_HTTP_ERRORS.get(code) or f"Pollinations respondeu {code}")
    mm = re.search(r"upported values are:?([^.\"]*)", txt)
    levels = [x for x in re.findall(r"'(\w+)'", mm.group(1)) if x in EFFORT_ORDER] if mm else []
    source = "lista do proprio modelo"
    if not levels:
        source = "teste um a um"
        for lv in EFFORT_ORDER:
            c, _ = ask(lv)
            if c in (401, 402, 403, 429): raise Exception(POL_HTTP_ERRORS.get(c) or f"Pollinations respondeu {c}")
            if c == 200: levels.append(lv)
    if levels: _pol_effort_ok[slug] = levels; _remember_efforts(slug, levels)
    return levels, source

def _near_effort(want, allowed):
    allowed = [a for a in EFFORT_ORDER if a in allowed]
    if not allowed: return None
    if want in allowed: return want
    wi = EFFORT_ORDER.index(want) if want in EFFORT_ORDER else 3
    return min(allowed, key=lambda a: (abs(EFFORT_ORDER.index(a) - wi), EFFORT_ORDER.index(a)))

class _PolHTTP(Exception):
    def __init__(self, code, body): super().__init__(body[:200]); self.code = code; self.body = body

def _pol_price(m):
    p = (m or {}).get("pricing") or {}
    try: return float(p.get("promptTextTokens") or 0) * 1e6, float(p.get("completionTextTokens") or 0) * 1e6
    except (TypeError, ValueError): return 0.0, 0.0

POL_MAX_PRICE = 4.5   # pollen por milhao de tokens (entrada, saida ou imagem de entrada): modelos pagos acima disso nao aparecem

def pollinations_menu(cfg, force=True):
    """Catalogo inteiro do Pollinations com a saude de agora, para o "menu do Pollinations" filtrar (o site nao tem esses filtros)."""
    key = cfg.get("pollinations_api_key") or ""
    cat = pollinations_catalog(key, force=force)
    if force: _pol_status["t"] = 0
    lat = pol_latency(key); out = []
    for mid, m in cat.items():
        pr = m.get("pricing") or {}; hl = m.get("health") or {}
        price = any(float(pr.get(k) or 0) > 0 for k in ("promptTextTokens", "completionTextTokens", "promptImageTokens", "completionImageTokens", "completionAudioTokens", "completionVideoTokens"))
        quest = bool(re.search(r"quest", mid + " " + str(m.get("title") or ""), re.I))
        out.append({"id": mid, "title": m.get("title") or mid.split("/")[-1], "category": m.get("category") or ",".join(m.get("output_modalities") or ["text"]), "owner": m.get("owned_by") or "",
                    "community": bool(m.get("community")), "success": hl.get("success_rate"), "status": hl.get("status") or "?", "requests": hl.get("requests"), "p50": lat.get(mid),
                    "free": not price and not m.get("paid_only"), "quest": quest, "paid": bool(price or m.get("paid_only")) and not quest,
                    "pin": _pol_price(m)[0], "pout": _pol_price(m)[1], "outputs": m.get("output_modalities") or ["text"]})
    out.sort(key=lambda x: (-(x["success"] or 0), x["title"].lower()))
    return out

def pollinations_models(cfg):
    """Cada provedor e um modelo a parte ([{id, name, provider, ctx, vision, pin, pout, free, health, success, speed}]); a interface junta os que sao o mesmo modelo."""
    key = cfg.get("pollinations_api_key") or ""
    cat = pollinations_catalog(key); out = []; lat = pol_latency(key)
    for mid, ex in POL_MODELS:
        m = cat.get(mid) or {}; pin, pout = _pol_price(m) if m else (ex.get("pin", 0.0), ex.get("pout", 0.0))
        if m and not m.get("pricing"): pin, pout = ex.get("pin", 0.0), ex.get("pout", 0.0)
        hl = m.get("health") or {}; inm = m.get("input_modalities") or ["text"]
        free = bool(ex.get("free")) or (bool(m) and pin == 0 and pout == 0)
        try: pimg = float(((m.get("pricing") or {}).get("promptImageTokens")) or 0) * 1e6 if m else 0.0
        except (TypeError, ValueError): pimg = 0.0
        if not free and not ex.get("keep") and max(pin, pout, pimg) > POL_MAX_PRICE: continue   # caro demais para o seu orcamento
        out.append({"id": mid, "name": m.get("title") or mid.split("/")[-1], "provider": mid.split("/")[1] if mid.startswith("community/") else "oficial",
                    "ctx": m.get("context_length") or 128000, "vision": "image" in inm, "pin": pin, "pout": pout, "free": free, "guess": bool(ex.get("guess")),
                    "health": hl.get("status") or ("degraded" if ex.get("flaky") else "?"), "success": hl.get("success_rate"), "created": m.get("created"), "official": not mid.startswith("community/"), "prio": bool(ex.get("prio")), "speed": ex.get("speed", 0), "tabs": ex.get("tabs", "chat"),
                    "warn": ex.get("warn") or (f"Limite de {m['per_user_rpm']} pedidos por minuto: se mandar varias mensagens seguidas pode dar erro de limite." if m.get("per_user_rpm") and m["per_user_rpm"] <= 5 else ""),
                    "reasoning": bool(m) and ("reasoning" in (m.get("capabilities") or []) or bool(m.get("reasoning"))), "effort": "reasoning_effort" in (m.get("supported_parameters") or []),
                    "tools": ("tool_calling" in (m.get("capabilities") or []) or bool(m.get("tools"))) if m else None, "rpm": m.get("per_user_rpm"), "p50": lat.get(mid),
                    "efforts": _pol_effort_ok.get(mid) or (cfg.get("pol_effort_ok") or {}).get(mid)})
    return out

def pol_chain(slug, cfg):
    """So o provedor escolhido: se ele falhar, o erro sobe e a interface recomeca com o proximo mais barato (assim voce ve o erro)."""
    return [slug]

POL_HTTP_ERRORS = {401: "Chave do Pollinations invalida (401). Confira a chave em Configuracoes.", 403: "A chave do Pollinations nao tem permissao (403).", 402: "Saldo de pollen insuficiente (402). Ganhe pollen nas missoes ou compre mais.", 429: "Limite do Pollinations atingido (429). Espere um pouco."}

def stream_pollinations(model, messages, think, cfg, max_tokens=None, agent=False, effort=None):
    """Gera ('content'|'thinking'|'stats'|'status', valor) pela API compativel com OpenAI do Pollinations; no DeepSeek V4.1, se o provedor cair antes de responder tenta o proximo mais barato."""
    key = (cfg.get("pollinations_api_key") or "").strip()
    if not key: raise Exception("Chave do Pollinations nao configurada. Abra Configuracoes e cole sua chave.")
    slug = model[4:]
    if not re.fullmatch(r"[\w.\-/:]+", slug): raise Exception("Modelo do Pollinations invalido.")
    msgs = []
    for m in messages:
        imgs = m.get("images") or []
        if imgs and m["role"] == "user": msgs.append({"role": "user", "content": [{"type": "text", "text": m["content"]}] + [{"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b}} for b in imgs]})
        else: msgs.append({"role": m["role"], "content": m["content"]})
    chain = pol_chain(slug, cfg); last = None
    for n, cand in enumerate(chain):
        payload = {"model": cand, "messages": msgs, "stream": True, "stream_options": {"include_usage": True}}
        if max_tokens: payload["max_tokens"] = int(max_tokens)
        caps = pol_caps(cand, key)   # None: o catalogo nao lista este modelo
        # Esforco de raciocinio: os modelos "pensam" em silencio antes da 1a palavra (a Pollinations nao mostra esse raciocinio): sem o Pensar, o minimo (era 10+ s de "Conectando")
        use_effort = caps["effort"] if caps else bool(re.search(r"(^|/)gpt-[56]", cand) and "oss" not in cand and "codex" not in cand)
        if use_effort:
            want = effort if effort in EFFORT_ORDER else ("medium" if think else "none")
            known = _pol_effort_ok.get(cand) or (cfg.get("pol_effort_ok") or {}).get(cand)
            payload["reasoning_effort"] = (_near_effort(want, known) if known else want) or want
        if agent and (caps is None or caps["tools"]): payload["tools"] = NATIVE_TOOLS_WEB if agent == "web" else (NATIVE_TOOLS_COMP + [t for t in (lumemcp.native_tools() if lumemcp else []) if t["function"]["name"].startswith("mcp__browser__")]) if agent == "comp" else (NATIVE_TOOLS + (lumemcp.native_tools() if lumemcp else []))   # aba Code: chamada de ferramenta nativa (so se o modelo tem a capacidade)
        t0 = time.time()
        hdr = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "lume-app"}
        try:
            response = None
            for attempt in range(3):
                try:
                    response = _cloud_open(urllib.request.Request(POL_API + "/v1/chat/completions", data=json.dumps(payload).encode(), headers=hdr), "O Pollinations"); break
                except urllib.error.HTTPError as e0:
                    body0 = e0.read().decode("utf-8", "replace")
                    if e0.code == 429 and attempt < 2:   # limite de pedidos: espera o tempo que o proprio provedor pede e tenta de novo
                        try: wait = min(15.0, float(e0.headers.get("Retry-After") or 3))
                        except ValueError: wait = 3.0
                        yield "status", f"Limite de pedidos do provedor; esperando {wait:.0f} s"; time.sleep(wait); continue
                    if e0.code == 400 and "reasoning_effort" in payload and attempt < 2:   # o erro diz quais niveis o modelo aceita: usa o mais proximo e lembra
                        mm = re.search(r"upported values are:?([^.\"]*)", body0); ok = [x for x in re.findall(r"'(\w+)'", mm.group(1)) if x in EFFORT_ORDER] if mm else []
                        if ok: _pol_effort_ok[cand] = ok; _remember_efforts(cand, ok); payload["reasoning_effort"] = _near_effort(payload["reasoning_effort"], ok)
                        else: payload.pop("reasoning_effort")
                        continue
                    if e0.code == 400 and "tools" in payload and attempt < 2: payload.pop("tools"); continue   # nem ferramentas nativas: volta ao formato de texto
                    raise _PolHTTP(e0.code, body0)
        except _PolHTTP as e:
            msg = e.body[:200]
            try: j = json.loads(e.body); msg = str((j.get("error") or {}).get("message") or msg)[:200]
            except (ValueError, AttributeError): pass
            last = Exception(POL_HTTP_ERRORS.get(e.code) or f"Pollinations respondeu {e.code}: {msg}")
            if e.code in (401, 403, 402): raise last   # chave ruim ou sem saldo: trocar de provedor nao adianta
            if n + 1 < len(chain): yield "status", f"Provedor {cand.split('/')[1] if '/' in cand else cand} fora do ar; tentando o proximo"
            continue
        except Exception as e:
            last = e
            if n + 1 < len(chain): yield "status", "Provedor fora do ar; tentando o proximo"
            continue
        got = False
        try:
            for item in _sse_chat(response, t0, {}):
                got = True; yield item
            return
        except Exception as e:
            if got: raise
            last = e
            if n + 1 < len(chain): yield "status", "Provedor fora do ar; tentando o proximo"
    raise last or Exception("O Pollinations nao respondeu.")

KEY_FIELDS = tuple((p + ":", v[0]) for p, v in X_PROVIDERS.items()) + (("pol:", "pollinations_api_key"), ("tdc:", "tomdacat_api_key"), ("vc:", "vercel_api_key"), ("l7:", "llm7_api_key"), ("or:", "openrouter_api_key"), ("groq", "groq_api_key"))
_bad_keys = {}   # chave -> ate quando evitar (ela falhou por saldo/limite/invalida)
KEY_FAIL_RE = re.compile(r"\b(401|402|403|429)\b|chave|saldo|pollen|credit|quota|limite|api key|unauthorized", re.I)

# ---------------------------------------------------------------- voz (Pollinations): STT = fala -> texto, TTS = texto -> fala
STT_MODELS = ("openai/whisper-large-v3", "openai/gpt-transcribe", "microsoft/mai-transcribe-2")
TTS_MODELS = ("openai/tts-1", "openai/tts-1-hd", "microsoft/mai-voice-2.1", "microsoft/mai-voice-2.1-flash")
POL_AUDIO_FAIL = {401: "Chave do Pollinations invalida (401).", 402: "Saldo de pollen insuficiente (402).", 403: "A chave do Pollinations nao tem permissao (403).", 429: "Limite do Pollinations atingido (429). Espere um pouco."}

def pol_audio_post(path, body, content_type, cfg, timeout=60):
    """POST de audio no Pollinations com a chave principal e, se ela falhar (invalida, sem saldo, limite), as de reserva. Devolve (bytes, content-type)."""
    keys = list(dict.fromkeys(k for k in [(cfg.get("pollinations_api_key") or "").strip()] + backup_keys(cfg, "pollinations_api_key") if k))
    if not keys: raise Exception("Voz precisa da chave do Pollinations (Configuracoes > Chaves de API).")
    last = None
    for k in keys:
        req = urllib.request.Request(POL_API + path, data=body, headers={"Authorization": "Bearer " + k, "Content-Type": content_type, "User-Agent": "lume-app"})
        try:
            with _cloud_open(req, "O Pollinations", timeout=timeout) as r: return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:200]
            try: msg = str((json.loads(msg).get("error") or {}).get("message") or msg)[:200]
            except (ValueError, AttributeError): pass
            last = Exception(POL_AUDIO_FAIL.get(e.code) or f"Pollinations respondeu {e.code}: {msg}")
            if e.code not in (401, 402, 403, 429): break
    raise last

def pol_tts(text, opts, cfg):
    """Texto -> audio mp3. opts: model (TTS_MODELS), voice. Devolve (bytes, mime)."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()[:4000]
    if not text: raise Exception("Nada para falar.")
    model = opts.get("model") if opts.get("model") in TTS_MODELS else TTS_MODELS[0]
    voice = re.sub(r"[^\w\-]", "", str(opts.get("voice") or ""))[:40] or ("nova" if model.startswith("openai/") else "pt-BR-Luana")
    data, mime = pol_audio_post("/v1/audio/speech", json.dumps({"model": model, "input": text, "voice": voice, "response_format": "mp3"}).encode("utf-8"), "application/json", cfg)
    return data, ("audio/mpeg" if "audio" not in mime else mime)

def pol_stt(audio, mime, opts, cfg):
    """Audio gravado -> texto. opts: model (STT_MODELS), lang (pt, en...)."""
    if not audio: raise Exception("Audio vazio.")
    model = opts.get("model") if opts.get("model") in STT_MODELS else STT_MODELS[0]
    lang = re.sub(r"[^a-zA-Z\-]", "", str(opts.get("lang") or ""))[:8]
    mime = re.sub(r"[^\w/+.\-]", "", str(mime or "audio/webm").split(";")[0]) or "audio/webm"
    ext = {"audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/ogg": "ogg", "audio/wav": "wav", "audio/x-wav": "wav", "audio/webm": "webm"}.get(mime, "webm")
    b = uuid.uuid4().hex; parts = [f'--{b}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode()]
    if lang: parts.append(f'--{b}\r\nContent-Disposition: form-data; name="language"\r\n\r\n{lang}\r\n'.encode())
    parts += [f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="fala.{ext}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + audio + b"\r\n", f"--{b}--\r\n".encode()]
    data, _ = pol_audio_post("/v1/audio/transcriptions", b"".join(parts), "multipart/form-data; boundary=" + b, cfg)
    try: return str(json.loads(data).get("text") or "").strip()
    except ValueError: raise Exception("Resposta estranha do Pollinations ao transcrever.")

# ---------------------------------------------------------------- feedback: manda para o servidor lume-feedback (lume-feedback/server.py)
# ---------------------------------------------------------------- log do Lume Auto (o roteador de modelos): tudo que ele decide fica no terminal e em router.log
ROUTER_LOG = os.path.join(BASE_DIR, "router.log"); _router_lock = threading.Lock()
def router_log_write(lines):
    out = []
    for l in (lines or [])[:200]:
        if not isinstance(l, dict): continue
        t = float(l.get("t") or time.time() * 1000) / 1000; ev = re.sub(r"[^a-z_ -]", "", str(l.get("ev") or "info").lower())[:20] or "info"; msg = re.sub(r"[\r\n]+", " ", str(l.get("msg") or ""))[:600]
        out.append(f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t))} [{ev}] {msg}"); log("ROUTER", f"{ev}: {msg}", COLOR_CYAN)
    if not out: return 0
    with _router_lock:
        try:
            if os.path.exists(ROUTER_LOG) and os.path.getsize(ROUTER_LOG) > 1_500_000:
                os.replace(ROUTER_LOG, ROUTER_LOG + ".1")
            with open(ROUTER_LOG, "a", encoding="utf-8") as f: f.write("\n".join(out) + "\n")
        except OSError: pass
    return len(out)
def router_log_tail(n=300):
    try:
        with open(ROUTER_LOG, "r", encoding="utf-8", errors="replace") as f: return f.read().splitlines()[-max(1, min(int(n), 2000)):]
    except OSError: return []

# ---------------------------------------------------------------- notas dos modelos (inteligencia e velocidade): vem do Gratisfy (dados do Artificial Analysis), guardadas 24 h
SCORES_FILE = os.path.join(BASE_DIR, "model_scores.json"); SCORES_URL = "https://gratisfy.xyz/api/benchmarks"; SCORES_TTL = 24 * 3600
def _score_keys(*names):
    """Chaves para casar um modelo do Lume com uma linha do Gratisfy: o nome sem enfeites, so letras e numeros (igual ao libs/lume-scores.js)."""
    out = set()
    for n in names:
        if not n: continue
        n = re.sub(r"\((?:free|max|xhigh|high|medium|low|default|reasoning|non-reasoning)[^)]*\)", "", str(n).lower()); base = re.sub(r":(free|cloud|thinking|latest|beta)$", "", n.split("/")[-1])
        for v in (n, base):
            k = re.sub(r"[^a-z0-9]", "", v)
            if len(k) >= 4: out.add(k)
    return out
def fetch_model_scores(refresh=False):
    """{ts, rows: [[chave, inteligencia, tok/s], ...]}. Usa o que ja foi baixado (ate 24 h); sem internet devolve o antigo."""
    old = None
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f: old = json.load(f)
    except Exception: pass
    if old and not refresh and time.time() - old.get("ts", 0) < SCORES_TTL: return old
    try:
        req = urllib.request.Request(SCORES_URL, headers={"User-Agent": "lume-app", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as r: d = json.loads(r.read(12_000_000).decode("utf-8"))
        best = {}
        for row in list(d.get("models") or []) + list(d.get("benchmarkRows") or []):
            b = row.get("benchmark") or {}; i = b.get("intelligence")
            if not isinstance(i, (int, float)): continue
            tps = b.get("speed") if isinstance(b.get("speed"), (int, float)) else None
            for k in _score_keys(row.get("id"), row.get("name"), b.get("aaSlug"), b.get("aaName"), *(row.get("sourceModelIds") or [])):
                if k not in best or i > best[k][0]: best[k] = (i, tps)
        out = {"ts": time.time(), "rows": [[k, v[0], v[1]] for k, v in best.items()]}
        with open(SCORES_FILE, "w", encoding="utf-8") as f: json.dump(out, f)
        return out
    except Exception as e:
        if old: return old
        raise Exception("Nao consegui baixar as notas dos modelos (" + str(getattr(e, "reason", e))[:80] + ").")

def send_feedback(cfg, d):
    """Repassa o feedback ao servidor configurado em feedback_url. Nunca manda config.json, chaves nem conversas: so o que o usuario escreveu, a imagem que ele anexou e (se marcou) versao/sistema."""
    url = str(cfg.get("feedback_url") or "").strip().rstrip("/")
    if not re.match(r"^https?://", url): raise Exception("Configure o endereco do servidor de feedback primeiro.")
    body = {k: d.get(k) for k in ("category", "message", "contact", "version", "os", "log", "screenshot_b64")}; body["app"] = "Lume"
    headers = {"Content-Type": "application/json", "User-Agent": "lume-app"}
    if cfg.get("feedback_key"): headers["X-Feedback-Key"] = str(cfg["feedback_key"])
    try:
        with urllib.request.urlopen(urllib.request.Request(url + "/api/feedback", data=json.dumps(body).encode("utf-8"), headers=headers), timeout=20) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        try: msg = json.load(e).get("error")
        except Exception: msg = ""
        raise Exception(msg or f"o servidor de feedback respondeu {e.code}")
    except Exception as e: raise Exception("Nao consegui falar com o servidor de feedback (" + str(getattr(e, "reason", e))[:80] + ").")

def backup_keys(cfg, field):
    """Chaves de reserva (campo <chave>_backup: uma por linha ou separadas por virgula)."""
    return [k for k in re.split(r"[\s,;]+", str(cfg.get(field + "_backup") or "")) if k]

def stream_model(model, messages, think, cfg, num_ctx=None, max_tokens=None, agent=False, effort=None):
    """Usa a chave principal; se ela morrer (invalida, sem saldo, limite) antes de qualquer resposta, tenta as chaves de reserva."""
    field = next((f for pre, f in KEY_FIELDS if model.startswith(pre)), None)
    keys = list(dict.fromkeys(k for k in [(cfg.get(field) or "").strip()] + backup_keys(cfg, field) if k)) if field else []
    if field and len(keys) > 1:
        def gen():
            now = time.time(); order = [k for k in keys if _bad_keys.get(k, 0) < now] + [k for k in keys if _bad_keys.get(k, 0) >= now]
            for i, k in enumerate(order):
                got = False
                try:
                    for ev in _stream_model_once(model, messages, think, dict(cfg, **{field: k}), num_ctx, max_tokens, agent, effort):
                        if ev[0] in ("content", "thinking"): got = True
                        yield ev
                    return
                except Exception as e:
                    if got or i + 1 >= len(order) or not KEY_FAIL_RE.search(str(e)): raise
                    _bad_keys[k] = time.time() + 600
                    log("CHAVES", f"Chave {i + 1} de {field.split('_')[0]} falhou ({str(e)[:80]}); usando a de reserva.", COLOR_YELLOW)
                    yield "status", "Chave principal falhou; usando a de reserva"
        return gen()
    return _stream_model_once(model, messages, think, cfg, num_ctx, max_tokens, agent, effort)

def _stream_model_once(model, messages, think, cfg, num_ctx=None, max_tokens=None, agent=False, effort=None):
    for _p, (_f, _u, _n, _s) in X_PROVIDERS.items():
        if model.startswith(_p + ":"):
            if _p in X_LIMIT: quota_hit(_p)
            return stream_openai_compat(model[len(_p) + 1:], messages, _u, cfg.get(_f), "O " + _n, max_tokens)
    if model.startswith("pol:"): return stream_pollinations(model, messages, think, cfg, max_tokens, agent, effort)
    if model.startswith("tdc:"): return stream_tomdacat(model, messages, cfg, max_tokens)
    if model.startswith("vc:"): return stream_openai_compat(model[3:], messages, VERCEL_URL, cfg.get("vercel_api_key"), "A Vercel", max_tokens)
    if model.startswith("l7:"): return stream_openai_compat(model[3:], messages, LLM7_URL, cfg.get("llm7_api_key"), "O LLM7", max_tokens)
    if model.startswith("or:"): return stream_openrouter(model, messages, think, cfg, max_tokens)
    if model.startswith("cf:"): return stream_cloudflare(model, messages, think, cfg, max_tokens)
    return stream_groq(model, messages, cfg, max_tokens) if model.startswith("groq") else stream_ollama(model, messages, think, num_ctx, max_tokens)

# ---------------------------------------------------------------- <think> dentro do texto
class ThinkSplitter:
    """Alguns modelos (DeepSeek R1 local, varios provedores) misturam o raciocinio no texto, entre <think> e </think>, em vez de mandar a parte "thinking" separada.
    Isto separa o fluxo em tempo real: o que esta entre as tags vira ("thinking", ...), o resto ("content", ...). Aguenta tag cortada entre dois pedacos
    e o caso de so vir o </think> (o modelo abriu o raciocinio no proprio prompt: tudo antes do </think> era raciocinio)."""
    OPEN = re.compile(r"<think(?:ing)?>", re.I); CLOSE = re.compile(r"</think(?:ing)?>", re.I)
    TAGS = ("<think>", "<thinking>", "</think>", "</thinking>")
    def __init__(self): self.buf = ""; self.inside = False; self.seen = False   # seen = ja saiu texto de resposta
    def _hold(self):
        """Quantos caracteres do fim do buffer podem ser o comeco de uma tag (ficam guardados ate a proxima parte)."""
        low = self.buf.lower(); i = low.rfind("<")
        if i < 0: return 0
        tail = low[i:]
        return len(tail) if any(t.startswith(tail) and tail != t for t in self.TAGS) else 0
    def feed(self, text):
        self.buf += text; out = []
        while True:
            m_open = None if self.inside else self.OPEN.search(self.buf)
            m_close = self.CLOSE.search(self.buf) if (self.inside or not self.seen) else None   # fora do raciocinio, so aceita </think> solto se ainda nao saiu resposta
            m = min((x for x in (m_open, m_close) if x), key=lambda x: x.start(), default=None)
            if m is None: break
            pre = self.buf[:m.start()]
            if pre: out.append(("thinking" if (self.inside or m is m_close) else "content", pre))
            if pre.strip() and not (self.inside or m is m_close): self.seen = True
            self.buf = self.buf[m.end():]; self.inside = (m is m_open)
        keep = self._hold(); emit = self.buf[:len(self.buf) - keep]
        if emit:
            out.append(("thinking" if self.inside else "content", emit))
            if not self.inside and emit.strip(): self.seen = True
        self.buf = self.buf[len(self.buf) - keep:]
        return out
    def flush(self):
        rest, self.buf = self.buf, ""
        return [("thinking" if self.inside else "content", rest)] if rest else []

# ---------------------------------------------------------------- servidor
LOOPBACK_IPS = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
LOCAL_HOSTS = ("127.0.0.1", "localhost")
# So estes arquivos sao servidos (nunca config.json, history.json, app.py...)
STATIC_PAGES = ("/", "/index.html")
PAGE_ALIAS = {"/share": "/share.html", "/dashboard": "/dashboard.html", "/feedback": "/feedback.html", "/quick": "/quick.html", "/pet": "/pet.html"}
# So o proprio PC (janela do app) pode usar estas rotas
LOCAL_ONLY_POST = ("/api/open_path", "/api/mcp_auto", "/api/mcp_save", "/api/save_config", "/api/save_key", "/api/server_config", "/api/perf_interval",
                   "/api/custom_theme", "/api/custom_theme_delete", "/api/account_import", "/api/config_import", "/api/pol_effort_probe", "/api/account/login", "/api/account/logout", "/api/resolve_pending", "/api/export", "/api/ios_profile_save", "/api/undo", "/api/stats_clear", "/api/open_url", "/api/update_apply", "/api/restart_app", "/api/run_code", "/api/run_stop", "/api/tunnel_start", "/api/tunnel_stop", "/api/tunnel_install", "/api/app_options", "/api/model_pull", "/api/model_delete", "/api/models_update_now", "/api/cloudflare_usage_set")
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
CUSTOM_ICON = os.path.join(RES_DIR, "icons", "lume.png")   # se existir, e o icone do app (janela, .exe, bandeja): a logo com fundo transparente
MOBILE_ICON = os.path.join(RES_DIR, "icons", "lume-mobile.png")   # icone do iPhone / aba do navegador: logo menor sobre um gradiente (make_icons.py)

def make_icon_png(size=180):
    """Icone do app: icons/lume.png se existir; senao um raio branco sobre azul gerado sem bibliotecas externas."""
    for path in (MOBILE_ICON, CUSTOM_ICON):
        if os.path.isfile(path):
            try:
                with open(path, "rb") as f: return f.read()
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
    "Chave do OpenRouter nao configurada": "OpenRouter API key not set. Open Settings and paste your key.",
    "Chave do OpenRouter invalida": "Invalid OpenRouter key (401). Check the key in Settings.", "O OpenRouter pediu credito": "OpenRouter asked for credit (402): this model is not free for your account.",
    "Limite do plano gratis do OpenRouter": "OpenRouter free plan limit reached (429). Wait a bit or try again tomorrow.", "O OpenRouter nao achou esse modelo": "OpenRouter could not find that model (404): it may have left the free list.",
    "Este modelo do OpenRouter nao e gratis": "This OpenRouter model is not free: Lume only uses free models.",
    "Token do Cloudflare nao configurado": "Cloudflare token not set. Open Settings and paste the token and Account ID.", "Token do Cloudflare invalido": "Invalid Cloudflare token (401). Check the token and Account ID in Settings.",
    "O token do Cloudflare nao tem permissao": "The Cloudflare token has no Workers AI permission (403).", "Limite diario gratis do Cloudflare": "Cloudflare daily free limit reached (10,000 neurons). Come back tomorrow or wait a bit.",
    "Modelo do Cloudflare invalido": "Invalid Cloudflare model: only Workers AI (@cf/...) models are used.",
    "Este modelo do Cloudflare nao esta disponivel": "This Cloudflare model is not available on the free plan (Workers Paid only): it was removed from the list.", "Esta conta do Cloudflare nao tem acesso": "This Cloudflare account has no access to this model: it was removed from the list.",
    "Este modelo do Cloudflare exige aceitar": "This Cloudflare model requires accepting a license agreement in the Cloudflare dashboard: it was removed from the list.",
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
        srv = TLSServer(("0.0.0.0", port), functools.partial(AppHandler, directory=RES_DIR))
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
        try: self.end_headers(); self.wfile.write(body)
        except (ConnectionError, OSError): pass   # a pagina fechou/recarregou no meio da resposta: nao e erro do Lume (antes enchia o terminal de traceback)

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
        icon_ok = ((p.startswith('/icons/') and '/' not in p[len('/icons/'):]) or (p.startswith('/fonts/') and p.endswith('.woff2') and '/' not in p[len('/fonts/'):]) or (p.startswith('/sounds/') and re.fullmatch(r'/sounds/[\w.\-]+\.(?:mp3|wav|m4a|ogg)', p) is not None) or (p.startswith('/libs/') and re.fullmatch(r'/libs/(?:stockfish/)?[\w.\-]+\.(?:js|css|wasm|txt)', p) is not None)) and '\\' not in p and '..' not in p
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
        if p == '/downloadowner':
            return self.download_owner()
        if not p.startswith('/api/'):
            return self.serve_static(p)
        local = self.is_local()
        if p == '/api/app_options':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json(app_options())
        if p == '/api/ui_rev':   # a interface pergunta daqui a pouco se algum arquivo dela mudou (so rodando do codigo-fonte)
            return self.send_json({"dev": bool(local and dev_enabled()), "rev": ui_rev() if local and dev_enabled() else "", "busy": bool(gens_active), "updated": bool(UPDATED_AT and time.time() - UPDATED_AT < 90), "pending": bool(DEV_PENDING["on"])})
        if p == '/api/browser/status':
            if not local or not lumebrowser: return self.send_json({"error": "local_only"}, 403)
            return self.send_json(lumebrowser.info())
        if p == '/api/browser/list':   # navegadores instalados (para escolher onde instalar a extensao)
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json({"browsers": installed_browsers()})
        if p == '/api/mcp':
            if not local or not lumemcp: return self.send_json({"error": "local_only"}, 403)
            _c = load_config().get("mcp_servers") or {}
            return self.send_json({"json": lumemcp.to_json(_c), "status": lumemcp.status(_c), "auto": bool(load_config().get("mcp_auto_allow"))})
        if p == '/api/tunnel':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json({**tunnel_state, "cloudflared": bool(find_cloudflared()), "tailscale": tailscale_status(), "port": PORT})
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
            return self.send_json({"cmd": pending_command["cmd"], "rule": pending_command["rule"], "detail": pending_command["detail"]} if local else {"cmd": ""})   # so o PC aprova comandos
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
        if p == '/api/openrouter_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            has = bool(load_config().get("openrouter_api_key"))
            if not has: return self.send_json({"key_saved": False, "models": []})
            try: return self.send_json({"key_saved": True, "models": openrouter_free_models()})
            except Exception as e: return self.send_json({"key_saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/vercel_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            if not cfg.get("vercel_api_key"): return self.send_json({"saved": False, "models": []})
            try: return self.send_json({"saved": True, "models": vercel_models(cfg)})
            except Exception as e: return self.send_json({"saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/tokenreply_usage':
            if not local: return self.send_json({"error": "local_only"}, 403)
            key = (load_config().get("tokenreply_api_key") or "").strip()
            if not key: return self.send_json({"error": "sem chave"}, 400)
            try:
                with urllib.request.urlopen(urllib.request.Request(TK_URL[:-3] + "/api/usage/token/", headers={"Authorization": "Bearer " + key, "User-Agent": "lume-app"}), timeout=15) as r: j = (json.load(r) or {}).get("data") or {}
                return self.send_json({"available": j.get("total_available_usd"), "granted": j.get("total_granted_usd"), "used": j.get("total_used_usd")})
            except Exception as e: return self.send_json({"error": str(e)[:160]}, 502)
        if p == '/api/voidai_credits':
            if not local: return self.send_json({"error": "local_only"}, 403)
            key = (load_config().get("voidai_api_key") or "").strip()
            if not key: return self.send_json({"error": "sem chave"}, 400)
            try:
                with urllib.request.urlopen(urllib.request.Request(VD_URL + "/credits", headers={"Authorization": "Bearer " + key, "User-Agent": "lume-app"}), timeout=15) as r: j = json.load(r)
                return self.send_json({"credits": j.get("current_credits"), "limit": j.get("daily_limit"), "plan": j.get("plan"), "used": j.get("credits_used")})
            except Exception as e: return self.send_json({"error": str(e)[:160]}, 502)
        if p == '/api/extra_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config(); out = {}
            for prov, (field, _u, _n, _s) in X_PROVIDERS.items():
                if not cfg.get(field): out[prov] = {"saved": False, "models": []}; continue
                try: out[prov] = {"saved": True, "models": extra_models(prov, cfg)}
                except Exception as e:   # a lista nao veio agora: mostra a ultima que funcionou
                    old = _read_json(LAST_FILE, {}); old = old.get(prov) if isinstance(old, dict) else None
                    out[prov] = {"saved": True, "models": [m for m in (old or []) if model_is_healthy(prov, m["id"])], "error": str(e)[:200], "stale": bool(old)}
            out["_checking"] = _health_state["on"]
            return self.send_json(out)
        if p == '/api/llm7_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            if not cfg.get("llm7_api_key"): return self.send_json({"saved": False, "models": []})
            try: return self.send_json({"saved": True, "models": llm7_models(cfg)})
            except Exception as e: return self.send_json({"saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/tomdacat_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            if not cfg.get("tomdacat_api_key"): return self.send_json({"saved": False, "models": []})
            try: return self.send_json({"saved": True, "models": tomdacat_models(cfg)})
            except Exception as e: return self.send_json({"saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/groq_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            if not cfg.get("groq_api_key"): return self.send_json({"saved": False, "models": []})
            try: return self.send_json({"saved": True, "models": groq_models(cfg)})
            except Exception as e: return self.send_json({"saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/pol_menu':
            if not local: return self.send_json({"error": "local_only"}, 403)
            try: return self.send_json({"models": pollinations_menu(load_config())})
            except Exception as e: return self.send_json({"error": str(e)[:200], "models": []})
        if p == '/api/pollinations_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            if not cfg.get("pollinations_api_key"): return self.send_json({"saved": False, "models": []})
            try: return self.send_json({"saved": True, "models": pollinations_models(cfg)})
            except Exception as e: return self.send_json({"saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/pollinations_usage':
            if not local: return self.send_json({"error": "local_only"}, 403)
            key = load_config().get("pollinations_api_key") or ""
            if not key: return self.send_json({"error": "sem chave"}, 400)
            try:
                with _pol_req("/account/balance", key, timeout=15) as r: return self.send_json({"balance": json.load(r).get("balance")})
            except Exception as e: return self.send_json({"error": str(e)[:160]}, 502)
        if p == '/api/cloudflare_usage':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json(cf_usage())
        if p == '/api/cloudflare_models':
            if not local: return self.send_json({"error": "local_only"}, 403)
            cfg = load_config()
            if not all(cf_creds(cfg)): return self.send_json({"saved": False, "models": []})
            probing = cfg.get("cloudflare_probe_acc") != cf_probe_key(cfg) or (self.query.get("reprobe") or [""])[0] == "1"
            try:
                models = cloudflare_models(cfg)
                if probing and not _cf_probe["running"]: threading.Thread(target=cloudflare_probe, daemon=True).start()
                return self.send_json({"saved": True, "models": models, "probing": probing})
            except urllib.error.HTTPError as e: return self.send_json({"saved": True, "models": [], "error": CF_HTTP_ERRORS.get(e.code) or f"Cloudflare respondeu {e.code}"})
            except Exception as e: return self.send_json({"saved": True, "models": [], "error": str(e)[:200]})
        if p == '/api/router_log':
            return self.send_json({"lines": router_log_tail(self.query.get('n', ['300'])[0] or 300), "file": ROUTER_LOG if local else ""})
        if p == '/api/model_scores':   # nota de inteligencia e velocidade por modelo (Gratisfy/Artificial Analysis); so baixa, nao manda nada seu
            try: return self.send_json(fetch_model_scores(self.query.get('refresh', [''])[0] == '1'))
            except Exception as e: return self.send_json({"error": str(e)[:200]}, 502)
        if p == '/api/providers_overview':   # painel de provedores: chave salva, quantos estao fora do ar e quando foi o ultimo teste (nunca devolve a chave)
            cfg = load_config(); out = {}
            for prov, (field, _u, name, _s) in X_PROVIDERS.items():
                mine = {k.split(":", 1)[1]: h for k, h in _health.items() if k.startswith(prov + ":")}
                out[prov] = {"name": name, "key": bool(cfg.get(field)), "show_all": prov in X_SHOW_ALL, "failing": [i for i, h in mine.items() if not h.get("ok", True)][:30], "tested": len(mine), "last": max([h.get("ts", 0) for h in mine.values()] or [0]), "limit": X_LIMIT.get(prov), "used_today": quota_today(prov) if prov in X_LIMIT else None}
            return self.send_json(out)
        if p == '/api/config_status':
            cfg = load_config()
            return self.send_json({"groq_key_saved": bool(cfg.get("groq_api_key")), "openrouter_key_saved": bool(cfg.get("openrouter_api_key")), "cloudflare_saved": all(cf_creds(cfg)), "pollinations_saved": bool(cfg.get("pollinations_api_key")), "tomdacat_saved": bool(cfg.get("tomdacat_api_key")), "vercel_saved": bool(cfg.get("vercel_api_key")), "llm7_saved": bool(cfg.get("llm7_api_key")), "x_saved": {p: bool(cfg.get(v[0])) for p, v in X_PROVIDERS.items()}, "aichixia_saved": bool(cfg.get("aichixia_api_key")), "aihubmix_saved": bool(cfg.get("aihubmix_api_key")), "literouter_saved": bool(cfg.get("literouter_api_key")),  "feedback_url": cfg.get("feedback_url", ""), "exa_key_saved": bool(exa_api_key(cfg)), "search_provider": cfg.get("search_provider", "auto"), "exa_type": cfg.get("exa_type", "lite"), "search_results": max_results(), "search_daily_limit": cfg.get("search_daily_limit", 100), "exa_today": exa_searches_today(), "auto_allow": bool(cfg.get("auto_allow")), "computer_control": bool(cfg.get("computer_control")) and computer_supported(), "computer_supported": computer_supported(), "max_agent_steps": int(cfg.get("max_agent_steps") or MAX_AGENT_STEPS), "workdir": get_workdir(cfg) if local else "", "default_workdir": BASE_DIR if local else ""})
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
                "generation_active": bool(gens_active), "alert": alert_state
            })
        if p == '/api/account_export':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json(export_accounts((self.query.get('all') or ['0'])[0] == '1'))
        if p == '/api/account':
            if not local: return self.send_json({"error": "local_only"}, 403)
            return self.send_json({"name": ACTIVE_ACCOUNT, "owner": OWNER_NAME, "accounts": list_accounts()})
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
            if self.is_desktop():   # root vindo do iPhone usa o endereco que ele mesmo abriu (como qualquer celular), nao o IP do PC
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
        if origin and urllib.parse.urlsplit(origin).netloc != (self.headers.get('Host') or '') and not (p.startswith('/api/browser/') and lumebrowser and lumebrowser.ext_origin(origin)):   # (a extensao do navegador tem origem propria, mas so nas rotas /api/browser/)
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
        if p.startswith('/api/browser/'):   # a extensao do navegador (so o proprio PC; parear exige Origin de extensao)
            if not local or not lumebrowser: return self.send_json({"error": "local_only"}, 403)
            try: _d = json.loads(post_data or b"{}")
            except Exception: _d = {}
            if p == '/api/browser/install':   # botao das configuracoes (so deste PC)
                return self.send_json(browser_install(_d.get("browser")))
            if p == '/api/browser/pair':
                tk = lumebrowser.pair(self.headers.get("Origin", ""))
                if not tk: return self.send_json({"error": "origin"}, 403)
                return self.send_json({"token": tk, "app": "lume"})
            if p == '/api/browser/poll': return self.send_json(lumebrowser.poll(_d.get("token"), _d.get("info")))
            if p == '/api/browser/result': return self.send_json({"ok": bool(lumebrowser.deliver(_d.get("token"), _d.get("id"), _d.get("result")))})
            return self.send_json({"error": "not_found"}, 404)
        quiet = ('/api/chat', '/api/history', '/api/state', '/api/browser/poll', '/api/browser/result')
        if p not in quiet: log("API", f"POST {p}", COLOR_BLUE)
        try:
            data = {} if p == '/api/chat' else json.loads(post_data or b'{}')
        except ValueError:
            return self.send_json({"error": "json invalido"}, 400)

        if p == '/api/auth/login':
            return self.handle_login(data)
        if p == '/api/account/login':
            name = str(data.get("name") or "").strip()
            if name and name != OWNER_NAME and not safe_account_name(name): return self.send_json({"error": "Nome invalido."}, 400)
            if not use_account(name): return self.send_json({"error": "Nao da para entrar nessa conta."}, 400)
            cfg = load_config(); cfg["active_account"] = ACTIVE_ACCOUNT; save_config(cfg); log("CONTA", f"Conta ativa no PC: {ACTIVE_ACCOUNT or OWNER_NAME}", COLOR_GREEN)
            return self.send_json({"ok": True, "name": ACTIVE_ACCOUNT})
        if p == '/api/config_import':
            try: new_cfg, n, skipped = import_config(data.get("config"), load_config())
            except ValueError as e: return self.send_json({"error": str(e)}, 400)
            try: shutil.copy2(CONFIG_FILE, CONFIG_FILE + ".bak")   # copia de seguranca do que estava antes
            except OSError: pass
            save_config(new_cfg); log("CONFIG", f"config.json importado: {n} campo(s); {len(skipped)} ignorado(s)", COLOR_GREEN)
            return self.send_json({"ok": True, "imported": n, "skipped": len(skipped)})
        if p == '/api/account_import':
            try: res = import_accounts(data.get("data"))
            except ValueError as e: return self.send_json({"error": str(e)}, 400)
            log("CONTA", f"Importadas {len(res)} conta(s) de um arquivo", COLOR_GREEN); return self.send_json({"ok": True, "imported": res})
        if p == '/api/provider_ping':   # 1 pedido pequeno de verdade a um modelo do provedor (so os provedores extras)
            prov = str(data.get("prov") or ""); cfg = load_config()
            if prov not in X_PROVIDERS: return self.send_json({"error": "provedor invalido"}, 400)
            if not cfg.get(X_PROVIDERS[prov][0]): return self.send_json({"ok": False, "err": "sem chave"})
            try: ids = [m["id"] for m in extra_models(prov, cfg, force=False, raw=True)]
            except Exception as e: return self.send_json({"ok": False, "err": str(e)[:120]})
            if not ids: return self.send_json({"ok": False, "err": "nenhum modelo listado"})
            ok, ms, err = health_test(prov, ids[0], cfg)
            if ok is not None and prov not in X_SHOW_ALL: _health[prov + ":" + ids[0]] = {"ok": bool(ok), "ts": time.time(), "ms": ms, "err": err}
            return self.send_json({"ok": ok, "ms": ms, "err": err, "model": ids[0]})
        if p == '/api/feedback_send':
            try: return self.send_json(send_feedback(load_config(), data))
            except Exception as e: return self.send_json({"error": str(e)[:200]}, 502)
        if p == '/api/tts':
            try: audio, mime = pol_tts(data.get("text"), data, load_config())
            except Exception as e: return self.send_json({"error": str(e)[:200]}, 502)
            self.send_response(200); self.send_header('Content-Type', mime); self.send_header('Content-Length', str(len(audio))); self.end_headers(); self.wfile.write(audio); return
        if p == '/api/stt':
            try: text = pol_stt(base64.b64decode(str(data.get("audio") or ""), validate=False), data.get("mime"), data, load_config())
            except Exception as e: return self.send_json({"error": str(e)[:200]}, 502)
            return self.send_json({"text": text})
        if p == '/api/pol_effort_probe':
            try: levels, source = probe_pol_efforts(str(data.get("model") or ""), load_config())
            except Exception as e: return self.send_json({"error": str(e)[:200]})
            log("ESFORCO", f"{data.get('model')}: aceita {levels} ({source})", COLOR_GREEN); return self.send_json({"ok": True, "levels": levels, "source": source})
        if p == '/api/account/logout':
            use_account(""); cfg = load_config(); cfg["active_account"] = ""; save_config(cfg); return self.send_json({"ok": True})
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
            for k, lo, hi in (("search_results", 1, 25), ("search_daily_limit", 0, 100000), ("max_agent_steps", 1, 200)):
                if k in data:
                    try: data[k] = max(lo, min(hi, int(data[k])))
                    except (TypeError, ValueError): return self.send_json({"error": "Opcao de pesquisa invalida."}, 400)
            for k in ("max_agent_steps", "groq_api_key", "openrouter_api_key", "pollinations_api_key", "cloudflare_api_token", "cloudflare_account_id", "exa_api_key", "tomdacat_api_key", "vercel_api_key", "llm7_api_key", "aichixia_api_key", "aihubmix_api_key", "literouter_api_key", "aichixia_api_key_backup", "aihubmix_api_key_backup", "literouter_api_key_backup", "paxsenix_api_key", "paxsenix_api_key_backup", "voidai_api_key", "voidai_api_key_backup", "tokenreply_api_key", "tokenreply_api_key_backup", "groq_api_key_backup", "openrouter_api_key_backup", "pollinations_api_key_backup", "tomdacat_api_key_backup", "vercel_api_key_backup", "llm7_api_key_backup", "workdir", "search_provider", "exa_type", "search_results", "search_daily_limit", "auto_allow", "computer_control", "feedback_url", "feedback_key", *X_KEY_FIELDS):
                if k in data: cfg[k] = bool(data[k]) if k in ("auto_allow", "computer_control") else data[k].strip() if k.endswith(("_key", "_token", "_id", "_backup", "_url")) else data[k]
            save_config(cfg)
            secrets_sent = [k for k in ("aichixia_api_key", "aihubmix_api_key", "literouter_api_key", "aichixia_api_key_backup", "aihubmix_api_key_backup", "literouter_api_key_backup", "paxsenix_api_key", "paxsenix_api_key_backup", "voidai_api_key", "voidai_api_key_backup", "tokenreply_api_key", "tokenreply_api_key_backup", "groq_api_key_backup", "openrouter_api_key_backup", "pollinations_api_key_backup", "tomdacat_api_key_backup", "vercel_api_key_backup", "llm7_api_key_backup", "groq_api_key", "openrouter_api_key", "pollinations_api_key", "tomdacat_api_key", "vercel_api_key", "llm7_api_key", "cloudflare_api_token", "exa_api_key", *X_KEY_FIELDS) if k in data]
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
            obj, code = extract_api(data)
            if "text" in obj: log("ARQUIVO", f"{data.get('filename')}: {obj['kind']}, {obj['chars']} caracteres" + (" (cortado)" if obj["truncated"] else ""), COLOR_GRAY)
            return self.send_json(obj, code)

        if p == '/api/undo':
            try: return self.send_json({"ok": True, "message": do_undo(str(data.get("id", "")))})
            except Exception as e: return self.send_json({"error": str(e)}, 400)

        if p == '/api/router_log':   # o Lume Auto manda aqui cada decisao (escolha, troca, falha...)
            return self.send_json({"ok": router_log_write(data.get("lines"))})
        if p == '/api/router_log_clear':
            with _router_lock:
                for f in (ROUTER_LOG, ROUTER_LOG + ".1"):
                    try: os.remove(f)
                    except OSError: pass
            return self.send_json({"ok": True})
        if p == '/api/run_code':
            return self.send_json(run_code(data.get("lang"), data.get("code"), bool(data.get("analyze")), bool(data.get("install")), str(data.get("rid") or "") or None))
        if p == '/api/run_stop':
            return self.send_json({"ok": stop_code(str(data.get("rid") or ""))})
        if p == '/api/open_path':   # abre a pasta de dados ou o arquivo de log no Explorer
            _w = data.get("what"); _t = BASE_DIR if _w == "data" else os.path.join(BASE_DIR, "lume.log") if _w == "log" else os.path.join(RES_DIR, "browser-extension") if _w == "extension" else None
            if not _t or not os.path.exists(_t): return self.send_json({"error": "Nao existe."}, 404)
            try: os.startfile(_t)
            except AttributeError: subprocess.Popen(["xdg-open", _t])
            return self.send_json({"ok": True})
        if p == '/api/mcp_auto':
            cfg = load_config(); cfg["mcp_auto_allow"] = bool(data.get("on")); save_config(cfg)
            return self.send_json({"ok": True, "auto": cfg["mcp_auto_allow"]})
        if p == '/api/mcp_save':
            if not lumemcp: return self.send_json({"error": "MCP indisponivel"}, 500)
            try: new = lumemcp.parse_config(data.get("json", ""))
            except ValueError as e: return self.send_json({"error": str(e)}, 400)
            cfg = load_config(); cfg["mcp_servers"] = new; save_config(cfg)
            if data.get("restart"): lumemcp.stop_all()
            lumemcp.sync(new, wait=True)
            return self.send_json({"ok": True, "json": lumemcp.to_json(new), "status": lumemcp.status(new)})
        if p == '/api/update_apply':
            return self.send_json(apply_update())
        if p == '/api/tunnel_install': return self.send_json(install_cloudflared())
        if p == '/api/app_options':
            cfg = load_config()
            if "start_with_terminal" in data:
                cfg["start_with_terminal"] = bool(data["start_with_terminal"]); save_config(cfg); set_terminal(cfg["start_with_terminal"])
            if "auto_update_models" in data:
                cfg["auto_update_models"] = bool(data["auto_update_models"]); save_config(cfg)
            if "ui_lang" in data: set_ui_lang(data["ui_lang"]); cfg = load_config()
            if data.get("quick_style") in QUICK_STYLES: cfg["quick_style"] = data["quick_style"]; save_config(cfg); quick_style_apply()
            if "browser_ai" in data: cfg["browser_ai"] = bool(data["browser_ai"]); save_config(cfg)
            if "quick_hotkey" in data: cfg["quick_hotkey"] = bool(data["quick_hotkey"]); save_config(cfg)
            if "pet_desktop" in data: cfg["pet_desktop"] = bool(data["pet_desktop"]); save_config(cfg)
            if "pet_size" in data: cfg["pet_size"] = max(50, min(400, int(data["pet_size"]))); save_config(cfg)
            if "pet_snap" in data: cfg["pet_snap"] = bool(data["pet_snap"]); save_config(cfg)
            if data.get("pet_reset"): PET["reset"] = True
            if "quick_sel_hotkey" in data: cfg["quick_sel_hotkey"] = bool(data["quick_sel_hotkey"]); save_config(cfg)
            if "log_full" in data:
                cfg["log_full"] = bool(data["log_full"]); save_config(cfg)
            if "auto_reload" in data: cfg["auto_reload"] = bool(data["auto_reload"]); save_config(cfg)
            if "hw_accel" in data:
                if data["hw_accel"] not in HW_MODES: return self.send_json({"error": "Opcao invalida."}, 400)
                cfg["hw_accel"] = data["hw_accel"]; save_config(cfg)
            if "tray" in data:
                cfg["tray_enabled"] = bool(data["tray"]); save_config(cfg)
                if cfg["tray_enabled"] and not tray_start(): cfg["tray_enabled"] = False; save_config(cfg); return self.send_json({"error": "Nao consegui criar o icone da bandeja (falta o pacote pystray)."}, 500)
                if not cfg["tray_enabled"]: tray_stop()
            if "start_with_windows" in data:
                try: autostart_set(bool(data["start_with_windows"]))
                except Exception as e: return self.send_json({"error": f"Nao consegui mudar: {e}"}, 500)
            return self.send_json({"ok": True, **app_options()})
        if p == '/api/tunnel_start': return self.send_json(start_tailscale() if data.get("tool") == "tailscale" else start_tunnel())
        if p == '/api/model_pull': return self.stream_pull(str(data.get("model", "")))
        if p == '/api/model_delete':
            name = str(data.get("model", ""))
            if not re.fullmatch(r'[\w.:\-/]+', name): return self.send_json({"error": "nome invalido"}, 400)
            try:
                try: ollama_unload(name)
                except Exception: pass
                urllib.request.urlopen(urllib.request.Request(f"{OLLAMA_URL}/api/delete", data=json.dumps({"model": name}).encode(), method="DELETE", headers={'Content-Type': 'application/json'}), timeout=30).read()
                _model_info_cache.clear(); log("MODELO", f"{name} apagado.", COLOR_YELLOW)
                return self.send_json({"ok": True})
            except Exception as e:
                return self.send_json({"ok": False, "error": str(e)}, 500)
        if p == '/api/models_update_now':
            if not model_update_state["running"]: threading.Thread(target=update_all_models, daemon=True).start()
            return self.send_json({"ok": True})
        if p == '/api/tunnel_stop': stop_tunnel(); return self.send_json({"ok": True})
        if p == '/api/restart_app':
            self.send_json({"ok": True}); threading.Thread(target=lambda: restart_app(notify=True), daemon=True).start(); return
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

        if p == '/api/cloudflare_usage_set':   # o dono digita o numero que o painel da Cloudflare mostra: a estimativa passa a partir dele
            try: v = float(str(data.get("neurons", "")).replace(",", ".").strip())
            except ValueError: return self.send_json({"error": "numero invalido"}, 400)
            cfg = load_config(); d = cfg.get("cloudflare_neurons") or {}
            if d.get("day") != _utc_day(): d = {"day": _utc_day(), "n": 0.0, "offset": 0.0}
            d["offset"] = round(max(0.0, min(CF_NEURON_LIMIT * 10, v)) - d.get("n", 0.0), 3); cfg["cloudflare_neurons"] = d; save_config(cfg)
            return self.send_json({"ok": True, **cf_usage()})
        if p == '/api/stop':
            rid = str(data.get("rid") or "")
            log("STOP", "Parada solicitada pelo usuario" + (f" ({rid})" if rid else " (todas)"), COLOR_YELLOW)
            if rid: ev = req_stops.get(rid); ev and ev.set()   # ja terminou: nada a fazer
            else:
                for ev in list(req_stops.values()): ev.set()
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
            for rid0, m0 in list(gens_active.items()):
                if m0 == model and rid0 in req_stops: req_stops[rid0].set()
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
        if p == '/api/config_status': return self.send_json({"guest": True, "groq_key_saved": False, "openrouter_key_saved": False, "cloudflare_saved": False, "pollinations_saved": False, "exa_key_saved": False})
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
            if len(post_data) > 55 * 1024 * 1024: return self.send_json({"error": "Historico grande demais."}, 413)
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
            return self.send_json(*extract_api(data))
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

    def download_owner(self):
        """GET /downloadowner: baixa o .mobileconfig que poe na tela do iPhone um icone que entra como dono (<endereco>/owner-CODIGO).
        So responde na rede de casa / Tailscale (nunca por tunel publico): quem baixa isso fica sabendo o codigo."""
        cfg = load_config(); code = cfg.get("owner_code") or ""
        if not (cfg.get("owner_link_enabled") and code and self.on_private_network()):
            log("SEGURANCA", f"/downloadowner recusado ({self.client_ip()})", COLOR_RED)
            self.send_response(404); self.end_headers(); return
        base = ("https://" if self.is_secure_conn() else "http://") + (self.headers.get('Host') or f"127.0.0.1:{PORT}")
        body = build_ios_profile(f"{base}/owner-{code}", APP_NAME + " (dono)")
        log("IPHONE", f"Perfil de dono baixado por {self.client_ip()} (aponta para {base}/owner-...)", COLOR_YELLOW)
        self.send_response(200); self.send_header('Content-Type', 'application/x-apple-aspen-config'); self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Disposition', 'attachment; filename="' + APP_NAME + '-dono.mobileconfig"'); self.send_header('Cache-Control', 'no-store'); self.end_headers()
        self.wfile.write(body)

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

    def stream_pull(self, name):
        """Baixa (ou atualiza) um modelo do Ollama repassando o progresso em linhas JSON."""
        if not re.fullmatch(r'[\w.:\-/]+', name or ""): return self.send_json({"error": "nome invalido"}, 400)
        if not start_ollama(): return self.send_json({"error": "O Ollama nao esta rodando."}, 503)
        self.send_response(200); self.send_header('Content-Type', 'application/x-ndjson'); self.end_headers()
        log("MODELO", f"Baixando {name}...", COLOR_CYAN)
        req = urllib.request.Request(f"{OLLAMA_URL}/api/pull", data=json.dumps({"model": name, "stream": True}).encode(), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                for line in r: self.wfile.write(line); self.wfile.flush()
            _model_info_cache.clear(); log("MODELO", f"{name} pronto.", COLOR_GREEN)
        except (BrokenPipeError, ConnectionResetError):
            log("MODELO", f"Download de {name} cancelado.", COLOR_YELLOW)
        except Exception as e:
            try: self.wfile.write((json.dumps({"error": str(e)}) + "\n").encode()); self.wfile.flush()
            except Exception: pass

    def handle_chat(self, req_json, local=True, guest=None):
        lang = 'en' if req_json.get('lang') == 'en' else 'pt'
        set_ui_lang(lang)
        L = lambda pt, en: en if lang == 'en' else pt
        cfg = load_config()
        agent = bool(req_json.get("agent"))
        gid, gmax, stop_ev = None, None, None
        rid = str(req_json.get('rid') or '')[:40] or uuid.uuid4().hex[:10]
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
        if gid: stop_ev.clear()
        else: stop_ev = req_stops[rid] = threading.Event()
        stopped = stop_ev.is_set
        started = time.time()
        model = req_json.get('model', 'qwen3.5:4b')
        if not gid: gens_active[rid] = model
        messages = req_json.get("messages", [])
        think = bool(req_json.get("think"))
        num_ctx = req_json.get("num_ctx")
        workdir = get_workdir(cfg)
        n_images = sum(len(m.get("images", [])) for m in messages)
        if cfg.get("log_full"): log("USUARIO", next((m["content"] for m in reversed(messages) if m.get("role") == "user"), ""), COLOR_YELLOW)
        log("CHAT", f"modelo={model} modo={'agente' if agent else 'chat'} mensagens={len(messages)} imagens={n_images} contexto={num_ctx or 'padrao'} pensar={think} web={bool(req_json.get('search_web'))}" + ("" if local else f" origem={self.client_address[0]}"), COLOR_CYAN)

        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.end_headers()

        def emit(obj):
            self.wfile.write((json.dumps(obj) + '\n').encode()); self.wfile.flush()
        verbose = bool(cfg.get("log_full")); think_buf = []   # "mostrar tudo no terminal": imprime o raciocinio, a resposta inteira, as chamadas de ferramenta e os resultados
        def send(text, kind="content"):
            if kind == "thinking" and verbose: think_buf.append(text)
            emit({"message": {"role": "assistant", kind: text}})
        def status(text): emit({"status": text})

        total_chars = 0
        web_tool = bool(req_json.get("search_web")) and not agent   # a IA decide quando pesquisar (ferramenta)
        comp_chat = (not agent) and bool(load_config().get("computer_control")) and computer_supported() and local   # Chat com o controle do computador (ligado nas opcoes); so no PC do dono
        browser_chat = (not agent) and local and bool(lumebrowser and lumebrowser.connected()) and bool(load_config().get("browser_ai", True))   # Chat com a extensao do navegador conectada
        use_tools = agent or web_tool or comp_chat or browser_chat; max_steps = max(1, min(200, int(load_config().get("max_agent_steps") or MAX_AGENT_STEPS))) if (agent or comp_chat or browser_chat) else 4
        kw_model = {k: v for k, v in (("agent", ("comp" if (comp_chat or browser_chat) else "web" if web_tool else True) if use_tools else None), ("effort", str(req_json.get("effort") or "") or None)) if v}   # so manda o que foi pedido
        try:
            if not model.startswith(CLOUD_PREFIXES):
                if not ollama_is_running():
                    status("Iniciando Ollama")
                    if not start_ollama(): raise Exception("Nao consegui iniciar o Ollama. Ele esta instalado?")
                if model not in [m["name"] for m in ollama_ps()]:
                    status("Carregando modelo")
            else:
                status("Esperando a Vercel responder" if model.startswith("vc:") else "Esperando o LLM7 responder" if model.startswith("l7:") else "Esperando o tomdacat responder" if model.startswith("tdc:") else "Conectando ao OpenRouter" if model.startswith("or:") else "Conectando ao Cloudflare" if model.startswith("cf:") else "Esperando o Pollinations responder" if model.startswith("pol:") else ("Conectando ao " + X_PROVIDERS[model.split(":")[0]][2]) if model.split(":")[0] in X_PROVIDERS else "Conectando ao Groq")

            if not messages or messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": ""})
            if agent:
                _tp = (TOOL_PROMPT_EN if lang == 'en' else TOOL_PROMPT).replace("{workdir}", workdir)
                if load_config().get("computer_control") and computer_supported():   # controle do mouse/teclado: so aparece para a IA se o dono ligou nas opcoes
                    _cut = _tp.index("Make ONE call" if lang == 'en' else "Faca UMA chamada"); _tp = _tp[:_cut] + (COMPUTER_PROMPT_EN if lang == 'en' else COMPUTER_PROMPT_PT) + _tp[_cut:]
                _mcp_txt = lumemcp.prompt_lines(lang) if lumemcp else ""
                if _mcp_txt:   # ferramentas dos servidores MCP ligados
                    _cut = _tp.index("Make ONE call" if lang == 'en' else "Faca UMA chamada"); _tp = _tp[:_cut] + _mcp_txt + _tp[_cut:]
                messages[0]["content"] += _tp
            elif web_tool or comp_chat or browser_chat:
                if web_tool: messages[0]["content"] += WEB_TOOL_PROMPT_EN if lang == 'en' else WEB_TOOL_PROMPT
                if comp_chat: messages[0]["content"] += COMPUTER_CHAT_EN if lang == 'en' else COMPUTER_CHAT_PT
                if browser_chat: messages[0]["content"] += browser_chat_prompt(lang)
            corrections = 0; native_tries = 0
            req_tokens = req_prompt = 0; req_seconds = 0.0   # para as estatisticas
            clean = list(messages)   # conversa sem as tentativas falhas e sem os pedidos de correcao (o plano B usa esta)
            failed_pending = False   # a ultima tentativa de chamar ferramenta falhou e ainda nao houve uma boa
            for step in range(max_steps if use_tools else 1):
                if step: emit({"step": step})   # a interface separa o pensamento de cada rodada em um bloco
                full = ""
                gen = stream_model(model, messages, think, cfg, num_ctx, gmax, **kw_model); splitter = ThinkSplitter()
                try:
                    for kind, piece in gen:
                        if stopped(): break
                        if kind == "status": status(piece); continue
                        if kind == "thinking":
                            send(piece, "thinking")
                            if verbose: term_stream(rid, "IA · RACIOCINIO", str(piece), COLOR_GRAY, model)
                            continue
                        if kind == "stats":
                            ptps = piece['prompt_tokens'] / piece['prompt_seconds'] if piece['prompt_seconds'] else 0
                            log("OLLAMA", f"{piece['tokens']} tokens em {piece['seconds']:.1f}s = {piece['tokens'] / piece['seconds']:.1f} t/s | prompt {piece['prompt_tokens']} tokens ({ptps:.0f} t/s) | carga do modelo {piece['load_seconds']:.1f}s | total {piece['total_seconds']:.1f}s", COLOR_GREEN)
                            req_tokens += piece["tokens"]; req_seconds += piece["seconds"]; req_prompt += piece["prompt_tokens"]
                            emit({"stats": piece}); continue
                        for k2, p2 in splitter.feed(piece):
                            if k2 == "thinking": send(p2, "thinking"); verbose and term_stream(rid, "IA · RACIOCINIO", p2, COLOR_GRAY, model)
                            else: full += p2; send(p2); verbose and term_stream(rid, "IA · RESPOSTA", p2, COLOR_CYAN, model)
                        if use_tools and ('}' in piece or '$' in piece) and find_tool_call(full): break
                    for k2, p2 in splitter.flush():   # sobras do buffer (uma tag que nunca terminou de chegar)
                        if k2 == "thinking": send(p2, "thinking"); verbose and term_stream(rid, "IA · RACIOCINIO", p2, COLOR_GRAY, model)
                        else: full += p2; send(p2); verbose and term_stream(rid, "IA · RESPOSTA", p2, COLOR_CYAN, model)
                finally:
                    gen.close()
                total_chars += len(full)
                if verbose:   # o texto ja saiu ao vivo (term_stream): so fecha a linha
                    think_buf.clear(); term_stream_end()
                if stopped():
                    send(L("\n\n[Geracao parada]", "\n\n[Generation stopped]"))
                    break
                call = find_tool_call(full) if use_tools else None
                if not call:
                    if use_tools and corrections < 2 and (invented_result(full) or looks_like_failed_call(full) or (agent and announces_action(full))):   # errou o formato (ou disse que ia agir e nao chamou nada): pede para repetir (ate 2 vezes)
                        corrections += 1; failed_pending = True
                        log("AGENTE", "A IA " + ("INVENTOU o resultado de uma ferramenta" if invented_result(full) else "disse que ia agir mas nao chamou nenhuma ferramenta" if (agent and announces_action(full) and not looks_like_failed_call(full)) else "errou o formato da chamada") + "; chamando a atencao dela. Mensagem COMPLETA dela, sem filtro:", COLOR_YELLOW)
                        if not verbose: log("IA · MENSAGEM COMPLETA", f"({model}) {full}", COLOR_CYAN)
                        send(L("\n\n[a IA inventou o resultado de uma ferramenta; dando uma bronca nela]", "\n\n[the AI made up a tool result; scolding it]") if invented_result(full) else L("\n\n[a IA disse que ia agir mas nao chamou nenhuma ferramenta; pedindo para ela continuar]", "\n\n[the AI said it would act but called no tool; asking it to continue]") if (agent and announces_action(full) and not looks_like_failed_call(full)) else L("\n\n[formato de ferramenta invalido, pedindo para a IA tentar de novo]", "\n\n[invalid tool format, asking the AI to try again]"))
                        messages.append({"role": "assistant", "content": full})
                        messages.append({"role": "user", "content": L(SCOLD_PT, SCOLD_EN) if invented_result(full) else L(NUDGE_PT, NUDGE_EN) if (agent and announces_action(full) and not looks_like_failed_call(full)) else L(CORRECTION_PT, CORRECTION_EN)})
                        status("Pensando")
                        continue
                    if use_tools and looks_like_failed_call(full): failed_pending = True   # sem tentativas de correcao sobrando
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
                    if use_tools and failed_pending:   # a IA pode ter escrito que "executou", mas nada rodou: avisa o usuario
                        log("AGENTE", "A IA nao conseguiu chamar a ferramenta no formato certo; nada foi executado.", COLOR_RED)
                        send(L("\n\n[Nenhuma ferramenta foi executada: a IA nao conseguiu chamar a ferramenta no formato correto. Se ela disse que executou algo, isso nao aconteceu. Modelos pequenos as vezes falham ao usar ferramentas: e so pedir de novo.]",
                               "\n\n[No tool was run: the AI could not call the tool in the correct format. If it said it ran something, that did not happen. Small models sometimes fail when using tools: just ask again.]"))
                    break
                # a IA pode pedir varias ferramentas de uma vez (chamadas em paralelo): roda ate 5, uma depois da outra, e devolve todos os resultados juntos
                calls = [call]; rest_from = call[2]
                while len(calls) < 5:
                    nxt = find_tool_call(full[rest_from:])
                    if not nxt: break
                    calls.append((nxt[0], nxt[1], rest_from + nxt[2])); rest_from = rest_from + nxt[2]
                failed_pending = False; corrections = 0; native_tries = 0   # cada passo ganha as suas tentativas
                full = full[:calls[-1][2]]; denied = False; results_txt = []; shot_imgs = []
                for tool_name, tool_args, _end in calls:
                    if lumemcp and tool_name not in TOOL_NAMES: tool_name = lumemcp.resolve(tool_name)
                    tool_args = normalize_args(tool_name, tool_args)
                    log("TOOL", f"{tool_name} {tool_args}", COLOR_CYAN)
                    if lumemcp and browser_chat and tool_name not in TOOL_NAMES: tool_name = lumemcp.resolve(tool_name)
                    _allowed = (("search_web", "read_url") if web_tool else ()) + (COMPUTER_TOOLS if comp_chat else ()) + (tuple(d["full"] for d in lumebrowser.defs()) if browser_chat else ())   # aba Chat: so o que ela liga (pesquisa, controle do computador e/ou o navegador)
                    web_denied = (web_tool or comp_chat or browser_chat) and tool_name not in _allowed
                    blocked = None; auto = False
                    comp = tool_name in COMPUTER_TOOLS
                    if comp and not (load_config().get("computer_control") and computer_supported()):
                        web_denied = True   # desligado nas opcoes: a ferramenta nao existe
                    elif comp and not agent and not comp_chat:
                        web_denied = True
                    is_mcp = str(tool_name).startswith("mcp__")
                    if is_mcp and ((not agent and not (browser_chat and str(tool_name).startswith("mcp__browser__"))) or not lumemcp or not lumemcp.find_tool(tool_name)): web_denied = True
                    if is_mcp and not web_denied:
                        _md = lumemcp.find_tool(tool_name)
                        if _md and time.time() < _mcp_grant.get(_md["server"], 0): auto = True   # o dono ja liberou este servidor (10 min, renova a cada uso)
                        if _md and load_config().get("mcp_auto_allow"):   # "aceitar sozinho" ligado no painel MCP: roda sem perguntar
                            auto = True; log("PERMISSAO", f"MCP permitido sozinho: {describe_tool(tool_name, tool_args)}", COLOR_YELLOW)
                    if needs_permission(tool_name) and not comp and not is_mcp and load_config().get("auto_allow"):   # "permitir sozinho": roda sem perguntar, exceto o que e perigoso (esse e bloqueado)
                        blocked = dangerous_reason(tool_name, tool_args); auto = not blocked
                        if blocked: log("PERMISSAO", f"Bloqueado ({blocked}): {describe_tool(tool_name, tool_args)}", COLOR_RED)
                        else: log("PERMISSAO", f"Permitido sozinho: {describe_tool(tool_name, tool_args)}", COLOR_YELLOW)
                    if comp and not web_denied and time.time() < _comp["grant"]: auto = True   # o dono ja liberou o controle nesta sessao (10 min, renova a cada uso)
                    if needs_permission(tool_name) and not auto and not blocked and not web_denied:
                        status("Aguardando permissão")
                        _desc = describe_tool(tool_name, tool_args)
                        if is_mcp: _desc = ("USAR O SEU NAVEGADOR (abas, paginas, cliques e digitacao, com os seus logins) por 10 minutos. Primeira acao: " if str(tool_name).startswith("mcp__browser__") else "USAR UM SERVIDOR MCP (programa externo) por 10 minutos. Primeira acao: ") + _desc
                        if comp: _desc = "CONTROLAR PROGRAMAS em segundo plano (mouse virtual, sem mexer no seu mouse) por 10 minutos. Primeira acao: " + _desc + ". Para parar tudo, mova o mouse para o canto superior esquerdo da tela."
                        if not ask_permission(_desc, stopped, (tool_name, tool_args)):
                            send(L("\n\n[Acao negada pelo usuario]", "\n\n[Action denied by the user]"))
                            denied = True; break
                    status("Pesquisando na web" if (web_tool and not comp_chat) else f"Executando: {tool_name}")
                    if web_denied and comp:
                        result = L("Erro: o controle do mouse e do teclado esta desligado nas opcoes do Code (ou este PC nao e Windows).", "Error: mouse and keyboard control is turned off in the Code options (or this PC is not Windows).")
                    elif web_denied:
                        result = L("Erro: essa ferramenta nao existe aqui.", "Error: that tool does not exist here.")
                    elif blocked:
                        result = L(f"Erro: comando BLOQUEADO por seguranca ({blocked}). O modo \"permitir sozinho\" nunca roda isso. Nao tente de novo: explique ao usuario ou use outra forma.", f"Error: command BLOCKED for safety ({blocked}). Auto-allow mode never runs this. Do not retry: explain it to the user or find another way.")
                    elif is_mcp:
                        _md = lumemcp.find_tool(tool_name)
                        if _md: _mcp_grant[_md["server"]] = time.time() + COMPUTER_GRANT_SECS
                        result, _mimgs = lumemcp.call_full(tool_name, tool_args)
                        if _mimgs: shot_imgs.extend(_mimgs)   # imagens devolvidas pela ferramenta voltam para a IA como imagens
                    elif comp:
                        _comp["grant"] = time.time() + COMPUTER_GRANT_SECS
                        result, _img = computer_execute(tool_name, tool_args, stopped)
                        if _img: shot_imgs.extend(_img if isinstance(_img, list) else [_img])
                        _nt = vcomp.pop_note() if vcomp else {}
                        if _nt.get("pt"): send(L("\n\n[" + _nt["pt"] + "]\n\n", "\n\n[" + _nt["en"] + "]\n\n"))   # aviso leve: "A IA tentou X, mas so achou Y; tirando print de Y..."
                    elif tool_name == "search_web":   # emite as fontes para a interface mostrar os cartoes
                        results, src = search_web_results(tool_args.get("query", ""), n=tool_args.get("results") or tool_args.get("num_results") or tool_args.get("max_results"))
                        result = format_search(results, src) if results else SEARCH_UNAVAILABLE
                        if results: emit({"sources": [{"title": t, "url": u} for t, _, u in results], "provider": src, "query": tool_args.get("query", "")})
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
                    if verbose or result.startswith("Erro") or result.startswith("Error"): log("TOOL · RESULTADO", result, COLOR_RED if result.startswith(("Erro", "Error")) else COLOR_GRAY)
                    send(L(f"\n\n[resultado de {tool_name}]\n{result}\n[/resultado]\n\n", f"\n\n[result of {tool_name}]\n{result}\n[/result]\n\n"))
                    results_txt.append((tool_name, result))
                if denied and not results_txt: break
                tool_name = calls[0][0]
                joined = "\n\n".join((f"[{n}]\n{r}" if len(calls) > 1 else r) for n, r in results_txt)
                pair = [{"role": "assistant", "content": full},
                        {"role": "user", "content": L(f"Resultado da ferramenta {tool_name}:\n{joined}", f"Tool result for {tool_name}:\n{joined}") if len(calls) == 1 else L(f"Resultados das ferramentas:\n{joined}", f"Tool results:\n{joined}")}]
                if shot_imgs: pair[1]["images"] = shot_imgs[-3:]   # a captura de tela volta como imagem na mesma mensagem do resultado
                messages.extend(pair); clean.extend(pair)
                if denied: break
                status("Pensando")
            else:
                if use_tools:
                    send(L(f"\n\n[Limite de {max_steps} chamadas de ferramenta atingido]", f"\n\n[Limit of {max_steps} tool calls reached]"))
                    log("AGENTE", "Limite de passos atingido", COLOR_YELLOW)

            if model.startswith("groq"):
                cfg = load_config()
                cfg["usage"]["groq"] += total_chars
                save_config(cfg)
            record_event({"type": "chat", **({"user": gid} if gid else {}), "model": model, "cloud": model.startswith(CLOUD_PREFIXES), "tab": "code" if agent else "chat",
                          "tokens": req_tokens or total_chars // 4, "seconds": req_seconds or (time.time() - started), "prompt_tokens": req_prompt, "chars": total_chars,
                          **({"pollen": round(pol_cost(model, req_prompt, req_tokens or total_chars // 4), 8)} if model.startswith("pol:") else {})})
            if model.startswith("cf:") and not gid:
                try: cf_add_neurons(model[3:], req_prompt, req_tokens or total_chars // 4)
                except Exception: pass
            u = model_usage.setdefault(model, {"uses": 0, "chars": 0})
            u["uses"] += 1; u["chars"] += total_chars; u["last_used"] = time.time()
            log("CHAT", f"concluido: {total_chars} caracteres em {time.time() - started:.1f}s", COLOR_GREEN)
        except Exception as e:
            log("ERRO", f"{type(e).__name__}: {e}", COLOR_RED)
            try: log("ERRO · DETALHES", traceback.format_exc(), COLOR_RED)
            except Exception: pass
            try: send(L(f"\n[Erro: {localize_error(e, lang)}]", f"\n[Error: {localize_error(e, lang)}]"))
            except Exception: pass
        finally:
            if gid:
                with guest_lock: guest_active[gid] = max(0, guest_active.get(gid, 1) - 1)
            else: gens_active.pop(rid, None); req_stops.pop(rid, None)

def start_server():
    global httpd, _health_started
    use_account(load_config().get("active_account") or "")
    if not _health_started:   # teste de saude dos modelos novos (Aichixia, AIHubMix, LiteRouter) a cada 10 minutos
        _health_started = True; _health_load(); threading.Thread(target=health_loop, daemon=True).start()
    handler = functools.partial(AppHandler, directory=RES_DIR)
    host = "0.0.0.0" if load_config().get("remote_enabled") and not OWNER_ONLY else "127.0.0.1"
    srv = None
    tries = 60 if HANDOFF else 8   # no reinicio sem sumir o app antigo ainda segura a porta ate o novo avisar que esta pronto
    for attempt in range(tries):   # na troca de modo o socket antigo pode demorar um instante para liberar a porta
        try:
            srv = ThreadingServer((host, PORT), handler); break
        except OSError as e:
            if attempt == tries - 1:
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
    """Converte icons/lume.png em .ico (o Windows aceita PNG dentro do .ico) para o icone da janela. None se nao houver."""
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
        log("ICONE", f"Nao consegui usar icons/lume.png: {e}", COLOR_YELLOW); return None

# ---------------- atualizar os modelos instalados (ollama pull) ----------------
model_update_state = {"running": False, "current": "", "done": 0, "total": 0, "updated": [], "error": ""}

def update_all_models():
    """Roda o pull em cada modelo local instalado: se nada mudou so confere o manifesto (rapido); se saiu versao nova, baixa."""
    if model_update_state["running"]: return
    tags = ollama_tags()
    if tags is None: model_update_state.update(error="O Ollama nao esta rodando."); return
    names = [m["name"] for m in tags if not m["name"].endswith("cloud")]
    model_update_state.update(running=True, current="", done=0, total=len(names), updated=[], error="")
    log("MODELO", f"Conferindo atualizacoes de {len(names)} modelo(s)...", COLOR_CYAN)
    try:
        for n in names:
            model_update_state["current"] = n; downloaded = False
            try:
                req = urllib.request.Request(f"{OLLAMA_URL}/api/pull", data=json.dumps({"model": n, "stream": True}).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    for line in r:
                        try: d = json.loads(line)
                        except ValueError: continue
                        if d.get("error"): raise Exception(d["error"])
                        if d.get("total") and (d.get("completed") or 0) < d["total"]: downloaded = True
                if downloaded: model_update_state["updated"].append(n); log("MODELO", f"{n} atualizado.", COLOR_GREEN)
            except Exception as e:
                model_update_state["error"] = f"{n}: {e}"; log("MODELO", f"Nao consegui atualizar {n}: {e}", COLOR_YELLOW)
            model_update_state["done"] += 1
        _model_info_cache.clear()
        cfg = load_config(); cfg["models_updated_at"] = time.time(); save_config(cfg)
    finally:
        model_update_state.update(running=False, current="")

def model_updater_loop():
    time.sleep(120)
    while True:
        try:
            cfg = load_config()
            if cfg.get("auto_update_models") and time.time() - cfg.get("models_updated_at", 0) > 7 * 86400 and not gens_active: update_all_models()
        except Exception as e:
            log("MODELO", f"Atualizador de modelos: {e}", COLOR_YELLOW)
        time.sleep(3600)

# ---------------- atualizacoes (GitHub) ----------------
DEFAULT_REPO = "marioondc9426/Lume"
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

def parse_ver(v):
    n = [int(x) for x in re.findall(r"\d+", v or "")][:4]; return tuple(n + [0] * (3 - len(n)))   # "1.7.03" -> (1, 7, 3)

def check_release():
    """Versao do .exe: compara com a ultima Release do GitHub (o CI sobe o Lume.exe em cada tag v*)."""
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{DEFAULT_REPO}/releases/latest", headers={"Accept": "application/vnd.github+json", "User-Agent": "lume-updater"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r: d = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404: return {"status": "unknown", "local": VERSION, "local_date": "exe", "version": VERSION}
            raise
        remote = str(d.get("tag_name", "")).lstrip("vV"); asset = next((a for a in d.get("assets", []) if a["name"].lower().endswith(".exe")), None)
        urgent = bool(re.search(r"\[(urgente|urgent|emerg[eê]ncia|emergency|security|seguran[cç]a)\]", str(d.get("name") or "") + " " + str(d.get("body") or ""), re.I))   # patch de seguranca: sem "depois"
        newer = parse_ver(remote) > parse_ver(VERSION)
        return {"status": "available" if (newer and asset) else "uptodate" if parse_ver(remote) == parse_ver(VERSION) else "ahead" if not newer else "unknown",
                "local": VERSION, "local_date": "exe", "version": VERSION, "remote_version": remote, "behind_by": 1 if newer else 0, "urgent": bool(urgent and newer),
                "commits": [{"sha": "v" + remote, "msg": (d.get("name") or ("v" + remote))}] if newer else [], "asset": ({"url": asset["browser_download_url"], "size": asset.get("size", 0), "digest": asset.get("digest", "")} if asset else None)}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}

pending_update = {"new": "", "cmd": ""}

def apply_release():
    """Baixa o Lume.exe novo da Release e prepara a troca; o reinicio (restart_app) faz a troca com o app fechado."""
    if not update_lock.acquire(blocking=False): return {"ok": False, "error": "busy"}
    try:
        info = check_release()
        if info.get("status") != "available" or not info.get("asset"): return {"ok": False, "error": "pull", "detail": "Nao ha versao nova para baixar."}
        a = info["asset"]; new = os.path.join(tempfile.gettempdir(), "Lume-update.exe"); h = hashlib.sha256()
        with urllib.request.urlopen(urllib.request.Request(a["url"], headers={"User-Agent": "lume-updater"}), timeout=60) as r, open(new, "wb") as f:
            for chunk in iter(lambda: r.read(1 << 20), b""): f.write(chunk); h.update(chunk)
        if a.get("size") and os.path.getsize(new) != a["size"]: os.remove(new); return {"ok": False, "error": "pull", "detail": "O download veio incompleto."}
        if a.get("digest", "").startswith("sha256:") and a["digest"][7:].lower() != h.hexdigest().lower(): os.remove(new); return {"ok": False, "error": "pull", "detail": "O arquivo baixado nao confere com o GitHub (sha256)."}
        cmd = os.path.join(tempfile.gettempdir(), "lume-update.cmd"); exe = sys.executable
        with open(cmd, "w", encoding="utf-8") as f:
            f.write(f'@echo off\r\nping -n 4 127.0.0.1 >nul\r\nset n=0\r\n:retry\r\nmove /y "{new}" "{exe}" >nul 2>&1\r\nif errorlevel 1 (\r\n  set /a n+=1\r\n  if %n% GEQ 20 goto fim\r\n  ping -n 2 127.0.0.1 >nul\r\n  goto retry\r\n)\r\n:fim\r\nstart "" "{exe}"\r\n')
        pending_update.update(new=new, cmd=cmd); log("UPDATE", f"Versao {info['remote_version']} baixada; a troca acontece ao reiniciar.", COLOR_GREEN)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": "pull", "detail": str(e)[:300]}
    finally:
        update_lock.release()

def check_update():
    """Compara a versao deste PC com o main do GitHub. status: uptodate | available | ahead | diverged | unknown | error."""
    if FROZEN: return check_release()
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
    if FROZEN: return apply_release()
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
            try: subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", req], cwd=BASE_DIR, timeout=300, creationflags=NOWIN)   # (so no modo fonte)
            except Exception as e: log("UPDATE", f"pip falhou (ignorado): {e}", COLOR_YELLOW)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": "pull", "detail": str(e)[:300]}
    finally:
        update_lock.release()

window_api = None

def default_browser():
    """(nome, exe, familia) do navegador padrao do Windows para links https; None se nao achar."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice") as k: progid = winreg.QueryValueEx(k, "ProgId")[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, progid + r"\shell\open\command") as k: cmd = winreg.QueryValueEx(k, "")[0]
        m = re.match(r'\s*"([^"]+)"', cmd) or re.match(r'\s*(\S+)', cmd); exe = m.group(1)
        if not os.path.isfile(exe): return None
        import vcomp
        info = vcomp.BROWSERS.get(os.path.basename(exe).lower())
        return (info[0] if info else os.path.splitext(os.path.basename(exe))[0], exe, info[1] if info else "chromium")
    except Exception: return None

def installed_browsers():
    """Navegadores instalados (registro do Windows, StartMenuInternet): [{name, exe, family, default}]. O padrao vem primeiro."""
    out, seen = [], set()
    try:
        import winreg, vcomp
        dflt = default_browser(); dexe = (dflt[1].lower() if dflt else "")
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try: base = winreg.OpenKey(root, r"SOFTWARE\Clients\StartMenuInternet")
            except OSError: continue
            for i in range(winreg.QueryInfoKey(base)[0]):
                try:
                    sub = winreg.EnumKey(base, i)
                    with winreg.OpenKey(base, sub + r"\shell\open\command") as k: cmd = winreg.QueryValueEx(k, "")[0]
                    m = re.match(r'\s*"([^"]+)"', cmd) or re.match(r'\s*(\S+)', cmd); exe = m.group(1)
                    if not os.path.isfile(exe) or exe.lower() in seen or "iexplore" in exe.lower(): continue
                    seen.add(exe.lower()); info = vcomp.BROWSERS.get(os.path.basename(exe).lower())
                    out.append({"name": info[0] if info else os.path.splitext(os.path.basename(exe))[0], "exe": exe, "family": info[1] if info else "chromium", "default": exe.lower() == dexe})
                except OSError: continue
        if dflt and dflt[1].lower() not in seen: out.append({"name": dflt[0], "exe": dflt[1], "family": dflt[2], "default": True})
    except Exception: pass
    return sorted(out, key=lambda b: (not b["default"], b["name"].lower()))

def browser_install(exe_choice=None):
    """Botao "Instalar no meu navegador": abre a pagina de extensoes do navegador PADRAO e a pasta da extensao.
    Nenhum navegador deixa instalar uma extensao de fora sem um clique do dono (e o Comet/Chrome so aceitam --load-extension com o navegador fechado), entao o que da para automatizar e isso + o passo a passo."""
    if sys.platform != "win32": return {"error": "So no Windows por enquanto."}
    ext = os.path.join(RES_DIR, "browser-extension")
    if not os.path.isdir(ext): return {"error": "A pasta browser-extension nao foi encontrada."}
    d = default_browser()
    if exe_choice:   # o dono escolheu outro navegador na lista (so vale um que esta instalado)
        ch = next((b for b in installed_browsers() if b["exe"].lower() == str(exe_choice).lower()), None)
        if ch: d = (ch["name"], ch["exe"], ch["family"])
    try: os.startfile(ext)   # a pasta no Explorador (para arrastar para a pagina de extensoes)
    except Exception: pass
    if not d: return {"browser": "", "steps": ["Nao achei o seu navegador padrao. Abra a pagina de extensoes dele (chrome://extensions), ligue o Modo do desenvolvedor e use Carregar sem compactacao com a pasta que abri."]}
    name, exe, fam = d; flags = getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        import vcomp
        running = any(w["exe"].lower() == os.path.basename(exe).lower() for w in vcomp.windows_info())
        if fam == "gecko":
            subprocess.Popen([exe, "about:debugging#/runtime/this-firefox"], creationflags=flags)
            steps = [f"Abri o {name} na pagina 'Este Firefox'.", "Clique em 'Carregar extensao temporaria...' e escolha o arquivo manifest.json da pasta que abri (no Firefox ela some quando ele fecha)."]
        else:
            subprocess.Popen([exe] + ([] if running else ["--load-extension=" + ext]) + ["chrome://extensions"], creationflags=flags)
            steps = [f"Abri a pagina de extensoes do {name}." + ("" if running else " Como ele estava fechado, tentei ja abrir com a extensao carregada: se 'Lume - IA no navegador' aparecer na lista, acabou."),
                     "Ligue o 'Modo do desenvolvedor' (canto da pagina).", "Arraste a pasta browser-extension (abri no Explorador) para a pagina, ou clique em 'Carregar sem compactacao' e escolha a pasta.",
                     "Deixe o Lume aberto: o icone da extensao mostra ON e o status aqui muda para Conectada."]
        return {"browser": name, "steps": steps}
    except Exception as e: return {"browser": name, "error": f"Nao consegui abrir o {name}: {e}"}

UPDATED_AT = time.time() if "--updated" in sys.argv else 0.0   # este processo nasceu de uma atualizacao automatica (a interface mostra "Lume atualizado")
HANDOFF = "--handoff" in sys.argv   # este processo e o app NOVO de um reinicio: espera o antigo liberar a porta e abre a janela no mesmo lugar
def _hf(name): return os.path.join(tempfile.gettempdir(), "lume-handoff-" + name)
def _my_hwnd(title):
    """A janela com esse titulo que pertence a ESTE processo (outra copia do Lume aberta nao atrapalha)."""
    u = ctypes.windll.user32; found = []; pid = os.getpid()
    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        p = wintypes.DWORD(); u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
            if b.value == title: found.append(h)
        return True
    u.EnumWindows(cb, 0); return found[0] if found else 0
def window_geometry():
    """Onde esta a janela principal (pixels) e se esta maximizada (o maximizar do Lume e proprio: guarda o tamanho de antes em window_api._restore)."""
    try:
        u = ctypes.windll.user32; hw = _my_hwnd(WINDOW_TITLE)
        if not hw: return None
        r = wintypes.RECT(); u.GetWindowRect(hw, ctypes.byref(r)); x, y, w, h = r.left, r.top, r.right - r.left, r.bottom - r.top
        mx = bool(window_api and getattr(window_api, "_maximized", False))
        if mx and getattr(window_api, "_restore", None): x, y, w, h = window_api._restore
        try: k = u.GetDpiForWindow(hw) / 96.0
        except Exception: k = 1.0
        return {"x": int(x), "y": int(y), "w": round(w / k), "h": round(h / k), "px": [int(x), int(y), int(w), int(h)], "max": mx}
    except Exception: return None
def handoff_geometry():
    """A posicao gravada pelo app antigo (vale por 90 s)."""
    try:
        if time.time() - os.path.getmtime(_hf("geom.json")) > 90: return None
        with open(_hf("geom.json"), "r", encoding="utf-8") as f: g = json.load(f).get("geom")
        return g if isinstance(g, dict) and g.get("w", 0) >= 300 and g.get("h", 0) >= 300 else None
    except Exception: return None
def _handoff_wait():
    """App ANTIGO: quando o novo avisa que esta pronto, solta as portas (a janela fica, com o aviso) e so fecha quando a janela nova ja apareceu. Se o novo nao vier, volta ao normal."""
    t0 = time.time()
    while time.time() - t0 < 45 and not os.path.exists(_hf("ready")): time.sleep(0.2)
    if not os.path.exists(_hf("ready")): log("ATUALIZACAO", "O app novo nao abriu a tempo; continuo neste.", COLOR_RED); _handoff_cancel(); return
    for s in (https_httpd, httpd):
        try:
            if s: s.shutdown()
        except Exception: pass
    t1 = time.time()
    while time.time() - t1 < 40 and not os.path.exists(_hf("shown")): time.sleep(0.2)
    if os.path.exists(_hf("shown")):
        try: set_terminal(False)   # .exe com "iniciar com o terminal": fecha o terminal do app antigo (o novo abriu o dele)
        except Exception: pass
        os._exit(0)   # sem shutdown_all: ele fecharia o Ollama que o app novo ja esta usando
    log("ATUALIZACAO", "A janela nova nao apareceu; religando este app.", COLOR_RED)
    threading.Thread(target=start_server, daemon=True).start(); time.sleep(1.5); _handoff_cancel()
def _handoff_cancel():
    try: window_api._window.evaluate_js("(document.getElementById('lume-restart')||{remove(){}}).remove(); location.reload()")
    except Exception: pass

def restart_app(notify=False):
    """Reinicia o Lume sem a janela sumir: abre o app novo por tras, no mesmo lugar, e so entao fecha este. notify: mostra o aviso na tela (atualizacao)."""
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if not FROZEN: flags = 0   # rodando do codigo (run.bat): o app novo herda ESTE terminal, entao o log continua na mesma janela e ela fecha junto com o app novo (antes o terminal antigo ficava parado)
    if notify:
        try:
            if window_api and window_api._window: window_api._window.evaluate_js("window.lumeRestarting && lumeRestarting()"); time.sleep(0.9)   # um instante para a tela de aviso aparecer
        except Exception: pass
    for n in ("ready", "shown"):
        try: os.remove(_hf(n))
        except OSError: pass
    try:
        with open(_hf("geom.json"), "w", encoding="utf-8") as f: json.dump({"geom": window_geometry()}, f)
    except OSError: pass
    swap = FROZEN and pending_update["cmd"]   # a troca do .exe precisa do arquivo livre: ai este app fecha antes e o novo abre no mesmo lugar logo depois
    if swap: subprocess.Popen(["cmd", "/c", pending_update["cmd"]], creationflags=flags)
    else:
        args = ([sys.executable] if FROZEN else [sys.executable, "app.py"]) + ["--handoff"] + (["--updated"] if notify else [])
        subprocess.Popen(args, cwd=BASE_DIR, creationflags=flags)
        threading.Thread(target=_handoff_wait, daemon=True).start(); return
    if window_api and window_api._window: window_api._window.destroy()

# ---------------------------------------------------------------- atualizar sozinho quando os arquivos do programa mudam (so rodando do codigo-fonte, nao no .exe)
DEV_PY = ("app.py", "lumemcp.py", "lumebrowser.py", "vcomp.py", "tls.py", "guests.py")
def _dev_files():
    py = [os.path.join(RES_DIR, f) for f in DEV_PY if os.path.isfile(os.path.join(RES_DIR, f))]
    ui = [os.path.join(RES_DIR, "index.html")] + [os.path.join(RES_DIR, "libs", f) for f in (os.listdir(os.path.join(RES_DIR, "libs")) if os.path.isdir(os.path.join(RES_DIR, "libs")) else []) if f.endswith((".js", ".css"))]
    return py, [f for f in ui if os.path.isfile(f)]
def _sig(files):
    out = []
    for f in files:
        try: st_ = os.stat(f); out.append((f, st_.st_mtime_ns, st_.st_size))
        except OSError: pass
    return out
def dev_enabled(): return (not FROZEN) and bool(load_config().get("auto_reload", True))
_ui_rev = {"rev": "", "since": 0.0}
def ui_rev():
    """Identifica a versao da interface (index.html + libs): muda quando um desses arquivos muda."""
    return hashlib.md5(repr(_sig(_dev_files()[1])).encode()).hexdigest()[:12]
DEV_PENDING = {"on": False}   # um .py mudou e esta pronto: a interface mostra "Atualizar agora / Deixar para depois"
def dev_watch_loop(poll=2.0, stable=2.5, restart=None):
    """Se um arquivo .py mudar (e compilar), reinicia o Lume quando nao houver resposta em andamento nem permissao pendente."""
    restart = restart or None; py0 = _sig(_dev_files()[0]); changed_at = 0.0; last = py0
    while True:
        time.sleep(poll)
        try:
            if not dev_enabled(): py0 = last = _sig(_dev_files()[0]); changed_at = 0.0; continue
            cur = _sig(_dev_files()[0])
            if cur != last: last = cur; changed_at = time.time()   # ainda mexendo: espera ficar parado
            if cur == py0 or not changed_at or time.time() - changed_at < stable: continue
            import py_compile
            old = set(py0); bad = [f for (f, m, sz) in cur if (f, m, sz) not in old and not _compiles(f, py_compile)]
            if bad:
                log("ATUALIZACAO", "Arquivo com erro de sintaxe, nao reiniciei: " + ", ".join(os.path.basename(b) for b in bad), COLOR_RED); py0 = cur; changed_at = 0.0; continue
            if gens_active or pending_command.get("resolve"): continue   # o dono esta conversando ou ha uma permissao esperando: tenta de novo daqui a pouco
            if restart is not None: log("ATUALIZACAO", "Arquivos do programa mudaram: reiniciando o Lume.", COLOR_YELLOW); restart(); return
            DEV_PENDING["on"] = True; log("ATUALIZACAO", "Arquivos do programa mudaram: a interface pergunta se reinicia agora ou depois.", COLOR_YELLOW); return
        except Exception as e:
            log("ATUALIZACAO", f"Vigia de arquivos: {e}", COLOR_RED)
def _compiles(path, py_compile):
    try:   # so confere a sintaxe, em memoria (nao grava .pyc)
        with open(path, "rb") as f: compile(f.read(), path, "exec")
        return True
    except Exception as e: log("ATUALIZACAO", f"{os.path.basename(path)}: {str(e)[:200]}", COLOR_RED); return False

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

# ---------------------------------------------------------------- opcoes do .exe: terminal com o log e iniciar com o Windows
terminal_proc = None

def terminal_is_open():
    return bool(terminal_proc and terminal_proc.poll() is None)

def set_terminal(on):
    """Abre/fecha uma janela de terminal que acompanha o log (lume.log) ao vivo. E uma janela a parte: fechar o terminal nao fecha o app. So no .exe (pelo run.bat o terminal ja existe)."""
    global terminal_proc
    if os.name != "nt" or not FROZEN: return False
    if on and not terminal_is_open():
        lp = os.path.join(BASE_DIR, "lume.log").replace("'", "''")
        script = f"$Host.UI.RawUI.WindowTitle = '{APP_NAME} - log'; Get-Content -LiteralPath '{lp}' -Tail 200 -Wait -Encoding UTF8"
        try: terminal_proc = subprocess.Popen(["powershell.exe", "-NoProfile", "-NoExit", "-Command", script], creationflags=0x00000010)   # CREATE_NEW_CONSOLE
        except OSError as e:
            log("TERMINAL", f"Nao consegui abrir o terminal: {e}", COLOR_RED); return False
        log("TERMINAL", "Terminal do log aberto (pode fechar a janela sem fechar o app).", COLOR_CYAN)
    elif not on and terminal_is_open():
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(terminal_proc.pid)], capture_output=True, creationflags=NOWIN); terminal_proc = None
    return True

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def autostart_get():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k: return bool(winreg.QueryValueEx(k, APP_NAME)[0])
    except Exception: return False

def autostart_set(on):
    """Iniciar com o Windows: um valor na chave Run do usuario (nao precisa de administrador). So vale para o .exe."""
    if not FROZEN: return False
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        try: winreg.DeleteValue(k, "Qwen")   # entrada do nome antigo do app
        except FileNotFoundError: pass
        if on: winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{sys.executable}" --autostart')
        else:
            try: winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError: pass
    return True

def tray_available():
    try: import pystray, PIL; return True
    except Exception: return False

# ---------------------------------------------------------------- aceleracao por hardware (a janela do app usa a placa de video)
HW_MODES = ("auto", "on", "off")
HW_FLAGS_ON = "--ignore-gpu-blocklist --enable-gpu-rasterization --enable-zero-copy"   # forca a GPU mesmo que o Chromium ache o driver "ruim"
HW_FLAGS_OFF = "--disable-gpu"
_gpu_names_cache = None
def gpu_names():
    """Nomes das placas de video (Windows: WMI; Linux: lspci). Lista vazia se nao deu para saber."""
    global _gpu_names_cache
    if _gpu_names_cache is not None: return _gpu_names_cache
    names = []; cache_f = os.path.join(BASE_DIR, "gpu_cache.json")
    try:   # o PowerShell leva ~2 s a cada abertura: guarda o resultado por 7 dias (a placa quase nunca muda)
        with open(cache_f, "r", encoding="utf-8") as f: c = json.load(f)
        if time.time() - float(c.get("t", 0)) < 7 * 86400 and isinstance(c.get("names"), list) and c["names"]: _gpu_names_cache = c["names"]; return _gpu_names_cache
    except Exception: pass
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"], stderr=subprocess.DEVNULL, timeout=8, creationflags=NO_WINDOW).decode("utf-8", "replace")
            names = [l.strip() for l in out.splitlines() if l.strip()]
        elif sys.platform.startswith("linux"):
            out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", "replace")
            names = [l.split(": ", 1)[-1].strip() for l in out.splitlines() if re.search(r"VGA|3D controller|Display controller", l)]
    except Exception: pass
    _gpu_names_cache = names
    if names:
        try:
            with open(cache_f, "w", encoding="utf-8") as f: json.dump({"t": time.time(), "names": names}, f)
        except OSError: pass
    return names

def hw_accel_decide(mode, names=None):
    """Retorna 'on' | 'off' | 'default' (o que vai valer). No automatico: placa NVIDIA/AMD/Intel Arc liga a forca total; so adaptador basico/virtual desliga; o resto (Intel integrado) deixa o Chromium decidir."""
    if mode in ("on", "off"): return mode
    names = gpu_names() if names is None else names
    if not names: return "default"
    real = [n for n in names if not re.search(r"basic|hyper-v|vmware|virtualbox|virtio|qxl|remote|parsec|indirect|citrix|\bsvga\b", n, re.I)]
    if not real: return "off"
    if any(re.search(r"nvidia|geforce|quadro|rtx|radeon|\bamd\b|\barc\b", n, re.I) for n in real): return "on"
    return "default"

def hw_accel_apply():
    """Poe as opcoes do navegador embutido (WebView2 / Qt WebEngine) a partir da configuracao. Precisa rodar antes da janela abrir."""
    mode = load_config().get("hw_accel", "auto")
    if mode not in HW_MODES: mode = "auto"
    eff = hw_accel_decide(mode)
    flags = HW_FLAGS_ON if eff == "on" else HW_FLAGS_OFF if eff == "off" else ""
    if flags:
        if sys.platform == "win32":
            cur = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
            os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (cur + " " + flags).strip()
        elif sys.platform.startswith("linux") and not (FROZEN and not _env("GPU")):   # o binario empacotado do Linux ja roda sem GPU de proposito (ver o topo do arquivo)
            cur = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (cur + " " + flags).strip()
    log("INICIO", f"Aceleracao de hardware: {mode} -> {eff}" + (f" ({', '.join(gpu_names())})" if gpu_names() else ""), COLOR_BLUE)
    return eff

def app_options():
    cfg = load_config()
    _hw = cfg.get("hw_accel", "auto"); _hw = _hw if _hw in HW_MODES else "auto"
    return {"frozen": FROZEN, "start_with_terminal": bool(cfg.get("start_with_terminal")), "terminal_open": terminal_is_open(), "start_with_windows": autostart_get(), "remote_enabled": bool(cfg.get("remote_enabled")),
            "tray": bool(cfg.get("tray_enabled")), "tray_available": tray_available(), "auto_update_models": bool(cfg.get("auto_update_models")), "log_full": bool(cfg.get("log_full")), "quick_hotkey": bool(cfg.get("quick_hotkey", True)), "pet_desktop": bool(cfg.get("pet_desktop", False)), "pet_size": int(cfg.get("pet_size", 200)), "pet_snap": bool(cfg.get("pet_snap", True)), "pet_available": sys.platform == "win32", "quick_sel_hotkey": bool(cfg.get("quick_sel_hotkey", True)), "browser_ai": bool(cfg.get("browser_ai", True)), "browser_ext": (lumebrowser.info() if lumebrowser else {}), "browser_ext_dir": os.path.join(RES_DIR, "browser-extension"), "quick_style": cfg.get("quick_style", "mica"), "quick_available": sys.platform == "win32",
            "hw_accel": _hw, "hw_accel_auto": hw_accel_decide("auto"), "gpu_names": gpu_names(), "auto_reload": bool(cfg.get("auto_reload", True)), "dev": not FROZEN,
            "version": VERSION, "platform": platform.platform(), "python": sys.version.split()[0], "data_dir": BASE_DIR, "has_log": os.path.exists(os.path.join(BASE_DIR, "lume.log")),
            "models_updated_at": cfg.get("models_updated_at", 0), "model_update": dict(model_update_state)}

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
        req = urllib.request.Request(CLOUDFLARED_URL, headers={"User-Agent": "lume-app"})
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

def find_tailscale():
    return shutil.which("tailscale") or next((p for p in (os.path.join(os.environ.get("ProgramFiles", ""), "Tailscale", "tailscale.exe"), os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Tailscale", "tailscale.exe")) if os.path.isfile(p)), None)

def ts_run(*args, timeout=25):
    r = subprocess.run([find_tailscale(), *args], capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", creationflags=NOWIN)
    return r.returncode, r.stdout or "", r.stderr or ""

_ts_cache = {"t": 0, "v": None}
def tailscale_status():
    """{installed, state (Running | NeedsLogin | Stopped...), name}. Em cache por alguns segundos (a tela consulta de tempos em tempos)."""
    if _ts_cache["v"] is not None and time.time() - _ts_cache["t"] < 8: return _ts_cache["v"]
    if not find_tailscale(): v = {"installed": False}
    else:
        try:
            code, out, _ = ts_run("status", "--json", timeout=8); d = json.loads(out)
            v = {"installed": True, "state": d.get("BackendState", ""), "name": ((d.get("Self") or {}).get("DNSName") or "").rstrip(".")}
        except Exception as e:
            v = {"installed": True, "state": "", "name": "", "error": str(e)[:120]}
    _ts_cache.update(t=time.time(), v=v); return v

def start_tailscale():
    """Publica o app na internet pelo Tailscale Funnel (endereco https://PC.rede.ts.net fixo, sem abrir porta no roteador). Entra na senha do app como qualquer acesso de fora."""
    if not find_tailscale(): return {"ok": False, "error": "O Tailscale nao esta instalado."}
    _ts_cache["v"] = None; st = tailscale_status()
    if st.get("state") != "Running": return {"ok": False, "error": f"O Tailscale nao esta conectado (estado: {st.get('state') or 'desconhecido'}). Abra o Tailscale e entre na sua conta."}
    stop_tunnel(); out = err = ""
    try:
        code, out, err = ts_run("funnel", "--bg", str(PORT), timeout=30)
    except subprocess.TimeoutExpired as e:   # sem o Funnel ligado na conta o comando fica esperando voce ligar pelo site
        out, err = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        code = 1
    text = out + "\n" + err
    link = re.search(r"https://login\.tailscale\.com/\S+", text)
    url = re.search(r"https://[\w.\-]+\.ts\.net", text)
    if code != 0 or not url:
        msg = "O Funnel nao esta ligado na sua conta do Tailscale. Abra " + link.group(0) + " e ative." if link else (text.strip()[-300:] or "Nao consegui ligar o Funnel.")
        try: ts_run("funnel", "reset", timeout=15)
        except Exception: pass
        tunnel_state.update(running=False, url="", error=msg, tool="tailscale"); return {"ok": False, "error": msg, "link": link.group(0) if link else ""}
    tunnel_state.update(running=True, url=url.group(0), error="", tool="tailscale"); log("TUNEL", f"Tailscale Funnel: {url.group(0)}", COLOR_YELLOW)
    return {"ok": True, "url": url.group(0)}

def stop_tunnel():
    global _tunnel_proc
    if tunnel_state.get("tool") == "tailscale" and tunnel_state.get("running"):
        try: ts_run("funnel", "reset", timeout=15); log("TUNEL", "Tailscale Funnel desligado.", COLOR_YELLOW)
        except Exception as e: log("TUNEL", f"Nao consegui desligar o Funnel: {e}", COLOR_RED)
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

tray_icon = None

def tray_start():
    """Icone ao lado do relogio: clique abre a janela; o botao de fechar da janela so a esconde (o app continua rodando)."""
    global tray_icon
    if tray_icon: return True
    try:
        import pystray
        from PIL import Image
        img = Image.open(CUSTOM_ICON).convert("RGBA") if os.path.isfile(CUSTOM_ICON) else Image.new("RGBA", (64, 64), (90, 120, 255, 255))
        menu = pystray.Menu(pystray.MenuItem("Abrir " + APP_NAME, lambda icon, item: tray_show(), default=True), pystray.MenuItem("Sair", lambda icon, item: tray_quit()))
        tray_icon = pystray.Icon(APP_NAME, img, APP_NAME, menu); tray_icon.run_detached()
        log("BANDEJA", "Icone da bandeja ligado.", COLOR_GREEN); return True
    except Exception as e:
        log("BANDEJA", f"Nao consegui ligar a bandeja: {e}", COLOR_YELLOW); tray_icon = None; return False

def tray_stop():
    global tray_icon
    if tray_icon:
        try: tray_icon.stop()
        except Exception: pass
        tray_icon = None

def tray_show():
    try: window_api._window.show(); window_api._window.restore()
    except Exception as e: log("BANDEJA", f"Nao consegui mostrar a janela: {e}", COLOR_YELLOW)

def quit_app():
    """Fechar de verdade. O pet e a caixinha (Alt+Espaco) sao janelas escondidas e o pywebview so termina quando TODAS fecham: destruir so a principal fazia a interface sumir e o programa (e o terminal) continuar vivo. Aqui fecha todas e, se mesmo assim o processo nao sair, forca depois de 8 s."""
    tray_stop()
    def _force():
        time.sleep(8)
        try: shutdown_all()
        except Exception: pass
        os._exit(0)
    threading.Thread(target=_force, daemon=True).start()
    main = window_api._window if window_api else None
    for w in list(webview.windows):
        if w is not main:
            try: w.destroy()
            except Exception: pass
    try:
        if main: main.destroy()
    except Exception: pass

def tray_quit(): quit_app()

class WindowApi:
    def open_feedback(self):
        """Janela SEPARADA de feedback (fica por cima, nao bloqueia o app): da para testar o Lume e anotar ao mesmo tempo. Se ja esta aberta, so traz para a frente."""
        if sys.platform.startswith("linux"):   # no Qt (Linux) uma 2a janela no MESMO processo trava a interface (CPU em 100%); la ela abre como um processo separado do Lume
            try:
                pr = getattr(self, "_fb_proc", None)
                if pr is not None and pr.poll() is None: return True   # ja esta aberta
                args = ([sys.executable] if FROZEN else [sys.executable, os.path.abspath(__file__)]) + ["--feedback-window", str(PORT), VERSION]
                self._fb_proc = subprocess.Popen(args, env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return True
            except Exception as e:
                log("FEEDBACK", f"Nao consegui abrir a janela de feedback: {e}", COLOR_YELLOW); return False
        try:
            w = getattr(self, "_fb_win", None)
            if w is not None:
                try: w.show(); w.restore(); return True
                except Exception: self._fb_win = None
            w = webview.create_window("Lume Feedback", f"http://127.0.0.1:{PORT}/feedback?v={urllib.parse.quote(VERSION)}", width=440, height=720, min_size=(360, 480))   # nao fica mais "sempre por cima": e uma janela normal para anotar enquanto testa
            w.events.closed += lambda: setattr(self, "_fb_win", None)
            self._fb_win = w; return True
        except Exception as e:
            log("FEEDBACK", f"Nao consegui abrir a janela de feedback: {e}", COLOR_YELLOW); return False
    """Botoes da barra de titulo propria (a janela nao tem a borda do Windows)."""
    def __init__(self):
        self._window = None   # com "_" o pywebview nao expoe ao JavaScript
        self._maximized = False
    def minimize(self): self._window.minimize()
    def open_html(self, html, title="Previa HTML"):
        """Abre o HTML de um bloco de codigo numa janela propria (sem acesso ao app)."""
        try: webview.create_window(str(title)[:60] or "Previa", html=str(html)[:3000000], width=1000, height=760, min_size=(360, 280))
        except Exception as e: log("PREVIA", f"Nao consegui abrir a janela: {e}", COLOR_YELLOW)
        return True
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
    def close(self):
        if tray_icon and load_config().get("tray_enabled"): self._window.hide(); return "hidden"   # com a bandeja ligada, fechar so esconde
        quit_app()

class QuickApi:
    """A caixinha do Alt+Espaco: a pagina (quick.html) so pede para esconder ou mudar a altura."""
    def hide(self):   # (a pagina pede ao perder o foco; logo depois de abrir o foco ainda esta chegando, entao ignora)
        if time.time() - QUICK.get("t", 0) > 0.6: quick_hide()
        return True
    def open_in_lume(self, msgs):
        """Leva a conversa da caixinha para o Lume: abre um chat novo com tudo e traz a janela principal para a frente."""
        quick_hide()
        try:
            w = window_api._window; w.show(); w.restore()
            w.evaluate_js("window.lumeImportChat && lumeImportChat(" + json.dumps(msgs, ensure_ascii=False) + ")")
            hw = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
            if hw: ctypes.windll.user32.SetForegroundWindow(hw)
        except Exception as e: log("RAPIDO", f"Nao consegui abrir no Lume: {e}", COLOR_YELLOW)
        return True
    def resize(self, h):
        try: quick_place(int(h))
        except Exception as e: log("RAPIDO", f"resize: {e}", COLOR_YELLOW)
        return True

QUICK_W, QUICK_TITLE = 680, "Lume Rapido"
def _quick_hwnd(): return ctypes.windll.user32.FindWindowW(None, QUICK_TITLE)
def quick_place(h_css=None):
    """Poe a caixinha no alto e no meio do monitor onde esta o mouse (tamanho em pixels da pagina)."""
    u = ctypes.windll.user32; hwnd = _quick_hwnd()
    if not hwnd: return
    try: k = u.GetDpiForWindow(hwnd) / 96.0
    except Exception: k = 1.0
    pt = wintypes.POINT(); u.GetCursorPos(ctypes.byref(pt))
    class MI(ctypes.Structure): _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    mi = MI(); mi.cbSize = ctypes.sizeof(mi); u.GetMonitorInfoW(u.MonitorFromPoint(pt, 2), ctypes.byref(mi)); w = mi.rcWork
    if h_css is None: r = wintypes.RECT(); u.GetWindowRect(hwnd, ctypes.byref(r)); h_css = round((r.bottom - r.top) / k)
    W, H = round(QUICK_W * k), round(max(70, h_css) * k)
    u.SetWindowPos(hwnd, ctypes.c_void_p(-1), w.left + (w.right - w.left - W) // 2, w.top + round((w.bottom - w.top) * 0.2), W, H, 0x0010)   # -1 = HWND_TOPMOST, 0x10 = NOACTIVATE

QUICK_STYLES = ("solid", "mica", "aero", "acrylic")
def quick_backcolor(w):
    """A janela do pywebview transparente deixa a cor de fundo do formulario (cinza claro) aparecer ATRAS da pagina, entao o vidro nunca aparecia (o fundo parecia um cinza chapado).
    Preto + 'vidro' do DWM (DwmExtendFrameIntoClientArea) = transparente de verdade."""
    try:
        from System import Action
        from System.Drawing import Color
        n = w.native
        def _set():
            n.BackColor = Color.Black
        n.Invoke(Action(_set))
    except Exception as e: log("RAPIDO", f"cor de fundo: {e}", COLOR_YELLOW)
def quick_style_apply():
    """Fundo da caixinha: mica / acrylic (Windows 11, via DWM), aero (vidro desfocado classico) ou solido."""
    try:
        hw = _quick_hwnd()
        if not hw: return
        if QUICK["win"] and load_config().get("quick_style", "mica") != "solid": quick_backcolor(QUICK["win"])
        st = load_config().get("quick_style", "mica"); dwm = ctypes.windll.dwmapi
        class ACCENT(ctypes.Structure): _fields_ = [("State", ctypes.c_int), ("Flags", ctypes.c_int), ("Color", ctypes.c_uint), ("Anim", ctypes.c_int)]
        class WCA(ctypes.Structure): _fields_ = [("Attr", ctypes.c_int), ("Data", ctypes.c_void_p), ("Size", ctypes.c_size_t)]
        def accent(state, color=0):
            a = ACCENT(state, 2, color, 0); d = WCA(19, ctypes.cast(ctypes.pointer(a), ctypes.c_void_p), ctypes.sizeof(a)); ctypes.windll.user32.SetWindowCompositionAttribute(hw, ctypes.byref(d))
        try:
            import winreg; dark = winreg.QueryValueEx(winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"), "AppsUseLightTheme")[0] == 0
        except Exception: dark = True
        dwm.DwmSetWindowAttribute(hw, 20, ctypes.byref(ctypes.c_int(1 if dark else 0)), 4)   # vidro escuro ou claro
        dwm.DwmSetWindowAttribute(hw, 33, ctypes.byref(ctypes.c_int(2)), 4)                    # cantos arredondados
        accent(0)
        if st == "solid": dwm.DwmSetWindowAttribute(hw, 38, ctypes.byref(ctypes.c_int(1)), 4)
        else:
            dwm.DwmExtendFrameIntoClientArea(hw, ctypes.byref((ctypes.c_int * 4)(-1, -1, -1, -1)))   # deixa o efeito aparecer atras da pagina transparente
            if st == "mica": dwm.DwmSetWindowAttribute(hw, 38, ctypes.byref(ctypes.c_int(2)), 4)
            elif st == "acrylic": dwm.DwmSetWindowAttribute(hw, 38, ctypes.byref(ctypes.c_int(3)), 4)
            else: dwm.DwmSetWindowAttribute(hw, 38, ctypes.byref(ctypes.c_int(1)), 4); accent(3, 0x66201E1C if dark else 0x66F5F5F5)   # aero: vidro desfocado (blur-behind)
        if QUICK["win"]: threading.Thread(target=lambda: QUICK["win"].evaluate_js("window.qstyle && qstyle(" + json.dumps(st) + ", " + json.dumps(dark) + ")"), daemon=True).start()   # em outra thread: evaluate_js numa janela escondida pode ficar esperando
    except Exception as e: log("RAPIDO", f"estilo: {e}", COLOR_YELLOW)

def quick_focus(w):
    """Da o foco do teclado ao controle do navegador dentro da janela (so SetForegroundWindow nao basta no WebView2)."""
    try:
        from System import Action
        n = w.native; n.Invoke(Action(lambda: n.webview.Focus()))
    except Exception as e: log("RAPIDO", f"foco: {e}", COLOR_YELLOW)

def _clip_open():
    u = ctypes.windll.user32
    for _ in range(15):
        if u.OpenClipboard(None): return True
        time.sleep(0.02)
    return False

def _clip_text():
    """(texto, so_texto): o texto da area de transferencia (None se nao ha) e se ela tem SO texto (imagem/arquivo copiados nao podem ser devolvidos depois)."""
    u = ctypes.windll.user32; k = ctypes.windll.kernel32
    u.GetClipboardData.restype = ctypes.c_void_p; u.GetClipboardData.argtypes = [wintypes.UINT]; u.EnumClipboardFormats.argtypes = [wintypes.UINT]
    k.GlobalLock.restype = ctypes.c_void_p; k.GlobalLock.argtypes = [ctypes.c_void_p]; k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    if not _clip_open(): return None, False
    try:
        only, f = True, 0
        while True:
            f = u.EnumClipboardFormats(f)
            if not f: break
            if f < 0xC000 and f not in (1, 7, 13, 16): only = False   # figura, arquivos... (os formatos registrados por apps, como o HTML, nao contam)
        if not u.IsClipboardFormatAvailable(13): return None, only
        h = u.GetClipboardData(13); p = k.GlobalLock(h) if h else None
        if not p: return None, only
        try: return ctypes.wstring_at(p), only
        finally: k.GlobalUnlock(h)
    finally: u.CloseClipboard()

def _clip_set(text):
    u = ctypes.windll.user32; k = ctypes.windll.kernel32
    k.GlobalAlloc.restype = ctypes.c_void_p; k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]; k.GlobalLock.restype = ctypes.c_void_p; k.GlobalLock.argtypes = [ctypes.c_void_p]; k.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    if not _clip_open(): return
    try:
        u.EmptyClipboard()
        if text:
            data = (text + "\0").encode("utf-16-le"); h = k.GlobalAlloc(0x0002, len(data)); p = k.GlobalLock(h)
            ctypes.memmove(p, data, len(data)); k.GlobalUnlock(h); u.SetClipboardData(13, h)
    finally: u.CloseClipboard()

def quick_grab_selection():
    """Copia (Ctrl+C) o que esta selecionado no app da frente e devolve o texto; a area de transferencia volta como estava.
    Nunca no terminal (la o Ctrl+C interrompe o programa que esta rodando) e nunca se voce copiou uma imagem/arquivo (nao daria para devolver)."""
    u = ctypes.windll.user32
    try:
        import vcomp
        hw = u.GetForegroundWindow(); pid = wintypes.DWORD(); u.GetWindowThreadProcessId(hw, ctypes.byref(pid))
        exe = vcomp._exe_of(pid.value).lower(); term = next((e for ws, (lab, e) in vcomp.CATEGORIES.items() if lab == "terminal"), set())
        if exe in term or hw == _quick_hwnd(): return None
        t0 = time.time()
        while time.time() - t0 < 1.0 and any(u.GetAsyncKeyState(v) & 0x8000 for v in (0x10, 0x11, 0x12, 0x20)): time.sleep(0.02)   # espera soltar Ctrl/Alt/Shift/Espaco: senao o Ctrl+C sairia errado
        before, only_text = _clip_text()
        if not only_text: return None
        seq0 = u.GetClipboardSequenceNumber()
        for _try in range(2):   # o primeiro Ctrl+C logo depois de trocar de janela as vezes se perde: tenta de novo uma vez
            for vk, up in ((0x11, 0), (0x43, 0), (0x43, 2), (0x11, 2)): u.keybd_event(vk, 0, up, 0)   # Ctrl+C
            for _ in range(15):
                time.sleep(0.02)
                if u.GetClipboardSequenceNumber() != seq0: break
            else: continue
            break
        else: return None   # nada selecionado (a area de transferencia nao mudou)
        time.sleep(0.03); got, _ = _clip_text(); _clip_set(before)
        return (got or "").strip()[:8000] or None
    except Exception as e: log("RAPIDO", f"selecao: {e}", COLOR_YELLOW); return None

def quick_selection():
    """Ctrl+Alt+Espaco: pega o texto selecionado e abre a caixinha com as acoes (explicar, traduzir...)."""
    if QUICK["visible"]: quick_hide(); return
    quick_toggle(quick_grab_selection())

def quick_toggle(sel=None):
    if QUICK["visible"]: quick_hide(); return
    w = QUICK["win"]
    if not w: return
    try:
        quick_style_apply(); w.show(); QUICK["visible"] = True; QUICK["t"] = time.time(); quick_place(86)
        u = ctypes.windll.user32; hwnd = _quick_hwnd()
        u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)   # um toque no Alt libera o SetForegroundWindow (o Windows nega foco a quem nao foi o ultimo a receber tecla)
        u.SetForegroundWindow(hwnd); quick_focus(w); w.evaluate_js("window.qshown && qshown()")
        if sel: w.evaluate_js("window.qselection && qselection(" + json.dumps(sel, ensure_ascii=False) + ")")
        threading.Timer(0.15, lambda: (quick_focus(w), w.evaluate_js("window.qshown && qshown()"))).start()   # de novo: o foco do teclado dentro da pagina as vezes so chega depois da janela
    except Exception as e: log("RAPIDO", f"Nao consegui abrir a caixinha: {e}", COLOR_YELLOW)

def quick_hotkey_loop():
    """Alt+Espaco global (RegisterHotKey). Liga e desliga sozinho conforme a opcao em Configuracoes > App."""
    u = ctypes.windll.user32; reg = False; reg2 = False; msg = wintypes.MSG(); warned = False
    while True:
        want2 = bool(load_config().get("quick_sel_hotkey", True))
        if want2 and not reg2: reg2 = bool(u.RegisterHotKey(None, 0x4C56, 0x0002 | 0x0001 | 0x4000, 0x20))   # Ctrl+Alt+Espaco (texto selecionado)
        elif reg2 and not want2: u.UnregisterHotKey(None, 0x4C56); reg2 = False
        want = bool(load_config().get("quick_hotkey", True))
        if want and not reg:
            reg = bool(u.RegisterHotKey(None, 0x4C55, 0x0001 | 0x4000, 0x20))   # MOD_ALT | MOD_NOREPEAT, VK_SPACE
            if not reg and not warned: warned = True; log("RAPIDO", "Alt+Espaco ja esta em uso por outro programa (ex.: PowerToys Run); a caixinha rapida nao abre por atalho.", COLOR_YELLOW)
        elif reg and not want: u.UnregisterHotKey(None, 0x4C55); reg = False
        while u.PeekMessageW(ctypes.byref(msg), None, 0x0312, 0x0312, 1):   # WM_HOTKEY
            if msg.wParam == 0x4C56: threading.Thread(target=quick_selection, daemon=True).start()
            if msg.wParam == 0x4C55:
                threading.Thread(target=quick_toggle, daemon=True).start()   # fora do laco do atalho: uma chamada lenta nao pode travar o proximo Alt+Espaco
        time.sleep(0.05)

def quick_setup():
    if sys.platform != "win32": return
    try:
        w = webview.create_window(QUICK_TITLE, f"http://127.0.0.1:{PORT}/quick", width=QUICK_W, height=86, frameless=True, on_top=True, hidden=True, easy_drag=False, transparent=True, js_api=QuickApi())
        def _loaded():   # o pywebview as vezes mostra a janela mesmo criada escondida
            try:
                hw = _quick_hwnd(); ctypes.windll.user32.ShowWindow(hw, 0)
                quick_style_apply()
            except Exception: pass
        w.events.loaded += _loaded
        QUICK["win"] = w; threading.Thread(target=quick_hotkey_loop, daemon=True).start()
    except Exception as e: log("RAPIDO", f"Caixinha Alt+Espaco indisponivel: {e}", COLOR_YELLOW)


# ---------------------------------------------------------------- pet na area de trabalho: o mascote numa janela transparente que da para jogar (quica nas bordas como uma gelatina)
PET = {"win": None, "reset": False, "hit": [], "state": None}
PET_TITLE = "Lume Pet"
def _pet_hwnd(): return ctypes.windll.user32.FindWindowW(None, PET_TITLE)
def pet_geometry(cfg=None):
    """(tamanho do bonequinho S, tamanho da janela W): a janela e maior para sobrar espaco quando ele estica ao voar."""
    pct = int((cfg or load_config()).get("pet_size", 200)); S = max(40, round(80 * pct / 100)); return S, round(S * 1.4)

def pet_style(w):
    """Janela do pet: sem fundo (vidro do DWM + preto = transparente), fora da barra de tarefas e que nao rouba o foco."""
    try:
        hw = _pet_hwnd()
        if not hw: return
        quick_backcolor(w); dwm = ctypes.windll.dwmapi; u = ctypes.windll.user32
        dwm.DwmSetWindowAttribute(hw, 33, ctypes.byref(ctypes.c_int(1)), 4)   # sem cantos arredondados
        dwm.DwmSetWindowAttribute(hw, 38, ctypes.byref(ctypes.c_int(1)), 4)   # sem efeito de fundo
        dwm.DwmExtendFrameIntoClientArea(hw, ctypes.byref((ctypes.c_int * 4)(-1, -1, -1, -1)))
        ex = u.GetWindowLongW(hw, -20); u.SetWindowLongW(hw, -20, ex | 0x80 | 0x08000000)   # TOOLWINDOW (sem botao na barra) | NOACTIVATE (nao pega o foco)
    except Exception as e: log("PET", f"estilo: {e}", COLOR_YELLOW)

def pet_region(S, W):
    """So o circulo (um pouco maior, para a gelatina esticar) recebe cliques; os cantos da janela deixam o clique passar."""
    try:
        hw = _pet_hwnd()
        if not hw: return
        d = round(S * 1.3); o = (W - d) // 2
        rgn = ctypes.windll.gdi32.CreateEllipticRgn(o, o, o + d, o + d); ctypes.windll.user32.SetWindowRgn(hw, rgn, True)
    except Exception: pass

def pet_js(code):
    """Roda JS na janela do pet sem travar a fisica (o pywebview espera a resposta da pagina)."""
    w = PET["win"]
    if not w: return
    threading.Thread(target=lambda: _pet_eval(w, code), daemon=True).start()
def _pet_eval(w, code):
    try: w.evaluate_js(code)
    except Exception: pass

def pet_loop():
    """A fisica do pet (60 quadros por segundo): segura com o mouse, joga, quica nas bordas da area de trabalho com gravidade, e grudar na borda."""
    u = ctypes.windll.user32; pt = wintypes.POINT(); cfg = load_config(); cfg_t = 0.0
    class MI(ctypes.Structure): _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    def work_area(x, y):
        mi = MI(); mi.cbSize = ctypes.sizeof(mi); u.GetMonitorInfoW(u.MonitorFromPoint(wintypes.POINT(int(x), int(y)), 2), ctypes.byref(mi)); return mi.rcWork
    x = y = 0.0; vx = vy = 0.0; shown = False; placed = False; S, W = pet_geometry(cfg); drag = None; down_prev = False; snapped = 0   # snapped: -1 esquerda, 1 direita
    hist = []; last = time.perf_counter(); sent = 0.0; saved_pos = None; saved_t = 0.0; hover = [0.0, 0]; GRAV = 1800.0; REST = 0.74
    def put(nx, ny, size=None):
        hw = _pet_hwnd()
        if hw: u.SetWindowPos(hw, ctypes.c_void_p(-1), int(nx), int(ny), int(size or W), int(size or W), 0x0010 | (0 if size else 0x0001))   # TOPMOST, sem ativar
    while True:
        time.sleep(0.012); now = time.perf_counter(); dt = min(0.05, now - last); last = now
        if now - cfg_t > 1.0: cfg = load_config(); cfg_t = now
        want = bool(cfg.get("pet_desktop")) and PET["win"] is not None
        hw = _pet_hwnd()
        if not want or not hw:
            if shown and PET["win"]:
                try: PET["win"].hide()
                except Exception: pass
                shown = False
            time.sleep(0.15); continue
        nS, nW = pet_geometry(cfg)
        if not shown:   # ligou agora: mostra (no lugar de antes, ou no canto de baixo)
            S, W = nS, nW
            try: PET["win"].show()
            except Exception: pass
            pet_style(PET["win"]); shown = True
            pos = cfg.get("pet_pos")
            if isinstance(pos, list) and len(pos) == 2: x, y = float(pos[0]), float(pos[1])
            else: PET["reset"] = True
            vx = vy = 0.0; snapped = 0; placed = False; put(x, y, W); pet_region(S, W); pet_js(f"petSize({S})")
        if nS != S:   # mudou o tamanho nas configuracoes
            cx, cy = x + W / 2, y + W / 2; S, W = nS, nW; x, y = cx - W / 2, cy - W / 2; put(x, y, W); pet_region(S, W); pet_js(f"petSize({S})")
        u.GetCursorPos(ctypes.byref(pt)); px, py = pt.x, pt.y; down = bool(u.GetAsyncKeyState(0x01) & 0x8000)
        wa = work_area(x + W / 2, y + W / 2); pad = (W - S) / 2
        if PET["reset"]:   # "Resetar posicao": canto de baixo, a direita, do monitor onde esta o mouse
            PET["reset"] = False; wa = work_area(px, py); x = wa.right - W + pad - 24; y = wa.bottom - W + pad - 24; vx = vy = 0.0; snapped = 0; drag = None; put(x, y)
        cxp, cyp = x + W / 2, y + W / 2; over = math.hypot(px - cxp, py - cyp) <= S / 2
        if down and not down_prev and over and drag is None:   # pegou o pet
            drag = {"ox": px - x, "oy": py - y, "t0": now, "p0": (px, py), "moved": False}; hist = []; vx = vy = 0.0
            if snapped: snapped = 0; pet_js("petSnap(0)")
        down_prev = down
        if drag is not None:
            if down:
                if not drag["moved"] and math.hypot(px - drag["p0"][0], py - drag["p0"][1]) > 5: drag["moved"] = True
                if drag["moved"]:
                    x, y = px - drag["ox"], py - drag["oy"]; put(x, y); hist.append((now, px, py)); hist = [h for h in hist if now - h[0] < 0.12]
            else:   # soltou: clique (pulinho) ou arremesso
                d = drag; drag = None
                if not d["moved"] and now - d["t0"] < 0.4: vy = -520.0; pet_js("petClick()")
                elif len(hist) >= 2 and now - hist[-1][0] < 0.08:
                    dtv = max(0.016, hist[-1][0] - hist[0][0]); vx = (hist[-1][1] - hist[0][1]) / dtv; vy = (hist[-1][2] - hist[0][2]) / dtv
                    sp = math.hypot(vx, vy)
                    if sp > 4200: vx, vy = vx * 4200 / sp, vy * 4200 / sp
                if cfg.get("pet_snap", True) and math.hypot(vx, vy) < 500:   # grudar na borda: solta perto da esquerda/direita, devagar
                    if cxp - wa.left < S * 0.7: snapped = -1
                    elif wa.right - cxp < S * 0.7: snapped = 1
                    if snapped: vx = vy = 0.0; pet_js(f"petSnap({snapped})")
        elif snapped:
            x = (wa.left - pad - S * 0.45) if snapped < 0 else (wa.right - W + pad + S * 0.45); put(x, y)
        else:   # fisica livre: gravidade, quicar nas bordas (gelatina) e parar no chao
            vy += GRAV * dt; x += vx * dt; y += vy * dt; sp0 = math.hypot(vx, vy)
            vx *= max(0.0, 1 - 0.08 * dt); lo_x, hi_x, lo_y, hi_y = wa.left - pad, wa.right - W + pad, wa.top - pad, wa.bottom - W + pad
            def hit(nx, ny, spd):
                if spd > 140: PET["hit"].append((nx, ny, spd))
            if x < lo_x: x = lo_x; hit(1, 0, abs(vx)); vx = abs(vx) * REST
            elif x > hi_x: x = hi_x; hit(-1, 0, abs(vx)); vx = -abs(vx) * REST
            if y < lo_y: y = lo_y; hit(0, 1, abs(vy)); vy = abs(vy) * REST
            elif y > hi_y:
                y = hi_y; hit(0, -1, abs(vy)); vy = -abs(vy) * REST
                if abs(vy) < 160: vy = 0.0
                vx *= max(0.0, 1 - 4.0 * dt)   # atrito no chao
                if abs(vx) < 12: vx = 0.0
            put(x, y)
        for h in PET["hit"][:4]: pet_js(f"petHit({h[0]},{h[1]},{h[2]:.0f})")
        PET["hit"].clear()
        if now - sent > 0.033:   # olhos seguem o cursor; a gelatina estica com a velocidade
            sent = now; dx, dy = px - (x + W / 2), py - (y + W / 2); dd = math.hypot(dx, dy) or 1.0; k = min(1.0, dd / 260)
            pet_js(f"petState({vx:.0f},{vy:.0f},{dx / dd * k:.2f},{dy / dd * k:.2f},{'true' if (drag is not None and drag['moved']) else 'false'})")
        if now - saved_t > 3.0:   # lembra onde ele ficou
            saved_t = now; cur = [int(x), int(y)]
            if cur != saved_pos and vx == 0 and abs(vy) < 5:
                saved_pos = cur
                try: c2 = load_config(); c2["pet_pos"] = cur; save_config(c2)
                except Exception: pass

def pet_setup():
    if sys.platform != "win32": return
    try:
        S, W = pet_geometry()
        w = webview.create_window(PET_TITLE, f"http://127.0.0.1:{PORT}/pet", width=W, height=W, frameless=True, on_top=True, hidden=True, easy_drag=False, transparent=True, focus=False)
        def _loaded():
            try:
                if load_config().get("pet_desktop"): pet_style(w); pet_js(f"petSize({pet_geometry()[0]})")   # ja ligado: a pagina acabou de carregar, so ajusta
                else: ctypes.windll.user32.ShowWindow(_pet_hwnd(), 0)   # o pywebview as vezes mostra a janela mesmo criada escondida
            except Exception: pass
        w.events.loaded += _loaded
        PET["win"] = w; threading.Thread(target=pet_loop, daemon=True).start()
    except Exception as e: log("PET", f"Pet da area de trabalho indisponivel: {e}", COLOR_YELLOW)


if __name__ == '__main__':
    if "--feedback-window" in sys.argv:   # processo so da janela de feedback (aberto pelo Lume no Linux): nao sobe servidor, so mostra a pagina do Lume que ja esta rodando
        _i = sys.argv.index("--feedback-window")
        webview.create_window("Lume Feedback", f"http://127.0.0.1:{int(sys.argv[_i + 1])}/feedback?v={urllib.parse.quote(sys.argv[_i + 2] if len(sys.argv) > _i + 2 else '')}", width=440, height=720, min_size=(360, 480))
        webview.start(private_mode=True)
        sys.exit(0)
    UI_LANG = load_config().get("ui_lang", "pt") if load_config().get("ui_lang") in ("pt", "en") else "pt"   # o terminal ja abre no idioma em que o app ficou
    log("INICIO", f"Pasta do programa: {BASE_DIR}", COLOR_BLUE)
    PORT = int(_env("PORT") or load_config().get("port", PORT))
    if FROZEN and load_config().get("start_with_terminal"): set_terminal(True)
    log("INICIO", "Groq: " + ("biblioteca ok" if HAS_GROQ else "biblioteca NAO instalada (pip install groq)"), COLOR_GREEN if HAS_GROQ else COLOR_YELLOW)
    if HANDOFF:
        try:
            with open(_hf("ready"), "w") as f: f.write(str(os.getpid()))   # o app antigo solta a porta agora
        except OSError: pass
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=start_ollama, daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()
    threading.Thread(target=model_updater_loop, daemon=True).start()
    if lumemcp: threading.Thread(target=lambda: lumemcp.sync(load_config().get("mcp_servers") or {}), daemon=True).start()   # liga os servidores MCP salvos
    if not FROZEN: threading.Thread(target=dev_watch_loop, daemon=True).start()   # reinicia sozinho quando os .py mudam (desligavel em Configuracoes > App)
    tray_on = bool(load_config().get("tray_enabled")) and tray_start()
    start_gpu_stream(gpu_interval_ms)
    for _ in range(300 if HANDOFF else 40):   # espera ESTE servidor subir (antes era um sleep fixo de 1 s): normalmente leva uns 0,1 s; no reinicio sem sumir espera o antigo soltar a porta
        if httpd is not None: break
        time.sleep(0.1)
    hw_accel_apply()
    log("INICIO", "Abrindo janela...", COLOR_BLUE)
    api = WindowApi()
    geo = handoff_geometry() if (HANDOFF or "--updated" in sys.argv) else None   # reinicio/atualizacao: a janela nova abre onde a antiga estava
    pos = {"x": geo["x"], "y": geo["y"]} if geo else {}
    api._window = webview.create_window(WINDOW_TITLE, f'http://127.0.0.1:{PORT}/index.html', width=geo["w"] if geo else 1100, height=geo["h"] if geo else 800, min_size=(800, 520), frameless=True, easy_drag=False, js_api=api, hidden=bool(tray_on and "--autostart" in sys.argv), **pos)
    if HANDOFF or geo:
        def _first_load():
            api._window.events.loaded -= _first_load
            try:
                if geo and geo.get("px"):   # o tamanho que o pywebview da nao bate com a borda do Windows: poe a janela exatamente onde a antiga estava
                    hw = _my_hwnd(WINDOW_TITLE)
                    if hw: ctypes.windll.user32.SetWindowPos(hw, 0, *geo["px"], 0x0004)   # 0x4 = nao mexe na ordem das janelas
                if geo and geo.get("max"): api.toggle_maximize()
            except Exception: pass
            try:
                with open(_hf("shown"), "w") as f: f.write("1")   # o app antigo pode fechar
            except OSError: pass
        api._window.events.loaded += _first_load
    # private_mode=False: sem isso o localStorage some toda vez que o app fecha
    window_api = api
    quick_setup()
    pet_setup()
    webview.start(private_mode=False, storage_path=os.path.join(BASE_DIR, "webview_data"), icon=custom_icon_ico())
    log("SAIDA", "Janela fechada. Desligando as IAs...", COLOR_YELLOW)
    shutdown_all()
    log("SAIDA", "Tudo desligado.", COLOR_GREEN)
