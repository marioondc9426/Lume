"""Ponte entre o Lume e a EXTENSAO do navegador (pasta browser-extension/): a IA enxerga e usa as abas do navegador que voce ja usa (Comet, Chrome, Edge, Brave, Firefox...), com os seus logins.
A extensao fica pedindo comandos ao Lume (long-poll em 127.0.0.1) e devolve o resultado; aqui so ha a fila, o pareamento e a definicao das ferramentas (que aparecem para a IA como mcp__browser__*)."""
import json, secrets, threading, time, queue

SERVER = "browser"          # nome do "servidor" que a IA ve: mcp__browser__ferramenta
TOKEN = secrets.token_urlsafe(24)   # novo a cada vez que o Lume abre; a extensao pega de novo no pareamento
POLL_SECS = 20              # quanto tempo a extensao espera por um comando antes de perguntar de novo
ALIVE_SECS = 45             # sem pergunta por esse tempo = extensao desconectada (o service worker do Chrome dorme)
CALL_TIMEOUT = 45

_cmds = queue.Queue(); _waiting = {}; _lock = threading.Lock()
_state = {"seen": 0.0, "info": {}}

def ext_origin(origin):
    """So extensoes podem parear (uma pagina da web nao consegue forjar o Origin)."""
    o = str(origin or ""); return o.startswith("chrome-extension://") or o.startswith("moz-extension://")

def pair(origin):
    return TOKEN if ext_origin(origin) else None

def connected(): return time.time() - _state["seen"] < ALIVE_SECS
def info(): return dict(_state["info"], connected=connected(), seen=_state["seen"])

def poll(token, extra=None, timeout=POLL_SECS):
    """A extensao pergunta: ha comando para mim? Devolve {"cmd": {...}} ou {}."""
    if not secrets.compare_digest(str(token or ""), TOKEN): return {"error": "token"}
    _state["seen"] = time.time()
    if isinstance(extra, dict): _state["info"] = {k: str(v)[:80] for k, v in list(extra.items())[:6]}
    try: c = _cmds.get(timeout=timeout)
    except queue.Empty: return {}
    _state["seen"] = time.time(); return {"cmd": c}

def deliver(token, cid, result):
    if not secrets.compare_digest(str(token or ""), TOKEN): return False
    with _lock: slot = _waiting.get(cid)
    if not slot: return False
    slot["result"] = result if isinstance(result, dict) else {"text": str(result)}; slot["ev"].set(); return True

def call(action, args=None, timeout=CALL_TIMEOUT):
    """Manda um comando a extensao e espera. Devolve (texto, [imagens base64])."""
    if not connected(): return ("Erro: a extensao do Lume nao esta conectada ao navegador. Peca ao dono para instalar/ativar a extensao (Configuracoes > App > Navegador) e deixar o navegador aberto."), []
    cid = secrets.token_hex(6); slot = {"ev": threading.Event(), "result": None}
    with _lock: _waiting[cid] = slot
    try:
        _cmds.put({"id": cid, "action": action, "args": args or {}})
        if not slot["ev"].wait(timeout): return f"Erro: o navegador nao respondeu em {timeout}s (a aba pode estar carregando ou a extensao dormiu).", []
        r = slot["result"] or {}
    finally:
        with _lock: _waiting.pop(cid, None)
    if r.get("error"): return "Erro: " + str(r["error"])[:600], []
    txt = str(r.get("text", "")).strip() or "(sem saida)"
    if action in ("tabs", "read_page"):
        who = _who()
        if who: txt = f"Navegador aberto no PC: {who}. Chame-o por esse nome (nao invente outro, como Chrome)." + chr(10) + txt
    if len(txt) > 14000: txt = txt[:14000] + f"\n...[cortado, {len(txt) - 14000} caracteres omitidos]"
    return txt, ([str(r["image"])] if r.get("image") else [])

def _who():
    """Nome(s) do navegador de verdade (a IA costuma chamar tudo de Chrome)."""
    try:
        import vcomp
        names = sorted({vcomp._friendly(w) for w in vcomp.windows_info() if w["exe"].lower() in vcomp.BROWSERS})
        if names: return " e ".join(names)
    except Exception: pass
    return str(_state["info"].get("brand", ""))

_S = lambda props, req=(): {"type": "object", "properties": props, "required": list(req)}
_TAB = {"type": "integer", "description": "id da aba (vem de tabs); se omitido usa a aba ativa"}
TOOLS = [
    ("tabs", "Lista as abas abertas no navegador do dono (id, titulo, endereco, qual esta ativa)", _S({})),
    ("open_url", "Abre um endereco no navegador (nova aba por padrao) e espera carregar", _S({"url": {"type": "string"}, "new_tab": {"type": "boolean", "description": "padrao true"}, "tab_id": _TAB}, ["url"])),
    ("read_page", "Le a pagina: titulo, texto visivel e a lista NUMERADA de botoes, links e campos que da para clicar/digitar (use o numero em click e type). Chame de novo depois de cada acao que muda a pagina", _S({"tab_id": _TAB})),
    ("click", "Clica no elemento de numero N da ultima read_page", _S({"index": {"type": "integer"}, "tab_id": _TAB}, ["index"])),
    ("type", "Digita texto no campo de numero N da ultima read_page (submit=true aperta Enter no fim)", _S({"index": {"type": "integer"}, "text": {"type": "string"}, "submit": {"type": "boolean"}, "tab_id": _TAB}, ["index", "text"])),
    ("scroll", "Rola a pagina", _S({"direction": {"type": "string", "description": "down, up, top ou bottom"}, "tab_id": _TAB})),
    ("screenshot", "Foto da parte visivel da aba (deixa a aba em primeiro plano)", _S({"tab_id": _TAB})),
    ("switch_tab", "Traz uma aba para a frente", _S({"tab_id": {"type": "integer"}}, ["tab_id"])),
    ("close_tab", "Fecha uma aba", _S({"tab_id": {"type": "integer"}}, ["tab_id"])),
    ("back", "Volta uma pagina no historico da aba", _S({"tab_id": _TAB})),
]
DESC_PREFIX = "[Navegador do dono] "

def defs():
    """No mesmo formato de lumemcp.tool_defs(): so aparecem com a extensao conectada."""
    if not connected(): return []
    return [{"full": f"mcp__{SERVER}__{n}", "server": SERVER, "tool": n, "kind": "browser", "description": DESC_PREFIX + d, "schema": s} for n, d, s in TOOLS]
