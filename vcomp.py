"""Controle do computador em SEGUNDO PLANO (so Windows): a IA usa ate 3 programas ao mesmo tempo sem encostar no mouse e no teclado do dono.
- ver: PrintWindow tira a foto da janela mesmo que outra esteja na frente (nao traz a janela para frente);
- agir: manda as mensagens de mouse/teclado direto para a janela (PostMessage), entao o mouse de verdade nao se mexe;
- a IA controla UM programa por vez (as fotos podem ser de todos); o "mouse virtual" e uma bolinha transparente, sem clique, que desliza ate o ponto.
Limites: jogos, programas "elevados" (administrador) e alguns apps modernos ignoram mensagens enviadas assim; atalhos com Ctrl/Alt nao valem em segundo plano."""
import base64, ctypes, io, queue, shutil, subprocess, sys, threading, time
from ctypes import wintypes

MAX_APPS = 3
SLOT_COLORS = [(66, 133, 244), (52, 168, 83), (251, 140, 0)]   # a bolinha muda de cor conforme o programa (1, 2, 3)

if sys.platform == "win32":
    u32, g32 = ctypes.windll.user32, ctypes.windll.gdi32
    class POINT(ctypes.Structure): _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    def _sig(fn, res, *args): fn.restype = res; fn.argtypes = list(args)
    H = ctypes.c_void_p
    _sig(u32.GetWindowRect, wintypes.BOOL, H, ctypes.POINTER(wintypes.RECT)); _sig(u32.GetClientRect, wintypes.BOOL, H, ctypes.POINTER(wintypes.RECT))
    _sig(u32.PrintWindow, wintypes.BOOL, H, H, wintypes.UINT); _sig(u32.GetDC, H, H); _sig(u32.ReleaseDC, ctypes.c_int, H, H)
    _sig(u32.ScreenToClient, wintypes.BOOL, H, ctypes.POINTER(POINT)); _sig(u32.RealChildWindowFromPoint, H, H, POINT)
    _sig(u32.PostMessageW, wintypes.BOOL, H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    _sig(u32.SendMessageTimeoutW, wintypes.LPARAM, H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM, wintypes.UINT, wintypes.UINT, ctypes.c_void_p)
    _sig(u32.IsWindow, wintypes.BOOL, H); _sig(u32.IsIconic, wintypes.BOOL, H); _sig(u32.IsWindowVisible, wintypes.BOOL, H); _sig(u32.ShowWindow, wintypes.BOOL, H, ctypes.c_int)
    _sig(u32.GetWindowTextLengthW, ctypes.c_int, H); _sig(u32.GetWindowTextW, ctypes.c_int, H, wintypes.LPWSTR, ctypes.c_int); _sig(u32.GetWindowThreadProcessId, wintypes.DWORD, H, ctypes.c_void_p)
    _sig(g32.CreateCompatibleDC, H, H); _sig(g32.CreateCompatibleBitmap, H, H, ctypes.c_int, ctypes.c_int); _sig(g32.SelectObject, H, H, H); _sig(g32.DeleteObject, wintypes.BOOL, H); _sig(g32.DeleteDC, wintypes.BOOL, H)
    _sig(g32.GetDIBits, ctypes.c_int, H, H, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
    _sig(g32.CreateDIBSection, H, H, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), H, wintypes.DWORD)
    _sig(u32.CreateWindowExW, H, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, H, H, H, H)
    _sig(u32.UpdateLayeredWindow, wintypes.BOOL, H, H, ctypes.c_void_p, ctypes.c_void_p, H, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
    _sig(u32.PeekMessageW, wintypes.BOOL, ctypes.c_void_p, H, wintypes.UINT, wintypes.UINT, wintypes.UINT); _sig(u32.DispatchMessageW, ctypes.c_ssize_t, ctypes.c_void_p); _sig(u32.DestroyWindow, wintypes.BOOL, H)
    try: ctypes.windll.dwmapi.DwmGetWindowAttribute.argtypes = [H, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    except Exception: pass

_apps = []                  # ate 3: {"hwnd", "title", "scale", "shot"}
_lock = threading.RLock()
_last_child = {}            # hwnd da janela -> ultimo filho clicado (onde o texto vai cair)

# ---------------------------------------------------------------- janelas
def _title(h):
    n = u32.GetWindowTextLengthW(h)
    if not n: return ""
    b = ctypes.create_unicode_buffer(n + 1); u32.GetWindowTextW(h, b, n + 1); return b.value

def _cloaked(h):
    v = wintypes.DWORD(0)
    try: ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 14, ctypes.byref(v), 4)
    except Exception: return False
    return bool(v.value)

def list_windows():
    """Janelas visiveis com titulo: [(hwnd, titulo, (l, t, r, b))]."""
    out = []
    EP = ctypes.WINFUNCTYPE(ctypes.c_bool, H, wintypes.LPARAM)
    def cb(h, _):
        if u32.IsWindowVisible(h) and not _cloaked(h):
            t = _title(h)
            if t and t != "Program Manager":
                r = wintypes.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
                if (r.right - r.left > 50 and r.bottom - r.top > 50) or u32.IsIconic(h): out.append((h, t, (r.left, r.top, r.right, r.bottom)))
        return True
    u32.EnumWindows(EP(cb), 0); return out

def _find(title):
    low = title.lower(); m = [w for w in list_windows() if low in w[1].lower()]
    return max(m, key=lambda w: (w[2][2] - w[2][0]) * (w[2][3] - w[2][1])) if m else None

def windows_text():
    ws = list_windows()
    if not ws: return "Nenhuma janela aberta encontrada."
    return "Janelas abertas:\n" + "\n".join(f"- {t[:90]}" for _, t, _ in ws[:40])

def workspace():
    with _lock:
        _apps[:] = [a for a in _apps if u32.IsWindow(a["hwnd"])]; return list(_apps)

def _label(i): return f"app {i + 1}: \"{_apps[i]['title'][:60]}\""

def use_apps(names):
    """Define os (ate 3) programas com que a IA trabalha. Devolve o texto para a IA."""
    if isinstance(names, str): names = [names]
    names = [str(n).strip() for n in (names or []) if str(n).strip()]
    if not names: return "Erro: diga em \"apps\" os titulos (ou parte do titulo) dos programas. Use list_windows para ver os abertos."
    if len(names) > MAX_APPS: return f"Erro: so da para usar {MAX_APPS} programas ao mesmo tempo."
    new = []
    for n in names:
        w = _find(n)
        if not w: return f"Erro: nenhuma janela com \"{n}\" no titulo. Use list_windows para ver os abertos."
        if all(w[0] != x["hwnd"] for x in new): new.append({"hwnd": w[0], "title": w[1], "scale": 1.0, "shot": False})
    with _lock: _apps[:] = new
    return "Programas em uso:\n" + "\n".join("- " + _label(i) for i in range(len(new))) + "\nTire um screenshot ({\"app\": \"all\"} ou {\"app\": 1}) antes de clicar. Voce controla UM programa por vez (diga \"app\": numero em cada acao)."

def _slot(spec, auto_add=True):
    """app numero (1-3) ou titulo -> indice no _apps (adiciona o titulo se couber)."""
    ws = workspace()
    s = str(spec if spec is not None else "").strip()
    if s.isdigit():
        i = int(s) - 1
        if 0 <= i < len(ws): return i
        raise RuntimeError(f"nao existe o app {s}. Use use_apps primeiro (maximo {MAX_APPS}).")
    if not s:
        if len(ws) == 1: return 0
        raise RuntimeError("diga qual programa: \"app\": 1, 2 ou 3 (veja use_apps).")
    w = _find(s)
    if not w: raise RuntimeError(f"nenhuma janela com \"{s}\" no titulo.")
    for i, a in enumerate(ws):
        if a["hwnd"] == w[0]: return i
    if not auto_add or len(ws) >= MAX_APPS: raise RuntimeError(f"ja ha {MAX_APPS} programas em uso; troque a lista com use_apps.")
    with _lock: _apps.append({"hwnd": w[0], "title": w[1], "scale": 1.0, "shot": False}); return len(_apps) - 1

# ---------------------------------------------------------------- abrir e fechar programas (.exe: jogos, DOSBox, VirtualBox...)
_launched = {}   # hwnd -> Popen: so os programas que o Lume abriu podem ser encerrados a forca
_RUNNABLE = (".exe", ".com", ".bat", ".cmd")

def _pid_of(h):
    pid = wintypes.DWORD(0); u32.GetWindowThreadProcessId(h, ctypes.byref(pid)); return pid.value

def launch(path, args=None, wait=15):
    """Abre um programa e espera a janela dele aparecer. Devolve o texto para a IA (e ja poe a janela entre os programas em uso, se couber)."""
    import os as _os
    p = str(path or "").strip().strip('"')
    if not p: return "Erro: diga o programa em \"path\" (caminho do .exe ou o nome, ex.: dosbox)."
    exe = p if _os.path.isfile(p) else (shutil.which(p) or "")
    if not exe or not _os.path.isfile(exe): return f"Erro: nao encontrei o programa \"{p}\". Use o caminho completo do .exe."
    ext = _os.path.splitext(exe)[1].lower()
    if ext not in _RUNNABLE: return f"Erro: so abro {', '.join(_RUNNABLE)} (isto e {ext or 'sem extensao'})."
    argv = [str(a) for a in (args or [])]
    before = {w[0] for w in list_windows()}
    try:
        cmd = ["cmd", "/c", exe] + argv if ext in (".bat", ".cmd") else [exe] + argv
        proc = subprocess.Popen(cmd, cwd=_os.path.dirname(exe) or None, creationflags=0x00000010 if ext in (".bat", ".cmd") else 0)   # 0x10 = janela de console propria p/ .bat
    except Exception as e: return f"Erro ao abrir: {e}"
    wait = max(2, min(60, int(wait or 15))); t0 = time.time(); found = None
    while time.time() - t0 < wait:
        time.sleep(0.4)
        cand = [w for w in list_windows() if w[0] not in before or _pid_of(w[0]) == proc.pid]
        if cand: found = max(cand, key=lambda w: (w[2][2] - w[2][0]) * (w[2][3] - w[2][1])); time.sleep(0.6); break
        if proc.poll() is not None and proc.returncode not in (0, None) and not cand: return f"Erro: o programa fechou logo ao abrir (codigo {proc.returncode})."
    if not found:
        return f"Abri {_os.path.basename(exe)} (pid {proc.pid}), mas nenhuma janela apareceu em {wait} s. Pode ser um programa sem janela, ou ainda carregando: use list_windows daqui a pouco."
    h, title, _ = found; _launched[h] = proc
    with _lock:
        ws = workspace()
        if all(a["hwnd"] != h for a in ws) and len(ws) < MAX_APPS: _apps.append({"hwnd": h, "title": title, "scale": 1.0, "shot": False}); slot = len(_apps)
        else: slot = next((i + 1 for i, a in enumerate(ws) if a["hwnd"] == h), 0)
    return f"Abri {_os.path.basename(exe)}. Janela: \"{title[:80]}\"" + (f" = app {slot}. Tire um screenshot dele antes de agir." if slot else f". Ja ha {MAX_APPS} programas em uso: troque a lista com use_apps para controlar este.")

def close(spec, force=False):
    i = _slot(spec, auto_add=False); a = _apps[i]; h = a["hwnd"]; name = _label(i)
    _post(h, 0x0010, 0, 0)   # WM_CLOSE: pede para fechar do jeito normal (o programa pode perguntar se quer salvar)
    for _ in range(25):
        time.sleep(0.2)
        if not u32.IsWindow(h): break
    msg = f"Pedi para fechar o {name}."
    p = _launched.get(h)
    if u32.IsWindow(h):
        if force and p and p.poll() is None:
            try: p.terminate(); msg += " Nao fechou sozinho: encerrei o processo que o Lume abriu."
            except Exception as e: msg += f" Nao consegui encerrar: {e}"
        else: msg += " A janela continua aberta (talvez esteja perguntando algo, como salvar). Veja com um screenshot." + (" Use \"force\": true para encerrar o processo." if p else "")
    else: msg += " Fechou."
    _launched.pop(h, None); return msg

def activate(spec):
    """Traz a janela do programa para a frente (para os que so aceitam teclado/mouse de verdade: jogos, DOSBox, janelas Tk). Devolve o hwnd."""
    i = _slot(spec, auto_add=False); h = _apps[i]["hwnd"]
    if u32.IsIconic(h): u32.ShowWindow(h, 9)
    fg = u32.GetForegroundWindow(); me = ctypes.windll.kernel32.GetCurrentThreadId(); t1 = u32.GetWindowThreadProcessId(fg, None) if fg else 0
    if t1 and t1 != me: u32.AttachThreadInput(me, t1, True)   # o Windows so deixa trocar o foco quem esta ligado a thread da janela da frente
    try: u32.BringWindowToTop(h); u32.SetForegroundWindow(h)
    finally:
        if t1 and t1 != me: u32.AttachThreadInput(me, t1, False)
    time.sleep(0.35)
    if u32.GetForegroundWindow() != h: raise RuntimeError("o Windows nao deixou trazer o programa para a frente")
    return h

def screen_point(spec, x, y):
    i, a = _target(spec); return _screen_pt(a, x, y)

# ---------------------------------------------------------------- take_screenshot: print de UM alvo pelo nome do app, titulo, exe, PID ou a tela inteira
NOTE = {}   # aviso para o chat quando o alvo pedido nao existe e outro parecido foi usado: {"pt": ..., "en": ...}
def pop_note():
    n = dict(NOTE); NOTE.clear(); return n

def _exe_of(pid):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
        if not h: return ""
        try:
            buf = ctypes.create_unicode_buffer(520); size = wintypes.DWORD(520)
            return os_basename(buf.value) if ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) else ""
        finally: ctypes.windll.kernel32.CloseHandle(h)
    except Exception: return ""
def os_basename(p): return str(p).replace("/", "\\").split("\\")[-1]

def windows_info():
    """Janelas visiveis com titulo: [{hwnd, title, pid, exe, area}]."""
    out = []
    for h, t, r in list_windows():
        pid = _pid_of(h); out.append({"hwnd": h, "title": t, "pid": pid, "exe": _exe_of(pid), "area": max(0, (r[2] - r[0]) * (r[3] - r[1]))})
    return out

_DESK = ("", "desktop", "tela", "tela inteira", "screen", "full", "fullscreen", "all", "todos", "area de trabalho", "monitor")
def resolve_target(target):
    """Acha a janela do alvo. Devolve (info | None, nota_ou_None, candidatos). A nota diz quando foi usado um alvo PARECIDO (ex.: Roblox.exe -> RobloxPlayerBeta.exe)."""
    import difflib, re as _re
    t = str(target or "").strip().strip("\"'"); low = t.lower(); infos = windows_info(); big = lambda l: max(l, key=lambda w: w["area"]) if l else None
    if low.isdigit():
        hit = [w for w in infos if w["pid"] == int(low)]
        return (big(hit), None, infos) if hit else (None, None, infos)
    stem = low[:-4] if low.endswith(".exe") else low
    is_exe = low.endswith(".exe") or bool(_re.fullmatch(r"[\w.\-]+\.exe", low))
    exact_exe = [w for w in infos if w["exe"].lower() == low or (not is_exe and w["exe"].lower() == stem + ".exe")]
    if exact_exe: return big(exact_exe), None, infos
    exact_title = [w for w in infos if w["title"].lower() == low]
    if exact_title: return big(exact_title), None, infos
    in_title = [w for w in infos if low and low in w["title"].lower()]
    if in_title and not is_exe: return big(in_title), None, infos
    like_exe = [w for w in infos if stem and (stem in w["exe"].lower()[:-4] or (len(w["exe"]) > 4 and w["exe"].lower()[:-4] in stem))]
    if like_exe:   # "Roblox.exe" nao existe, mas "RobloxPlayerBeta.exe" sim
        best = sorted(like_exe, key=lambda w: (not w["exe"].lower().startswith(stem), len(w["exe"])))[0]["exe"]; w = big([x for x in like_exe if x["exe"] == best])
        return w, (t, w["exe"]), infos
    if in_title: return big(in_title), (t, in_title[0]["title"]) if is_exe else None, infos
    names = {}; [names.setdefault(w["exe"][:-4].lower() if w["exe"].lower().endswith(".exe") else w["exe"].lower(), w) for w in infos if w["exe"]]
    [names.setdefault(w["title"].lower(), w) for w in infos]
    close = difflib.get_close_matches(stem, list(names), n=1, cutoff=0.8)   # so erro de digitacao (chromee -> chrome); nada de trocar um app por outro so parecido
    if close: w = names[close[0]]; return w, (t, w["exe"] or w["title"]), infos
    return None, None, infos

# ---- categorias ("browser", "terminal"...) e navegadores pelo nome: exe -> (nome de verdade, familia)
BROWSERS = {"chrome.exe": ("Google Chrome", "chromium"), "msedge.exe": ("Microsoft Edge", "chromium"), "comet.exe": ("Comet", "chromium"), "brave.exe": ("Brave", "chromium"), "opera.exe": ("Opera", "chromium"),
            "vivaldi.exe": ("Vivaldi", "chromium"), "chromium.exe": ("Chromium", "chromium"), "arc.exe": ("Arc", "chromium"), "browser.exe": ("Yandex Browser", "chromium"), "duckduckgo.exe": ("DuckDuckGo", "chromium"),
            "firefox.exe": ("Firefox", "gecko"), "librewolf.exe": ("LibreWolf", "gecko"), "waterfox.exe": ("Waterfox", "gecko"), "zen.exe": ("Zen", "gecko"), "iexplore.exe": ("Internet Explorer", "trident")}
BROWSER_WORDS = {"chrome": "chrome.exe", "google chrome": "chrome.exe", "googlechrome": "chrome.exe", "edge": "msedge.exe", "msedge": "msedge.exe", "microsoft edge": "msedge.exe", "comet": "comet.exe", "brave": "brave.exe", "opera": "opera.exe",
                 "vivaldi": "vivaldi.exe", "chromium": "chromium.exe", "arc": "arc.exe", "yandex": "browser.exe", "firefox": "firefox.exe", "mozilla": "firefox.exe", "mozilla firefox": "firefox.exe", "librewolf": "librewolf.exe", "waterfox": "waterfox.exe", "zen": "zen.exe"}
CATEGORIES = {
    ("browser", "browsers", "navegador", "navegadores", "web browser"): ("navegador", set(BROWSERS)),
    ("terminal", "terminais", "console", "shell", "prompt"): ("terminal", {"windowsterminal.exe", "wt.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "conhost.exe", "alacritty.exe", "wezterm-gui.exe", "mintty.exe", "conemu64.exe", "conemu.exe", "hyper.exe", "tabby.exe", "kitty.exe"}),
    ("editor", "ide", "code editor", "editor de codigo"): ("editor de codigo", {"code.exe", "cursor.exe", "windsurf.exe", "notepad++.exe", "notepad.exe", "sublime_text.exe", "devenv.exe", "pycharm64.exe", "idea64.exe", "zed.exe"}),
    ("explorer", "file manager", "arquivos", "gerenciador de arquivos", "files"): ("explorador de arquivos", {"explorer.exe", "filepilot.exe", "files.exe"}),
    ("chat", "messenger", "mensagens"): ("chat", {"discord.exe", "telegram.exe", "whatsapp.exe", "slack.exe", "ms-teams.exe", "teams.exe", "signal.exe"}),
}
CAT_MAX = 3   # no maximo 3 prints por pedido de categoria (a IA recebe as 3 imagens mais recentes)

def _friendly(w):
    return BROWSERS.get(w["exe"].lower(), (None,))[0] or (w["exe"][:-4] if w["exe"].lower().endswith(".exe") else w["exe"]) or w["title"][:40]

def resolve_group(target, infos):
    """"browser"/"terminal"/... ou um navegador pelo nome. Devolve (janelas, rotulo, aviso_ou_None) ou None se nao for um grupo.
    Um navegador pedido que NAO esta aberto mas e da mesma familia de outro que esta (chrome -> comet) devolve o aberto, com um aviso que diz o nome verdadeiro."""
    low = str(target or "").strip().strip("\"'").lower(); low = low[:-4] if low.endswith(".exe") else low
    def pick(exes, skip_titles=("Program Manager",)):
        best = {}
        for w in infos:
            if w["exe"].lower() in exes and w["title"] not in skip_titles and (w["exe"].lower() not in best or w["area"] > best[w["exe"].lower()]["area"]): best[w["exe"].lower()] = w
        return sorted(best.values(), key=lambda w: -w["area"])[:CAT_MAX]
    for words, (label, exes) in CATEGORIES.items():
        if low in words:
            ws = pick(exes)
            if ws: return ws, label, None
            return [], label, None
    req = BROWSER_WORDS.get(low)
    if req:
        have = pick({req})
        if have: return have, BROWSERS[req][0], None
        fam = BROWSERS[req][1]; alt = pick({e for e, (_, f) in BROWSERS.items() if f == fam})
        if alt:
            names = " e ".join(_friendly(w) for w in alt); rq = BROWSERS[req][0]
            warn = f'ATENCAO: o {rq} NAO esta aberto. O navegador aberto e o {names} (baseado em {fam.capitalize()}, como o {rq}). Chame-o de {names}, NUNCA de {rq}: o {rq} nao foi detectado.'
            return alt, names, (rq, names, warn)
    return None

def take_screenshot(target, include_overlay=False, hide_overlay=None, show_overlay=None):
    """Print de UM alvo (ou de varios, se for uma categoria como "browser"). Devolve (texto, [jpeg_base64]). Define NOTE se usou um alvo parecido."""
    from PIL import ImageGrab
    NOTE.clear(); t = str(target or "").strip().strip("\"'"); desk = t.lower() in _DESK
    def pack(img, where):
        W, H = img.size; k = min(1.0, 1280 / max(W, H))
        if k < 1: img = img.resize((int(W * k), int(H * k)))
        b = io.BytesIO(); img.convert("RGB").save(b, "JPEG", quality=72); return f"Captura de {where}: {img.size[0]}x{img.size[1]} pixels.", [base64.b64encode(b.getvalue()).decode()]
    if desk:
        hid = False
        try:
            if hide_overlay and not include_overlay: hid = bool(hide_overlay()); time.sleep(0.25 if hid else 0)   # a caixa do Alt+Espaco some um instante para nao sair no print
            img = ImageGrab.grab(all_screens=True)
        finally:
            if hid and show_overlay: show_overlay()
        txt, imgs = pack(img, "a area de trabalho inteira" + (" (com a caixa do Alt+Espaco)" if include_overlay else "")); return txt, imgs
    def shoot(w):
        try: img = _capture(w["hwnd"])
        except Exception:   # PrintWindow falhou (ex.: foto preta): tenta a area da janela na tela
            r = wintypes.RECT(); u32.GetWindowRect(w["hwnd"], ctypes.byref(r)); img = ImageGrab.grab(bbox=(max(0, r.left), max(0, r.top), r.right, r.bottom), all_screens=True)
        return pack(img, f"{_friendly(w)} - \"{w['title'][:60]}\" ({w['exe'] or 'PID ' + str(w['pid'])}, PID {w['pid']})")
    infos = windows_info(); grp = resolve_group(t, infos)
    if grp is not None:
        ws, label, sub = grp
        if not ws:
            lst = "\n".join(f"- {x['title'][:60]} ({x['exe'] or '?'}, PID {x['pid']})" for x in sorted(infos, key=lambda x: -x["area"])[:15])
            return f"Erro: nenhum {label} aberto agora. Abertos:\n{lst}\nTente um desses ou use target=\"desktop\".", []
        texts, imgs = [], []
        for w in ws:
            try: tx, im = shoot(w); texts.append(tx); imgs += im
            except Exception as e: texts.append(f"Falhou em {_friendly(w)}: {e}")
        head = (f"{len(ws)} janelas de {label} abertas ({', '.join(_friendly(w) for w in ws)}): um print de cada, na mesma ordem." if len(ws) > 1 else f"Aberto agora ({label}): {_friendly(ws[0])}." if label == "navegador" else "")
        if sub:
            head = (sub[2] + " " + head).strip()
            NOTE.update({"pt": f'A IA tentou tirar print do {sub[0]}, mas o {sub[0]} nao esta aberto; so o {sub[1]} esta. Tirando print do {sub[1]}...', "en": f'The AI tried to take a screenshot of {sub[0]} but {sub[0]} is not open; only {sub[1]} is. Taking a screenshot of {sub[1]}...'})
        return (head + "\n" if head else "") + "\n".join(texts), imgs
    w, sub, infos = resolve_target(t)
    if not w:
        lst = "\n".join(f"- {x['title'][:60]} ({x['exe'] or '?'}, PID {x['pid']})" for x in sorted(infos, key=lambda x: -x["area"])[:15])
        return f"Erro: nao achei nenhum app, janela, exe ou PID parecido com \"{t}\". Abertos agora:\n{lst}\nTente um desses ou use target=\"desktop\".", []
    if sub: NOTE.update({"pt": f'A IA tentou tirar print de "{sub[0]}", mas so achou "{sub[1]}"; tirando print de {sub[1]}...', "en": f'The AI tried to take a screenshot of "{sub[0]}" but only "{sub[1]}" was found; taking a screenshot of {sub[1]}...'})
    txt, imgs = shoot(w)
    if sub: txt += f" Voce pediu \"{sub[0]}\", mas so existe \"{sub[1]}\": e dele este print."
    return txt, imgs

# ---------------------------------------------------------------- ver (PrintWindow)
def _capture(hwnd):
    from PIL import Image
    if u32.IsIconic(hwnd): u32.ShowWindow(hwnd, 4); time.sleep(0.35)   # minimizada: volta sem tomar o foco (a foto de uma janela minimizada vem vazia)
    r = wintypes.RECT(); u32.GetWindowRect(hwnd, ctypes.byref(r)); w, h = r.right - r.left, r.bottom - r.top
    if w < 20 or h < 20: raise RuntimeError("a janela esta pequena demais para fotografar")
    sdc = u32.GetDC(None); mdc = g32.CreateCompatibleDC(sdc); bmp = g32.CreateCompatibleBitmap(sdc, w, h); old = g32.SelectObject(mdc, bmp)
    try:
        ok = u32.PrintWindow(hwnd, mdc, 2)   # 2 = PW_RENDERFULLCONTENT (pega tambem navegadores e apps modernos)
        g32.SelectObject(mdc, old)
        class BIH(ctypes.Structure): _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD), ("a", ctypes.c_long), ("b", ctypes.c_long), ("c", wintypes.DWORD), ("d", wintypes.DWORD)]
        bi = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4); g32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    finally:
        g32.DeleteObject(bmp); g32.DeleteDC(mdc); u32.ReleaseDC(None, sdc)
    if not ok: raise RuntimeError("o Windows nao deixou fotografar essa janela")
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    if img.getextrema() == ((0, 0), (0, 0), (0, 0)): raise RuntimeError("a foto veio preta (esse programa nao deixa ser fotografado em segundo plano)")
    return img

def screenshot(which):
    """which: "all", numero, titulo ou lista deles. Devolve (texto, [jpeg_base64...])."""
    ws = workspace()
    if isinstance(which, (list, tuple)): specs = list(which)
    elif str(which).strip().lower() in ("all", "todos", "todas", "*", ""): specs = list(range(1, len(ws) + 1))
    else: specs = [which]
    if not specs: return "Erro: nenhum programa em uso. Use use_apps primeiro.", []
    idx = []
    for s in specs:
        i = _slot(s)
        if i not in idx: idx.append(i)
    texts, imgs = [], []
    for n, i in enumerate(idx):
        a = _apps[i]
        try: img = _capture(a["hwnd"])
        except Exception as e: texts.append(f"{_label(i)}: erro: {e}"); continue
        W, Hh = img.size; k = min(1.0, 1280 / max(W, Hh)); a["scale"] = k; a["shot"] = True
        if k < 1: img = img.resize((int(W * k), int(Hh * k)))
        b = io.BytesIO(); img.save(b, "JPEG", quality=70); imgs.append(base64.b64encode(b.getvalue()).decode())
        texts.append(f"Imagem {len(imgs)} = {_label(i)}, {img.size[0]}x{img.size[1]} pixels")
    head = "Capturas feitas em segundo plano (sem mexer nas suas janelas):\n" if imgs else ""
    return head + "\n".join(texts) + ("\nAs coordenadas x,y de cada app sao medidas na imagem DELE (canto superior esquerdo = 0,0)." if imgs else ""), imgs

# ---------------------------------------------------------------- agir (mensagens de janela)
WM = {"move": 0x200, "ldown": 0x201, "lup": 0x202, "ldbl": 0x203, "rdown": 0x204, "rup": 0x205, "mdown": 0x207, "mup": 0x208, "wheel": 0x20A, "keydown": 0x100, "keyup": 0x101, "char": 0x102, "activate": 0x6, "setfocus": 0x7}
def _lp(x, y): return ((int(y) & 0xFFFF) << 16) | (int(x) & 0xFFFF)
def _post(h, msg, wp, lp):
    if not u32.PostMessageW(h, msg, wp, lp): raise RuntimeError("o programa nao aceitou a mensagem (talvez rode como administrador)")

def _send(h, msg, wp, lp):   # sincrona (espera o programa tratar): a rolagem do Chromium confere o que esta sob o ponto na hora de tratar, entao a bolinha so aparece depois
    if not u32.SendMessageTimeoutW(h, msg, wp, lp, 2, 1500, None): raise RuntimeError("o programa nao respondeu a tempo")

def _target(spec, need_shot=True):
    i = _slot(spec); a = _apps[i]
    if need_shot and not a["shot"]: raise RuntimeError(f"tire um screenshot do {_label(i)} antes (as coordenadas vem dele)")
    return i, a

def _screen_pt(a, x, y):
    r = wintypes.RECT(); u32.GetWindowRect(a["hwnd"], ctypes.byref(r))
    return int(r.left + float(x) / a["scale"]), int(r.top + float(y) / a["scale"])

def _child_at(top, sx, sy):
    h = top
    for _ in range(12):
        p = POINT(sx, sy); u32.ScreenToClient(h, ctypes.byref(p)); c = u32.RealChildWindowFromPoint(h, p)
        if not c or c == h: break
        h = c
    return h

def _wake(top, child):   # faz o programa achar que esta ativo (sem trazer para frente)
    _post(top, WM["activate"], 2, 0); _post(child, WM["setfocus"], 0, 0)

def mouse(name, spec, x, y, button="left", double=False, amount=-3):
    i, a = _target(spec); sx, sy = _screen_pt(a, x, y)
    top = a["hwnd"]; child = _child_at(top, sx, sy); p = POINT(sx, sy); u32.ScreenToClient(child, ctypes.byref(p)); lp = _lp(p.x, p.y)
    _last_child[top] = child
    if name == "scroll":
        _send(child, WM["wheel"], ((int(amount) * 120) & 0xFFFF) << 16, _lp(sx, sy)); ball_go(sx, sy, i, False); return f"Rolei {amount} no {_label(i)} em {x},{y} (em segundo plano)."
    ball_go(sx, sy, i, name == "mouse_click")
    _post(child, WM["move"], 0, lp)
    if name == "mouse_click":
        b = str(button or "left").lower(); down, up, mk = {"left": ("ldown", "lup", 1), "right": ("rdown", "rup", 2), "middle": ("mdown", "mup", 0x10)}.get(b, ("ldown", "lup", 1))
        _wake(top, child); time.sleep(0.03)
        for n in range(2 if double else 1):
            _post(child, WM["ldbl"] if (double and n == 1 and b == "left") else WM[down], mk, lp); time.sleep(0.04); _post(child, WM[up], 0, lp); time.sleep(0.06)
        return f"Cliquei ({b}{', duplo' if double else ''}) no {_label(i)} em {x},{y} (em segundo plano; o seu mouse nao mexeu)."
    return f"Mouse virtual movido no {_label(i)} para {x},{y}."

_VK = {"enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "space": 0x20, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22, "insert": 0x2D,
       "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, **{f"f{n}": 0x6F + n for n in range(1, 13)}}
_CHAR_KEYS = {0x0D: 13, 0x09: 9, 0x08: 8, 0x1B: 27, 0x20: 32}   # teclas que tambem geram caractere

def _focus_hwnd(top):
    class GTI(ctypes.Structure): _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD), ("hwndActive", H), ("hwndFocus", H), ("hwndCapture", H), ("hwndMenuOwner", H), ("hwndMoveSize", H), ("hwndCaret", H), ("rc", wintypes.RECT)]
    g = GTI(); g.cbSize = ctypes.sizeof(GTI)
    tid = u32.GetWindowThreadProcessId(top, None)
    if u32.GetGUIThreadInfo(tid, ctypes.byref(g)) and g.hwndFocus: return g.hwndFocus
    return _last_child.get(top) or top

def keyboard(name, spec, text="", key=""):
    i, a = _target(spec, need_shot=False); top = a["hwnd"]
    tgt = _focus_hwnd(top)
    if name == "type_text":
        text = str(text)[:2000]; units = text.replace("\r\n", "\n").encode("utf-16-le")
        for k in range(0, len(units), 2):
            ch = units[k] | (units[k + 1] << 8); _post(tgt, WM["char"], 13 if ch == 10 else ch, 1); time.sleep(0.008)
        return f"Digitei {len(text)} caracteres no {_label(i)} (em segundo plano)."
    keys = [k.strip().lower() for k in str(key).replace(" ", "").split("+") if k.strip()]
    if not keys: return "Erro: diga a tecla em \"key\"."
    vks = []
    for k in keys:
        if k in _VK: vks.append(_VK[k])
        elif len(k) == 1:
            v = ctypes.windll.user32.VkKeyScanW(ord(k)) & 0xFF
            if v == 0xFF: return f"Erro: tecla desconhecida: {k}"
            vks.append(v)
        else: return f"Erro: tecla desconhecida: {k}"
    mods = [v for v in vks if v in (0x11, 0x12, 0x10)]; main = [v for v in vks if v not in mods]
    for v in vks: _post(tgt, WM["keydown"], v, 1 | (u32.MapVirtualKeyW(v, 0) << 16))
    for v in main:
        if v in _CHAR_KEYS and not mods: _post(tgt, WM["char"], _CHAR_KEYS[v], 1)
        elif len(keys) == 1 and len(keys[0]) == 1: _post(tgt, WM["char"], ord(keys[0]), 1)
    for v in reversed(vks): _post(tgt, WM["keyup"], v, 0xC0000001 | (u32.MapVirtualKeyW(v, 0) << 16))
    note = " Atalhos com Ctrl/Alt/Shift podem nao funcionar em segundo plano: confira com um screenshot." if mods else ""
    return f"Apertei {'+'.join(keys)} no {_label(i)} (em segundo plano)." + note

# ---------------------------------------------------------------- o mouse virtual: uma bolinha transparente que nao recebe clique
_ball_q = queue.Queue(); _ball_thread = None
def ball_go(x, y, slot=0, click=False):
    global _ball_thread
    if _ball_thread is None or not _ball_thread.is_alive():
        _ball_thread = threading.Thread(target=_ball_loop, daemon=True); _ball_thread.start()
    _ball_q.put((x, y, slot, click))

def _draw_ball(S, color, ring):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = S // 2
    if ring: d.ellipse([c - ring, c - ring, c + ring, c + ring], outline=color + (170,), width=3)
    d.ellipse([c - 15, c - 15, c + 15, c + 15], fill=color + (215,), outline=(255, 255, 255, 235), width=3)
    d.ellipse([c - 5, c - 5, c + 5, c + 5], fill=(255, 255, 255, 235))
    return im

def _ball_loop():
    S = 72
    class BF(ctypes.Structure): _fields_ = [("op", ctypes.c_ubyte), ("fl", ctypes.c_ubyte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_ubyte)]
    class BIH(ctypes.Structure): _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD), ("a", ctypes.c_long), ("b", ctypes.c_long), ("c", wintypes.DWORD), ("d", wintypes.DWORD)]
    # WS_EX_LAYERED | TRANSPARENT (clique passa direto) | TOPMOST | TOOLWINDOW | NOACTIVATE
    hwnd = u32.CreateWindowExW(0x80000 | 0x20 | 0x8 | 0x80 | 0x08000000, "Static", "LumeBall", 0x80000000, 0, 0, S, S, None, None, None, None)
    if not hwnd: return
    sdc = u32.GetDC(None); mdc = g32.CreateCompatibleDC(sdc); bits = ctypes.c_void_p()
    bi = BIH(ctypes.sizeof(BIH), S, -S, 1, 32, 0, 0, 0, 0, 0, 0); dib = g32.CreateDIBSection(mdc, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0); g32.SelectObject(mdc, dib)
    def paint(x, y, color, ring):
        im = _draw_ball(S, color, ring).convert("RGBa").tobytes("raw", "BGRa"); ctypes.memmove(bits, im, len(im))
        pos = POINT(int(x) - S // 2, int(y) - S // 2); sz = wintypes.SIZE(S, S); src = POINT(0, 0); bf = BF(0, 0, 255, 1)
        u32.UpdateLayeredWindow(hwnd, sdc, ctypes.byref(pos), ctypes.byref(sz), mdc, ctypes.byref(src), 0, ctypes.byref(bf), 2)
    cur = None; shown = False; last = time.time(); msg = ctypes.create_string_buffer(64)
    try:
        while True:
            while u32.PeekMessageW(msg, None, 0, 0, 1): u32.DispatchMessageW(msg)
            try: job = _ball_q.get(timeout=0.2)
            except queue.Empty:
                if shown and time.time() - last > 4: u32.ShowWindow(hwnd, 0); shown = False   # some depois de 4 s parado
                continue
            x, y, slot, click = job; color = SLOT_COLORS[slot % 3]
            if not shown: u32.ShowWindow(hwnd, 4); shown = True; cur = (x, y)
            if cur is None: cur = (x, y)
            for n in range(1, 13):   # desliza ate o ponto (curva suave)
                k = 1 - (1 - n / 12) ** 3; paint(cur[0] + (x - cur[0]) * k, cur[1] + (y - cur[1]) * k, color, 0); time.sleep(0.012)
            cur = (x, y)
            if click:
                for r in (18, 24, 30, 0): paint(x, y, color, r); time.sleep(0.04)
            last = time.time()
    finally:
        try: u32.DestroyWindow(hwnd)
        except Exception: pass
