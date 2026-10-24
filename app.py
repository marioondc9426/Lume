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
import atexit
import base64
import functools
import webview

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

PORT = 8000
OLLAMA_URL = "http://127.0.0.1:11434"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")     # chaves de API, pasta de trabalho, uso
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")   # chats
STATE_FILE = os.path.join(BASE_DIR, "state.json")       # preferencias da interface + memorias
THEMES_DIR = os.path.join(BASE_DIR, "custom themes")    # temas criados no editor de temas
MAX_AGENT_STEPS = 8        # limite de chamadas de ferramenta por mensagem
MAX_TOOL_OUTPUT = 8000     # caracteres devolvidos a IA por ferramenta
TOOL_TIMEOUT = 60          # segundos para cmd/powershell
MIN_WEB_QUERY = 5         # mensagens menores que isso ("oi") nao disparam pesquisa na web
VRAM_WARN_MB = 6144        # aviso de VRAM alta (6 GB)
MAX_ALERTS = 5             # quantas vezes repetir o mesmo aviso enquanto a situacao continuar
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

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f: cfg = json.load(f)
        except Exception as e:
            log("CONFIG", f"config.json invalido ({e}). Usando padrao.", COLOR_RED)
    else:
        log("CONFIG", "Criando config padrao", COLOR_YELLOW)
    cfg.setdefault("groq_api_key", "")
    cfg.setdefault("workdir", "")
    cfg.setdefault("usage", {}).setdefault("groq", 0)
    return cfg

def save_config(config_data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(config_data, f, indent=4)

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
def search_web(query):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        titles = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
        links = re.findall(r'<a class="result__url" href="([^"]+)"', html)
        clean_titles = [re.sub(r'<[^>]+>', '', t).strip() for t in titles[:3]]
        if not clean_titles: return "Nenhum resultado."
        res = "\n\n--- RESULTADOS ---\n"
        for i, (t, l) in enumerate(zip(clean_titles, links)): res += f"[{i+1}] {t}\nLink: {l.strip()}\n\n"
        return res
    except Exception as e: return f"Erro: {e}"

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
Faca UMA chamada por vez; o resultado volta na proxima mensagem. Quando terminar, responda normalmente, sem ferramentas.
"""

PATH_TOOLS = ("list_files", "read_file", "write_file")

def normalize_args(name, args):
    """Aceita argumentos mal formados (chave errada) pegando o primeiro valor."""
    if not isinstance(args, dict): args = {}
    key = "command" if name in ("cmd", "powershell") else "query" if name == "search_web" else "path" if name in PATH_TOOLS else None
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

def execute_tool(tool_name, tool_args, workdir):
    def full(p): return p if os.path.isabs(p) else os.path.join(workdir, p)
    try:
        if tool_name == "list_files":
            return truncate("\n".join(os.listdir(full(tool_args.get("path", ".")))) or "(pasta vazia)")
        if tool_name == "read_file":
            with open(full(tool_args["path"]), 'r', encoding='utf-8', errors='replace') as f: return truncate(f.read())
        if tool_name == "write_file":
            path = full(tool_args["path"])
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f: f.write(tool_args.get("content", ""))
            return "Arquivo escrito com sucesso."
        if tool_name in ("cmd", "powershell"):
            cmd = tool_args["command"]
            argv = cmd if tool_name == "cmd" else ["powershell", "-NoProfile", "-Command", cmd]
            r = subprocess.run(argv, shell=(tool_name == "cmd"), capture_output=True, text=True, errors="replace", timeout=TOOL_TIMEOUT, cwd=workdir)
            out = (r.stdout or "") + (r.stderr or "")
            if r.returncode != 0: out += f"\n[codigo de saida {r.returncode}]"
            return truncate(out.strip() or "(sem saida)")
        if tool_name == "search_web":
            return truncate(search_web(tool_args.get("query", "")))
        return f"Ferramenta desconhecida: {tool_name}"
    except subprocess.TimeoutExpired:
        return f"Erro: comando passou de {TOOL_TIMEOUT}s e foi cancelado."
    except KeyError as e:
        return f"Erro: argumento faltando: {e}"
    except Exception as e:
        return f"Erro: {e}"

TOOL_MARK = re.compile(r'\$\$\s*\[\s*TOOL\s*[:\s]\s*(\w+)[^\]]*\]', re.IGNORECASE)

def find_tool_call(text):
    """Procura uma chamada completa `$$[TOOL: nome] {json}$$`. Retorna (nome, args, fim) ou None."""
    m = TOOL_MARK.search(text)
    if not m: return None
    rest = text[m.end():]
    start = rest.find('{')
    if start == -1: return None
    try:
        args, used = json.JSONDecoder().raw_decode(rest[start:])
    except Exception:
        try:
            args, used = json.JSONDecoder().raw_decode(rest[start:].replace("'", '"'))
        except Exception:
            return None
    end = m.end() + start + used
    tail = text[end:end + 4].lstrip()
    if tail.startswith("$$"): end = text.index("$$", end) + 2
    return m.group(1), args, end

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

def ollama_ps():
    """Modelos carregados na memoria agora: [{name, size, size_vram, ...}]."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=2) as r: return json.load(r).get("models", [])
    except Exception:
        return []

def ollama_load(model):
    ollama_post("/api/generate", {"model": model, "keep_alive": "10m"})

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
    stop_gpu_stream()
    for m in ollama_ps():
        try:
            ollama_unload(m["name"]); log("SAIDA", f"Modelo {m['name']} desligado.", COLOR_YELLOW)
        except Exception as e:
            log("SAIDA", f"Nao consegui desligar {m['name']}: {e}", COLOR_RED)
    stop_ollama()
atexit.register(stop_ollama)

# ---------------------------------------------------------------- monitor de memoria
alert_state = {"id": 0, "kind": "", "text": "", "suggest": "", "count": 0, "max": MAX_ALERTS}
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

def emit_alert(kind, text, suggest, count):
    alert_state.update(id=alert_state["id"] + 1, kind=kind, text=text, suggest=suggest, count=count)
    log("MEMORIA", f"{text} (aviso {count}/{MAX_ALERTS})", COLOR_YELLOW)

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
    if swap and _swap_alerts["count"] < MAX_ALERTS and now - _swap_alerts["last"] >= 30:
        ranked = rank_models_to_stop(loaded)
        for _, _, detail in ranked: log("MEMORIA", f"  pontuacao -> {detail}", COLOR_GRAY)
        suggest = ranked[0][1] if ranked else ""
        _swap_alerts["count"] += 1; _swap_alerts["last"] = now
        text = f"VRAM no limite ({used / 1024:.1f} de {total / 1024:.1f} GB)" + (", modelo vazando para a RAM/CPU" if partial else "")
        text += f". Recomendado desligar o modelo {suggest}." if suggest else "."
        emit_alert("swap", text, suggest, _swap_alerts["count"])
    elif high and not swap and _vram_alerts["count"] < MAX_ALERTS and now - _vram_alerts["last"] >= 10:
        _vram_alerts["count"] += 1; _vram_alerts["last"] = now
        emit_alert("vram", f"VRAM alta: {used / 1024:.1f} de {total / 1024:.1f} GB em uso.", "", _vram_alerts["count"])

def monitor_loop():
    while True:
        time.sleep(2)
        try: check_memory()
        except Exception as e: log("MEMORIA", f"Erro no monitor: {e}", COLOR_RED)

# ---------------------------------------------------------------- modelos
def stream_ollama(model, messages, think, num_ctx=None):
    """Gera ('content'|'thinking'|'stats', valor)."""
    payload = {"model": model, "messages": messages, "stream": True, "think": bool(think)}
    if num_ctx: payload["options"] = {"num_ctx": int(num_ctx)}   # tamanho do contexto (o padrao do Ollama e 4096)
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

def stream_model(model, messages, think, cfg, num_ctx=None):
    return stream_groq(model, messages, cfg) if model.startswith("groq") else stream_ollama(model, messages, think, num_ctx)

# ---------------------------------------------------------------- servidor
class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def log_message(self, format, *args): pass

    def send_json(self, obj, code=200):
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_OPTIONS(self):
        self.send_response(204); self.end_headers()

    def do_GET(self):
        if self.path == '/favicon.ico': self.send_response(404); self.end_headers(); return
        if self.path in ('/', '/index.html'): log("HTTP", "Interface carregada", COLOR_BLUE)
        if self.path == '/api/usage':
            return self.send_json(load_config().get("usage", {}))
        if self.path == '/api/check_pending':
            return self.send_json({"cmd": pending_command["cmd"]})
        if self.path == '/api/history':
            return self.send_json(load_history())
        if self.path == '/api/state':
            return self.send_json(load_state())
        if self.path == '/api/custom_themes':
            return self.send_json(list_custom_themes())
        if self.path == '/api/config_status':
            cfg = load_config()
            return self.send_json({"groq_key_saved": bool(cfg.get("groq_api_key")), "workdir": get_workdir(cfg), "default_workdir": BASE_DIR})
        if self.path == '/api/models_status':
            running = ollama_is_running()
            used, total, _ = get_gpu_metrics()
            loaded = [{"name": m["name"], "size": m.get("size", 0), "size_vram": m.get("size_vram", 0)} for m in ollama_ps()] if running else []
            return self.send_json({"running": running, "loaded": loaded, "vram_total": total, "vram_used": used})
        if self.path == '/api/metrics':
            vram_used, vram_total, gpu_util = get_gpu_metrics()
            vram_pct = None
            vram_warn = ''
            if vram_used is not None and vram_total:
                vram_pct = round(100 * vram_used / vram_total, 1)
                if vram_used >= vram_total - 300: vram_warn = f'VRAM no limite ({vram_pct}%)'
                elif vram_used > VRAM_WARN_MB: vram_warn = f'VRAM alta ({vram_used / 1024:.1f} GB)'
            return self.send_json({
                "vram_used": vram_used, "vram_total": vram_total, "vram": vram_used,
                "vram_pct": vram_pct, "gpu": gpu_util, "vram_warn": vram_warn,
                "generation_active": generation_active, "alert": alert_state
            })
        super().do_GET()

    def do_POST(self):
        post_data = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        quiet = ('/api/chat', '/api/history', '/api/state')
        if self.path not in quiet: log("API", f"POST {self.path}", COLOR_BLUE)
        data = {} if self.path == '/api/chat' else json.loads(post_data or b'{}')

        if self.path in ('/api/save_config', '/api/save_key'):
            cfg = load_config()
            if data.get("workdir") and not os.path.isdir(data["workdir"]):
                log("CONFIG", f"Pasta de trabalho invalida: {data['workdir']}", COLOR_RED)
                return self.send_json({"error": "Pasta de trabalho nao existe."}, 400)
            for k in ("groq_api_key", "workdir"):
                if k in data: cfg[k] = data[k]
            save_config(cfg)
            log("CONFIG", "Configuracoes salvas (" + ", ".join(k for k in data if k != "groq_api_key") + (", chave groq" if "groq_api_key" in data else "") + ")", COLOR_GREEN)
            return self.send_json({"ok": True})

        if self.path == '/api/history':
            save_history(data)
            log("HISTORICO", f"{len(data)} chat(s) salvos", COLOR_GRAY)
            return self.send_json({"ok": True})

        if self.path == '/api/state':
            save_state(data)
            return self.send_json({"ok": True})

        if self.path == '/api/custom_theme':
            name = safe_theme_name(data.get("name"))
            os.makedirs(THEMES_DIR, exist_ok=True)
            path = os.path.join(THEMES_DIR, name + ".json")
            _write_json(path, data.get("theme", {}))
            log("TEMA", f"Tema '{name}' salvo em {path}", COLOR_GREEN)
            return self.send_json({"ok": True, "name": name, "path": path})

        if self.path == '/api/custom_theme_delete':
            name = safe_theme_name(data.get("name"))
            path = os.path.join(THEMES_DIR, name + ".json")
            if os.path.exists(path): os.remove(path); log("TEMA", f"Tema '{name}' apagado", COLOR_YELLOW)
            return self.send_json({"ok": True})

        if self.path == '/api/resolve_pending':
            approved = data.get("approved", False)
            log("PERMISSAO", "Aprovado pelo usuario" if approved else "Negado pelo usuario", COLOR_GREEN if approved else COLOR_RED)
            if pending_command["resolve"]:
                pending_command["resolve"](approved)
            return self.send_json({"ok": True})

        if self.path == '/api/stop':
            log("STOP", "Parada solicitada pelo usuario", COLOR_YELLOW)
            stop_generation_flag.set()
            return self.send_json({"ok": True})

        if self.path == '/api/start':
            return self.send_json({"running": start_ollama()})

        if self.path == '/api/model_start':
            model = data.get("model", "")
            try:
                if not start_ollama(): raise Exception("Ollama nao esta rodando.")
                log("MODELO", f"Carregando {model}...", COLOR_CYAN)
                t = time.time(); ollama_load(model)
                log("MODELO", f"{model} carregado em {time.time() - t:.1f}s", COLOR_GREEN)
                return self.send_json({"ok": True})
            except Exception as e:
                log("MODELO", f"Falha ao carregar {model}: {e}", COLOR_RED)
                return self.send_json({"ok": False, "error": str(e)}, 500)

        if self.path == '/api/model_stop':
            model = data.get("model", "")
            if generation_active and active_model == model: stop_generation_flag.set()
            try:
                ollama_unload(model)
                log("MODELO", f"{model} desligado.", COLOR_YELLOW)
                return self.send_json({"ok": True})
            except Exception as e:
                log("MODELO", f"Falha ao desligar {model}: {e}", COLOR_RED)
                return self.send_json({"ok": False, "error": str(e)}, 500)

        if self.path == '/api/perf_interval':
            ms = max(50, min(5000, int(data.get("ms", 50))))
            if ms != gpu_interval_ms or not gpu_proc: start_gpu_stream(ms)
            return self.send_json({"ok": True, "ms": ms})

        if self.path == '/api/export':
            name = re.sub(r'[^\w.\- ]', '_', data.get("filename", "chat.txt"))
            folder = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(folder, exist_ok=True)
            base, ext = os.path.splitext(name); path = os.path.join(folder, name); n = 1
            while os.path.exists(path):
                path = os.path.join(folder, f"{base} ({n}){ext}"); n += 1
            with open(path, 'wb') as f: f.write(base64.b64decode(data.get("b64", "")))
            log("EXPORTAR", f"Salvo em {path}", COLOR_GREEN)
            return self.send_json({"ok": True, "path": path})

        if self.path == '/api/chat':
            return self.handle_chat(json.loads(post_data))

        self.send_json({"error": "rota desconhecida"}, 404)

    def handle_chat(self, req_json):
        global generation_active, active_model
        stop_generation_flag.clear()
        generation_active = True
        started = time.time()
        model = req_json.get('model', 'qwen3.5:4b')
        active_model = model
        messages = req_json.get("messages", [])
        agent = bool(req_json.get("agent"))
        think = bool(req_json.get("think"))
        num_ctx = req_json.get("num_ctx")
        cfg = load_config()
        workdir = get_workdir(cfg)
        n_images = sum(len(m.get("images", [])) for m in messages)
        log("CHAT", f"modelo={model} modo={'agente' if agent else 'chat'} mensagens={len(messages)} imagens={n_images} contexto={num_ctx or 'padrao'} pensar={think} web={bool(req_json.get('search_web'))}", COLOR_CYAN)

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
                messages[0]["content"] += TOOL_PROMPT.replace("{workdir}", workdir)
            elif req_json.get("search_web"):
                query = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")[:200]
                if len(query.strip()) >= MIN_WEB_QUERY:
                    status("Pesquisando na web")
                    log("WEB", f"Pesquisando: {query}", COLOR_CYAN)
                    messages[0]["content"] += "\n\n[PESQUISA NA WEB - use se for relevante e cite os links]" + search_web(query)
                else:
                    log("WEB", "Mensagem curta demais, pesquisa ignorada.", COLOR_GRAY)

            for step in range(MAX_AGENT_STEPS if agent else 1):
                full = ""
                gen = stream_model(model, messages, think, cfg, num_ctx)
                try:
                    for kind, piece in gen:
                        if stop_generation_flag.is_set(): break
                        if kind == "thinking":
                            send(piece, "thinking"); continue
                        if kind == "stats":
                            ptps = piece['prompt_tokens'] / piece['prompt_seconds'] if piece['prompt_seconds'] else 0
                            log("OLLAMA", f"{piece['tokens']} tokens em {piece['seconds']:.1f}s = {piece['tokens'] / piece['seconds']:.1f} t/s | prompt {piece['prompt_tokens']} tokens ({ptps:.0f} t/s) | carga do modelo {piece['load_seconds']:.1f}s | total {piece['total_seconds']:.1f}s", COLOR_GREEN)
                            emit({"stats": piece}); continue
                        full += piece
                        send(piece)
                        if agent and ('}' in piece or '$' in piece) and find_tool_call(full): break
                finally:
                    gen.close()
                total_chars += len(full)
                if stop_generation_flag.is_set():
                    send("\n\n[Geracao parada]")
                    break
                call = find_tool_call(full) if agent else None
                if not call:
                    break
                tool_name, tool_args, end = call
                tool_args = normalize_args(tool_name, tool_args)
                full = full[:end]
                log("TOOL", f"{tool_name} {tool_args}", COLOR_CYAN)
                if needs_permission(tool_name):
                    status("Aguardando permissão")
                    if not ask_permission(describe_tool(tool_name, tool_args)):
                        send("\n\n[Acao negada pelo usuario]")
                        break
                status(f"Executando: {tool_name}")
                result = execute_tool(tool_name, tool_args, workdir)
                log("TOOL", f"resultado de {tool_name}: {len(result)} caracteres", COLOR_GREEN if not result.startswith("Erro") else COLOR_RED)
                send(f"\n\n[resultado de {tool_name}]\n{result}\n\n")
                messages.append({"role": "assistant", "content": full})
                messages.append({"role": "user", "content": f"Resultado da ferramenta {tool_name}:\n{result}"})
                status("Pensando")
            else:
                if agent:
                    send(f"\n\n[Limite de {MAX_AGENT_STEPS} chamadas de ferramenta atingido]")
                    log("AGENTE", "Limite de passos atingido", COLOR_YELLOW)

            if model.startswith("groq"):
                cfg = load_config()
                cfg["usage"]["groq"] += total_chars
                save_config(cfg)
            u = model_usage.setdefault(model, {"uses": 0, "chars": 0})
            u["uses"] += 1; u["chars"] += total_chars; u["last_used"] = time.time()
            log("CHAT", f"concluido: {total_chars} caracteres em {time.time() - started:.1f}s", COLOR_GREEN)
        except Exception as e:
            log("ERRO", f"{type(e).__name__}: {e}", COLOR_RED)
            try: send(f"\n[Erro: {e}]")
            except Exception: pass
        finally:
            generation_active = False

def start_server():
    handler = functools.partial(CORSRequestHandler, directory=BASE_DIR)
    try:
        with ThreadingServer(("", PORT), handler) as httpd:
            log("SERVIDOR", f"Rodando em http://127.0.0.1:{PORT}", COLOR_GREEN)
            httpd.serve_forever()
    except OSError as e:
        log("SERVIDOR", f"Nao foi possivel usar a porta {PORT}: {e}. Ja tem outra copia aberta?", COLOR_RED)

class WindowApi:
    """Botoes da barra de titulo propria (a janela nao tem a borda do Windows)."""
    def __init__(self):
        self._window = None   # com "_" o pywebview nao expoe ao JavaScript
        self._maximized = False
    def minimize(self): self._window.minimize()
    def toggle_maximize(self):
        if self._maximized: self._window.restore()
        else: self._window.maximize()
        self._maximized = not self._maximized
        return self._maximized
    def close(self): self._window.destroy()

if __name__ == '__main__':
    log("INICIO", f"Pasta do programa: {BASE_DIR}", COLOR_BLUE)
    log("INICIO", "Groq: " + ("biblioteca ok" if HAS_GROQ else "biblioteca NAO instalada (pip install groq)"), COLOR_GREEN if HAS_GROQ else COLOR_YELLOW)
    threading.Thread(target=start_server, daemon=True).start()
    threading.Thread(target=start_ollama, daemon=True).start()
    threading.Thread(target=monitor_loop, daemon=True).start()
    start_gpu_stream(gpu_interval_ms)
    time.sleep(1)
    log("INICIO", "Abrindo janela...", COLOR_BLUE)
    api = WindowApi()
    api._window = webview.create_window('AI Website Thingmabobber', f'http://127.0.0.1:{PORT}/index.html', width=1100, height=800, min_size=(800, 520), frameless=True, easy_drag=False, js_api=api)
    # private_mode=False: sem isso o localStorage some toda vez que o app fecha
    webview.start(private_mode=False, storage_path=os.path.join(BASE_DIR, "webview_data"))
    log("SAIDA", "Janela fechada. Desligando as IAs...", COLOR_YELLOW)
    shutdown_all()
    log("SAIDA", "Tudo desligado.", COLOR_GREEN)
