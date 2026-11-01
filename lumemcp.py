"""Cliente MCP (Model Context Protocol) do Lume: liga servidores MCP por stdio (o mesmo formato "mcpServers" do Claude Desktop)
e mostra as ferramentas deles para a IA do modo Code. Cada servidor e um programa que o Lume abre (ex.: npx ... ou python ...) e conversa por JSON-RPC, uma mensagem por linha.
So o dono configura (um servidor MCP roda comandos no PC); as chamadas das ferramentas sempre passam pela permissao do Lume."""
import hashlib, json, os, re, shutil, subprocess, sys, threading, time

PROTOCOL = "2024-11-05"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
START_TIMEOUT = 60      # a 1a vez que o npx baixa um servidor pode demorar
CALL_TIMEOUT = 120
MAX_RESULT = 20000

class McpError(Exception): pass

class Server:
    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.proc = None; self.tools = []; self.error = ""; self.ready = False; self.starting = False
        self._id = 0; self._pending = {}; self._wlock = threading.Lock(); self.log_tail = []

    # ---- baixo nivel
    def _send(self, obj):
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self._wlock:
            self.proc.stdin.write(data); self.proc.stdin.flush()

    def _read_out(self):
        try:
            for raw in iter(self.proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").strip()
                if not line: continue
                try: msg = json.loads(line)
                except ValueError: self.log_tail = (self.log_tail + [line[:300]])[-20:]; continue   # linha de log no stdout: ignora
                if not isinstance(msg, dict): continue
                if "method" in msg and "id" in msg:   # o servidor pediu algo ao Lume: so respondemos ping; o resto nao e suportado
                    try: self._send({"jsonrpc": "2.0", "id": msg["id"], **({"result": {}} if msg["method"] == "ping" else {"error": {"code": -32601, "message": "not supported by Lume"}})})
                    except Exception: pass
                elif "id" in msg and msg["id"] in self._pending:
                    slot = self._pending.pop(msg["id"]); slot["msg"] = msg; slot["ev"].set()
        except Exception: pass
        finally:
            for slot in list(self._pending.values()):   # o processo acabou: acorda quem esperava
                slot.setdefault("msg", {"error": {"message": "o servidor MCP fechou"}}); slot["ev"].set()
            self.ready = False

    def _read_err(self):
        try:
            for raw in iter(self.proc.stderr.readline, b""):
                t = raw.decode("utf-8", "replace").strip()
                if t: self.log_tail = (self.log_tail + [t[:300]])[-20:]
        except Exception: pass

    def request(self, method, params=None, timeout=CALL_TIMEOUT):
        if not self.proc or self.proc.poll() is not None: raise McpError("o servidor MCP nao esta rodando")
        self._id += 1; rid = self._id; slot = {"ev": threading.Event()}; self._pending[rid] = slot
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        if not slot["ev"].wait(timeout):
            self._pending.pop(rid, None); raise McpError(f"sem resposta em {timeout}s ({method})")
        msg = slot["msg"]
        if "error" in msg:
            e = msg["error"]; raise McpError(str(e.get("message") if isinstance(e, dict) else e))
        return msg.get("result") or {}

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, **({"params": params} if params else {})})

    # ---- ciclo de vida
    def start(self):
        self.starting = True; self.error = ""; self.ready = False
        try:
            cmd = str(self.cfg.get("command") or "").strip()
            if not cmd: raise McpError("falta o \"command\"")
            exe = shutil.which(cmd) or cmd
            args = [str(a) for a in (self.cfg.get("args") or [])]
            env = dict(os.environ); env.update({str(k): str(v) for k, v in (self.cfg.get("env") or {}).items()})
            try:
                self.proc = subprocess.Popen([exe] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=self.cfg.get("cwd") or None, creationflags=NO_WINDOW)
            except FileNotFoundError: raise McpError(f"programa nao encontrado: {cmd} (instale-o ou use o caminho completo)")
            threading.Thread(target=self._read_out, daemon=True).start(); threading.Thread(target=self._read_err, daemon=True).start()
            self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "Lume", "version": "1"}}, START_TIMEOUT)
            self.notify("notifications/initialized")
            tools, cursor = [], None
            while True:
                res = self.request("tools/list", {"cursor": cursor} if cursor else {}, START_TIMEOUT)
                tools += [t for t in (res.get("tools") or []) if isinstance(t, dict) and t.get("name")]
                cursor = res.get("nextCursor")
                if not cursor or len(tools) > 300: break
            self.tools = tools; self.ready = True
        except Exception as e:
            self.error = str(e) + ((" | " + " / ".join(self.log_tail[-3:])) if self.log_tail else ""); self.stop()
        finally:
            self.starting = False

    def stop(self):
        p, self.proc = self.proc, None; self.ready = False
        if p:
            try: p.terminate()
            except Exception: pass

    def call(self, tool, args, timeout=CALL_TIMEOUT):
        res = self.request("tools/call", {"name": tool, "arguments": args if isinstance(args, dict) else {}}, timeout)
        parts = []
        for c in res.get("content") or []:
            if not isinstance(c, dict): continue
            t = c.get("type")
            if t == "text": parts.append(str(c.get("text", "")))
            elif t in ("image", "audio"): parts.append(f"[{t} omitido: o Lume so mostra texto de ferramentas MCP]")
            elif t == "resource":
                r = c.get("resource") or {}; parts.append(str(r.get("text") or f"[recurso {r.get('uri', '')}]"))
            else: parts.append(json.dumps(c, ensure_ascii=False)[:500])
        if not parts and res.get("structuredContent") is not None: parts.append(json.dumps(res["structuredContent"], ensure_ascii=False))
        out = "\n".join(parts).strip() or "(sem saida)"
        if len(out) > MAX_RESULT: out = out[:MAX_RESULT] + f"\n...[cortado, {len(out) - MAX_RESULT} caracteres omitidos]"
        return ("Erro: " + out) if res.get("isError") else out

# ---------------------------------------------------------------- varios servidores
_servers = {}      # nome -> Server
_lock = threading.RLock()

def parse_config(obj):
    """Aceita {"mcpServers": {...}} (o formato do Claude Desktop) ou direto {"nome": {...}}. Devolve {nome: {command, args, env, cwd, enabled}}."""
    if isinstance(obj, str):
        try: obj = json.loads(obj)
        except ValueError as e: raise ValueError(f"JSON invalido: {e}")
    if not isinstance(obj, dict): raise ValueError("o JSON precisa ser um objeto")
    obj = obj.get("mcpServers", obj)
    if not isinstance(obj, dict): raise ValueError("\"mcpServers\" precisa ser um objeto")
    out = {}
    for name, c in obj.items():
        if not isinstance(c, dict): raise ValueError(f"\"{name}\": precisa ser um objeto com \"command\"")
        if c.get("url") and not c.get("command"): raise ValueError(f"\"{name}\": servidores MCP por URL (HTTP) ainda nao sao suportados; use um servidor com \"command\" (stdio)")
        if not str(c.get("command") or "").strip(): raise ValueError(f"\"{name}\": falta o \"command\"")
        args = c.get("args") or []
        if not isinstance(args, list): raise ValueError(f"\"{name}\": \"args\" precisa ser uma lista")
        env = c.get("env") or {}
        if not isinstance(env, dict): raise ValueError(f"\"{name}\": \"env\" precisa ser um objeto")
        out[str(name)[:40]] = {"command": str(c["command"]).strip(), "args": [str(a) for a in args], "env": {str(k): str(v) for k, v in env.items()}, **({"cwd": str(c["cwd"])} if c.get("cwd") else {}), "enabled": c.get("enabled", True) is not False}
    return out

def to_json(configs):
    return json.dumps({"mcpServers": {n: {k: v for k, v in c.items() if not (k == "enabled" and v) and not (k in ("args", "env") and not v)} for n, c in (configs or {}).items()}}, ensure_ascii=False, indent=2)

def sync(configs, wait=False):
    """Deixa os servidores rodando iguais a configuracao: para os que sumiram ou mudaram e inicia os novos (em segundo plano)."""
    threads = []
    with _lock:
        for name in list(_servers):
            s = _servers[name]; c = configs.get(name)
            if not c or not c.get("enabled", True) or s.cfg != c: s.stop(); del _servers[name]
        for name, c in (configs or {}).items():
            if not c.get("enabled", True) or name in _servers: continue
            s = Server(name, c); _servers[name] = s
            t = threading.Thread(target=s.start, daemon=True); t.start(); threads.append(t)
    if wait:
        for t in threads: t.join(START_TIMEOUT + 5)

def stop_all():
    with _lock:
        for s in _servers.values(): s.stop()
        _servers.clear()

def status(configs=None):
    with _lock:
        out = []
        for name, c in (configs or {}).items():
            s = _servers.get(name)
            out.append({"name": name, "enabled": c.get("enabled", True), "command": (c.get("command", "") + " " + " ".join(c.get("args", []))).strip()[:160],
                        "state": "off" if not s else "starting" if s.starting else "ready" if s.ready else "error",
                        "tools": [t["name"] for t in (s.tools if s else [])], "error": (s.error if s else "")})
        return out

def _safe(s): return re.sub(r"\W+", "_", str(s)).strip("_") or "x"

def tool_defs():
    """Ferramentas de todos os servidores prontos: [{full, server, tool, description, schema}] (o nome completo e mcp__servidor__ferramenta)."""
    out = []
    with _lock:
        for sname, s in _servers.items():
            if not s.ready: continue
            for t in s.tools:
                full = f"mcp__{_safe(sname)}__{_safe(t['name'])}"
                if len(full) > 64: full = full[:55] + "_" + hashlib.md5(full.encode()).hexdigest()[:8]
                out.append({"full": full, "server": sname, "tool": t["name"], "description": str(t.get("description") or "")[:400], "schema": t.get("inputSchema") if isinstance(t.get("inputSchema"), dict) else {"type": "object", "properties": {}}})
    return out

def find_tool(full):
    for d in tool_defs():
        if d["full"] == full: return d
    return None

def call_full(full, args):
    d = find_tool(full)
    if not d: return "Erro: ferramenta MCP desconhecida (ou o servidor nao esta rodando): " + str(full)
    with _lock: s = _servers.get(d["server"])
    if not s or not s.ready: return f"Erro: o servidor MCP \"{d['server']}\" nao esta pronto."
    try: return s.call(d["tool"], args)
    except McpError as e: return "Erro: " + str(e)
    except Exception as e: return f"Erro: {type(e).__name__}: {e}"

def signature(schema):
    """Resumo curto dos argumentos para o prompt de texto: {"a": "string", "b?": "number"}."""
    props = (schema or {}).get("properties") or {}; req = set((schema or {}).get("required") or [])
    return "{" + ", ".join(f'"{k}{"" if k in req else "?"}": "{(v.get("type") if isinstance(v, dict) else "") or "any"}"' for k, v in list(props.items())[:12]) + "}"

def prompt_lines(lang="pt"):
    d = tool_defs()
    if not d: return ""
    head = ("Ferramentas de servidores MCP (programas externos que o dono ligou; pedem permissao). Argumentos com ? sao opcionais:\n" if lang != "en" else "Tools from MCP servers (external programs the owner turned on; they ask permission). Arguments with ? are optional:\n")
    return head + "\n".join(f"- {x['full']} {signature(x['schema'])} : {x['description'].splitlines()[0][:200] if x['description'] else x['tool']}" for x in d[:60]) + "\n"

def native_tools():
    """Formato de ferramentas nativas (OpenAI) para os modelos que aceitam."""
    return [{"type": "function", "function": {"name": x["full"], "description": (x["description"] or x["tool"])[:400], "parameters": x["schema"]}} for x in tool_defs()[:60]]
