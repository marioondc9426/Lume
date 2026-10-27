#!/usr/bin/env python3
"""lume-feedback: recebe o que os usuarios mandam pelo app "Lume Feedback" e mostra num dashboardzinho.

    python server.py                      sobe em http://0.0.0.0:8787  (dashboard em /dashboard)
    python server.py --port 9000 --host 127.0.0.1

Senha do dashboard: NAO tem quando o servidor roda so neste PC (--host 127.0.0.1); quando fica exposto na rede (padrao 0.0.0.0) pede senha: variavel FEEDBACK_PASSWORD,
ou uma gerada na primeira vez e guardada em feedback_password.txt. Force com --password ou --no-password.
Chave de envio (opcional): FEEDBACK_KEY; se existir, o app precisa mandar o mesmo valor no cabecalho X-Feedback-Key.
Dados: feedback.db (SQLite) na pasta do servidor (ou FEEDBACK_DATA). So usa a biblioteca padrao do Python."""
import argparse
import base64
import csv
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import sys
import threading
import time
import urllib.parse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("FEEDBACK_DATA") or HERE
DB = os.path.join(DATA, "feedback.db")
MAX_BODY = 3 * 1024 * 1024        # corpo do pedido
MAX_SHOT = 1_500_000              # captura de tela (bytes, ja decodificada)
CATS = ("bug", "sugestao", "outro")
STATUS = ("novo", "lido", "resolvido")
_lock = threading.Lock()
_hits = {}          # ip -> horarios dos ultimos envios (limite por hora)
_login_fail = {}    # ip -> (falhas, ate quando bloqueado)
_sessions = {}      # token -> expira em
NEED_PW = True      # False quando roda so neste PC (ver main)


@contextmanager
def db():
    """Abre o banco, confirma as mudancas e fecha ao sair do bloco."""
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, category TEXT, message TEXT, contact TEXT, app TEXT, version TEXT, os TEXT, ip TEXT, log TEXT, shot BLOB, shot_type TEXT, status TEXT DEFAULT 'novo')""")
        yield c; c.commit()
    finally: c.close()


def password():
    if os.environ.get("FEEDBACK_PASSWORD"): return os.environ["FEEDBACK_PASSWORD"]
    p = os.path.join(DATA, "feedback_password.txt")
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f: f.write(secrets.token_urlsafe(9))
        print("Senha do dashboard (guardada em feedback_password.txt):", open(p, encoding="utf-8").read().strip(), flush=True)
    return open(p, encoding="utf-8").read().strip()


def clip(v, n): return str(v or "").strip()[:n]


def sniff_image(b):
    if b[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if b[:3] == b"\xff\xd8\xff": return "image/jpeg"
    return None


def validate(d):
    """Devolve (campos limpos, erro)."""
    if not isinstance(d, dict): return None, "json invalido"
    msg = clip(d.get("message"), 5000)
    if len(msg) < 3: return None, "escreva pelo menos algumas palavras"
    cat = d.get("category") if d.get("category") in CATS else "outro"
    shot, stype = None, None
    if d.get("screenshot_b64"):
        try: shot = base64.b64decode(str(d["screenshot_b64"]), validate=True)
        except Exception: return None, "imagem invalida"
        stype = sniff_image(shot)
        if not stype or len(shot) > MAX_SHOT: return None, "imagem invalida ou grande demais (PNG/JPEG ate 1,5 MB)"
    return {"category": cat, "message": msg, "contact": clip(d.get("contact"), 120), "app": clip(d.get("app") or "Lume", 40), "version": clip(d.get("version"), 30), "os": clip(d.get("os"), 80), "log": clip(d.get("log"), 20000), "shot": shot, "shot_type": stype}, None


class H(BaseHTTPRequestHandler):
    server_version = "lume-feedback"
    def log_message(self, fmt, *a): sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % a))

    # ---- respostas
    def send(self, code, body, ctype="application/json", headers=None):
        if isinstance(body, (dict, list)): body = json.dumps(body).encode("utf-8")
        elif isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff"); self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)

    def ip(self): return self.client_address[0]
    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY: return None
        return self.rfile.read(n)
    def authed(self):
        if not NEED_PW: return True
        tok = (re.search(r"fb_session=([\w-]+)", self.headers.get("Cookie") or "") or [None, ""])[1]
        return _sessions.get(tok, 0) > time.time()

    # ---- GET
    def do_GET(self):
        u = urllib.parse.urlsplit(self.path); p = u.path; q = urllib.parse.parse_qs(u.query)
        if p == "/": return self.send(302, b"", "text/plain", {"Location": "/dashboard"})
        if p == "/health": return self.send(200, {"ok": True})
        if p == "/dashboard": return self.send(200, DASH, "text/html; charset=utf-8", {"Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"})
        if not p.startswith("/api/admin/"): return self.send(404, {"error": "nao encontrado"})
        if not self.authed(): return self.send(401, {"error": "login"})
        with _lock, db() as c:
            if p == "/api/admin/items":
                where, args = [], []
                if q.get("category", [""])[0] in CATS: where.append("category=?"); args.append(q["category"][0])
                if q.get("status", [""])[0] in STATUS: where.append("status=?"); args.append(q["status"][0])
                s = q.get("q", [""])[0].strip()
                if s: where.append("(message LIKE ? OR contact LIKE ? OR version LIKE ? OR os LIKE ?)"); args += ["%" + s + "%"] * 4
                rows = c.execute("SELECT id, ts, category, message, contact, app, version, os, status, (shot IS NOT NULL) AS has_shot FROM feedback" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT 500", args).fetchall()
                cnt = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM feedback GROUP BY status")}
                return self.send(200, {"items": [dict(r) for r in rows], "counts": cnt})
            m = re.fullmatch(r"/api/admin/item/(\d+)", p)
            if m:
                r = c.execute("SELECT id, ts, category, message, contact, app, version, os, ip, log, status, (shot IS NOT NULL) AS has_shot FROM feedback WHERE id=?", (int(m.group(1)),)).fetchone()
                return self.send(200, dict(r)) if r else self.send(404, {"error": "nao encontrado"})
            m = re.fullmatch(r"/api/admin/shot/(\d+)", p)
            if m:
                r = c.execute("SELECT shot, shot_type FROM feedback WHERE id=?", (int(m.group(1)),)).fetchone()
                return self.send(200, r["shot"], r["shot_type"]) if r and r["shot"] else self.send(404, {"error": "sem imagem"})
            if p == "/api/admin/export.csv":
                out = io.StringIO(); w = csv.writer(out); w.writerow(["id", "data", "categoria", "status", "mensagem", "contato", "app", "versao", "so"])
                for r in c.execute("SELECT * FROM feedback ORDER BY id"): w.writerow([r["id"], time.strftime("%Y-%m-%d %H:%M", time.localtime(r["ts"])), r["category"], r["status"], r["message"], r["contact"], r["app"], r["version"], r["os"]])
                return self.send(200, out.getvalue(), "text/csv; charset=utf-8", {"Content-Disposition": 'attachment; filename="feedback.csv"'})
        return self.send(404, {"error": "nao encontrado"})

    def do_OPTIONS(self):   # o Lume do iPhone manda direto do navegador: libera o envio (CORS)
        self.send(204, b"", "text/plain", {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, X-Feedback-Key", "Access-Control-Max-Age": "86400"})

    # ---- POST / DELETE
    def do_POST(self):
        p = urllib.parse.urlsplit(self.path).path; raw = self.body()
        if raw is None: return self.send(413, {"error": "pedido grande demais"})
        try: d = json.loads(raw or b"{}")
        except ValueError: return self.send(400, {"error": "json invalido"})
        if p == "/api/feedback":   # quem manda (o app): sem login, com limite por hora
            key = os.environ.get("FEEDBACK_KEY")
            if key and not hmac.compare_digest(str(self.headers.get("X-Feedback-Key") or ""), key): return self.send(401, {"error": "chave de envio invalida"})
            now = time.time(); hits = [t for t in _hits.get(self.ip(), []) if now - t < 3600]
            if len(hits) >= 10: return self.send(429, {"error": "muitos envios; tente mais tarde"})
            f, err = validate(d)
            if err: return self.send(400, {"error": err})
            _hits[self.ip()] = hits + [now]
            with _lock, db() as c: cur = c.execute("INSERT INTO feedback (ts, category, message, contact, app, version, os, ip, log, shot, shot_type) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (now, f["category"], f["message"], f["contact"], f["app"], f["version"], f["os"], self.ip(), f["log"], f["shot"], f["shot_type"]))
            return self.send(201, {"ok": True, "id": cur.lastrowid}, headers={"Access-Control-Allow-Origin": "*"})
        if p == "/api/login":
            fails, until = _login_fail.get(self.ip(), (0, 0))
            if until > time.time(): return self.send(429, {"error": "muitas tentativas; espere um pouco"})
            if hmac.compare_digest(str(d.get("password") or ""), password()):
                tok = secrets.token_urlsafe(24); _sessions[tok] = time.time() + 12 * 3600; _login_fail.pop(self.ip(), None)
                return self.send(200, {"ok": True}, headers={"Set-Cookie": f"fb_session={tok}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200"})
            fails += 1; _login_fail[self.ip()] = (fails, time.time() + (60 if fails >= 5 else 0)); time.sleep(0.6)
            return self.send(401, {"error": "senha errada"})
        if not self.authed(): return self.send(401, {"error": "login"})
        m = re.fullmatch(r"/api/admin/item/(\d+)", p)
        if m and d.get("status") in STATUS:
            with _lock, db() as c: c.execute("UPDATE feedback SET status=? WHERE id=?", (d["status"], int(m.group(1))))
            return self.send(200, {"ok": True})
        return self.send(404, {"error": "nao encontrado"})

    def do_DELETE(self):
        if not self.authed(): return self.send(401, {"error": "login"})
        m = re.fullmatch(r"/api/admin/item/(\d+)", urllib.parse.urlsplit(self.path).path)
        if not m: return self.send(404, {"error": "nao encontrado"})
        with _lock, db() as c: c.execute("DELETE FROM feedback WHERE id=?", (int(m.group(1)),))
        return self.send(200, {"ok": True})


DASH = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lume Feedback</title>
<style>
:root{--bg:#16161a;--card:#202026;--line:#2e2e36;--tx:#ececf0;--mu:#9a9aa6;--ac:#4d6bfe}
@media (prefers-color-scheme: light){:root{--bg:#f4f4f6;--card:#fff;--line:#e2e2e8;--tx:#1b1b20;--mu:#6b6b76}}
a{color:inherit;text-decoration:none}[hidden]{display:none!important}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{display:flex;gap:12px;align-items:center;padding:14px 18px;border-bottom:1px solid var(--line);flex-wrap:wrap}header h1{font-size:1.05rem;margin:0;flex:1}
input,select,button{font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px}button{cursor:pointer}button.p{background:var(--ac);border-color:var(--ac);color:#fff}
main{display:grid;grid-template-columns:minmax(280px,420px) 1fr;gap:14px;padding:14px 18px;max-width:1300px;margin:0 auto}@media(max-width:800px){main{grid-template-columns:1fr}}
.list{display:flex;flex-direction:column;gap:8px}.it{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;cursor:pointer}.it.on{border-color:var(--ac)}.it .m{overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;margin-top:4px}
.chip{display:inline-block;padding:1px 9px;border-radius:999px;font-size:.75rem;background:var(--line);margin-right:6px}.chip.bug{background:#e5484d33;color:#e5484d}.chip.sugestao{background:#3fb95033;color:#3fb950}.chip.novo{background:#f0b42933;color:#d9a21b}
.view{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;min-height:200px}.view pre{white-space:pre-wrap;word-break:break-word;background:var(--bg);border-radius:10px;padding:10px;max-height:260px;overflow:auto;font-size:.85rem}
.view img{max-width:100%;border-radius:10px;border:1px solid var(--line)}.mu{color:var(--mu);font-size:.85rem}.row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}
#login{max-width:340px;margin:12vh auto;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;display:flex;flex-direction:column;gap:10px}
</style></head><body>
<div id="login" hidden><h1 style="margin:0 0 4px;font-size:1.15rem">Lume Feedback</h1><input id="pw" type="password" placeholder="Senha" autocomplete="current-password"><button class="p" id="go">Entrar</button><div class="mu" id="lerr"></div></div>
<div id="app" hidden><header><h1>Lume Feedback <span class="mu" id="cnt"></span></h1><input id="q" placeholder="Buscar..." style="width:200px"><select id="cat"><option value="">Todas as categorias</option><option value="bug">Bug</option><option value="sugestao">Sugestão</option><option value="outro">Outro</option></select><select id="st"><option value="">Todos os status</option><option value="novo">Novos</option><option value="lido">Lidos</option><option value="resolvido">Resolvidos</option></select><a href="/api/admin/export.csv"><button>CSV</button></a></header>
<main><div class="list" id="list"></div><div class="view" id="view"><span class="mu">Escolha uma mensagem na lista.</span></div></main></div>
<script>
const $=id=>document.getElementById(id);let cur=null;
const el=(t,c,x)=>{const e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e};
const api=async(p,o)=>{const r=await fetch(p,o);if(r.status===401&&p!=='/api/login'){show(false);throw 0}return r};
const when=t=>new Date(t*1000).toLocaleString('pt-BR');
function show(ok){$('login').hidden=ok;$('app').hidden=!ok}
async function load(){const u=new URLSearchParams({q:$('q').value,category:$('cat').value,status:$('st').value});
 const r=await api('/api/admin/items?'+u);const d=await r.json();show(true);const c=d.counts||{};$('cnt').textContent=`· ${c.novo||0} novos · ${c.lido||0} lidos · ${c.resolvido||0} resolvidos`;
 const L=$('list');L.textContent='';if(!d.items.length)L.appendChild(el('div','mu','Nada por aqui ainda.'));
 d.items.forEach(i=>{const b=el('div','it'+(i.id===cur?' on':''));const h=el('div');h.append(el('span','chip '+i.category,i.category),el('span','chip '+i.status,i.status),el('span','mu','#'+i.id+' · '+when(i.ts)));b.append(h,el('div','m',i.message));b.onclick=()=>open(i.id);L.appendChild(b)})}
async function open(id){cur=id;const r=await api('/api/admin/item/'+id);const i=await r.json();const V=$('view');V.textContent='';
 const h=el('div');h.append(el('span','chip '+i.category,i.category),el('span','chip '+i.status,i.status),el('span','mu','#'+i.id+' · '+when(i.ts)));V.appendChild(h);
 V.appendChild(el('p',null,i.message)).style.whiteSpace='pre-wrap';
 V.appendChild(el('div','mu',[i.app,i.version,i.os,i.contact&&('contato: '+i.contact)].filter(Boolean).join(' · ')));
 if(i.has_shot){const im=el('img');im.src='/api/admin/shot/'+id;im.alt='captura de tela';V.appendChild(im)}
 if(i.log){V.appendChild(el('div','mu','Informações/log enviados:'));V.appendChild(el('pre',null,i.log))}
 const row=el('div','row');['novo','lido','resolvido'].forEach(s=>{const b=el('button',i.status===s?'p':'','Marcar '+s);b.onclick=async()=>{await api('/api/admin/item/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:s})});await load();open(id)};row.appendChild(b)});
 const del=el('button',null,'Apagar');del.onclick=async()=>{if(confirm('Apagar esta mensagem?')){await api('/api/admin/item/'+id,{method:'DELETE'});cur=null;V.textContent='';await load()}};row.appendChild(del);V.appendChild(row);
 if(i.status==='novo'){await api('/api/admin/item/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'lido'})});load()}}
$('go').onclick=async()=>{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('pw').value})});if(r.ok){load()}else{$('lerr').textContent=(await r.json()).error||'erro'}};
$('pw').onkeydown=e=>{if(e.key==='Enter')$('go').click()};['q','cat','st'].forEach(i=>$(i).oninput=()=>load());
load().catch(()=>show(false));setInterval(()=>{if(!$('app').hidden)load().catch(()=>{})},30000);
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="lume-feedback: servidor + dashboard")
    ap.add_argument("--host", default="0.0.0.0"); ap.add_argument("--password", action="store_true", help="exige senha mesmo rodando so neste PC"); ap.add_argument("--no-password", action="store_true", help="nunca pede senha (so use em rede de confianca)"); ap.add_argument("--port", type=int, default=int(os.environ.get("PORT") or 8787))
    a = ap.parse_args(); os.makedirs(DATA, exist_ok=True)
    global NEED_PW
    local = a.host in ("127.0.0.1", "localhost", "::1")
    NEED_PW = a.password or not (a.no_password or local)
    with db(): pass
    if NEED_PW: password()
    print("Dashboard:", "com senha" if NEED_PW else "sem senha (so quem alcanca este servidor entra)", flush=True)
    srv = ThreadingHTTPServer((a.host, a.port), H)
    print(f"lume-feedback em http://{a.host}:{a.port}  (dashboard: /dashboard)", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: pass


if __name__ == "__main__":
    main()
