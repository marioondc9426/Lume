#!/usr/bin/env python3
"""Lume Feedback: app separado para mandar bug, sugestao ou comentario (com captura de tela, se quiser) para o servidor lume-feedback.

    python lume_feedback.py                         abre a janela
    python lume_feedback.py --server http://IP:8787 define o servidor (fica salvo)

O servidor vem de: --server, da variavel LUME_FEEDBACK_URL, do arquivo server.txt ao lado do app ou do que voce digitou antes (~/.lume-feedback.json).
Privacidade: este app NUNCA le o config.json nem as chaves do Lume. So manda o que voce escreve, a captura que voce escolher e (se marcar) o sistema e a versao."""
import argparse
import base64
import io
import json
import os
import platform
import queue
import sys
import threading
import urllib.error
import urllib.request

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:   # sem tkinter (ex.: servidor sem tela): so o modo de linha de comando funciona
    tk = None

APP_VERSION = "1.0"
CONF = os.path.join(os.path.expanduser("~"), ".lume-feedback.json")
HERE = os.path.dirname(os.path.abspath(getattr(sys, "_MEIPASS", None) or __file__))
CATS = [("bug", "Bug (algo não funciona)"), ("sugestao", "Sugestão"), ("outro", "Outro")]
MAX_SHOT = 1_400_000


def load_conf():
    try: return json.load(open(CONF, encoding="utf-8"))
    except Exception: return {}


def save_conf(c):
    try: json.dump(c, open(CONF, "w", encoding="utf-8"))
    except OSError: pass


def default_server(conf):
    if os.environ.get("LUME_FEEDBACK_URL"): return os.environ["LUME_FEEDBACK_URL"]
    if conf.get("server"): return conf["server"]
    try: return open(os.path.join(HERE, "server.txt"), encoding="utf-8").read().strip()
    except OSError: return "http://127.0.0.1:8787"


def system_info():
    return f"{platform.system()} {platform.release()} · {platform.machine()} · Python {platform.python_version()} · Lume Feedback {APP_VERSION}"


def shrink(data):
    """Reduz a imagem (se o Pillow existir) para caber no limite do servidor. Devolve bytes PNG/JPEG ou None."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data)).convert("RGB"); im.thumbnail((1600, 1600))
        for q in (85, 70, 55, 40):
            b = io.BytesIO(); im.save(b, "JPEG", quality=q)
            if b.tell() <= MAX_SHOT: return b.getvalue()
        return None
    except Exception:
        return data if len(data) <= MAX_SHOT else None


def grab_screen():
    from PIL import ImageGrab
    b = io.BytesIO(); ImageGrab.grab().save(b, "PNG"); return shrink(b.getvalue())


def send_feedback(server, payload, key="", timeout=20):
    """Manda para o servidor. Devolve (ok, mensagem). payload: category, message, contact, version, os, log, screenshot (bytes)."""
    body = {k: v for k, v in payload.items() if k != "screenshot"}; body["app"] = body.get("app") or "Lume"
    if payload.get("screenshot"): body["screenshot_b64"] = base64.b64encode(payload["screenshot"]).decode()
    req = urllib.request.Request(server.rstrip("/") + "/api/feedback", data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json", **({"X-Feedback-Key": key} if key else {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return True, "Enviado! Obrigado. (#%s)" % json.load(r).get("id")
    except urllib.error.HTTPError as e:
        try: msg = json.load(e).get("error")
        except Exception: msg = ""
        return False, msg or ("o servidor respondeu " + str(e.code))
    except Exception as e:
        return False, "não consegui falar com o servidor (" + str(getattr(e, "reason", e))[:80] + ")"


class App:
    def __init__(self, server):
        self.conf = load_conf(); self.shot = None; self.q = queue.Queue()
        r = self.root = tk.Tk(); r.title("Lume Feedback"); r.geometry("560x640"); r.minsize(480, 560)
        pad = {"padx": 16, "pady": (8, 0)}
        ttk.Label(r, text="Lume Feedback", font=("TkDefaultFont", 15, "bold")).pack(anchor="w", padx=16, pady=(14, 0))
        ttk.Label(r, text="Conte o que aconteceu ou o que você gostaria. Nada do seu config.json nem das suas chaves é enviado.", wraplength=520, foreground="#666").pack(anchor="w", padx=16)
        ttk.Label(r, text="O que é?").pack(anchor="w", **pad)
        self.cat = ttk.Combobox(r, state="readonly", values=[t for _, t in CATS]); self.cat.current(0); self.cat.pack(fill="x", padx=16)
        ttk.Label(r, text="Mensagem").pack(anchor="w", **pad)
        self.msg = tk.Text(r, height=9, wrap="word", font=("TkDefaultFont", 11)); self.msg.pack(fill="both", expand=True, padx=16)
        ttk.Label(r, text="Contato (opcional: e-mail ou usuário, para eu responder)").pack(anchor="w", **pad)
        self.contact = ttk.Entry(r); self.contact.insert(0, self.conf.get("contact", "")); self.contact.pack(fill="x", padx=16)
        row = ttk.Frame(r); row.pack(fill="x", padx=16, pady=(8, 0))
        ttk.Label(row, text="Versão do Lume").pack(side="left"); self.ver = ttk.Entry(row, width=10); self.ver.insert(0, self.conf.get("version", "")); self.ver.pack(side="left", padx=8)
        self.sysinfo = tk.BooleanVar(value=True); ttk.Checkbutton(row, text="Incluir o sistema (Windows/Linux, versão)", variable=self.sysinfo).pack(side="left", padx=8)
        shot = ttk.Frame(r); shot.pack(fill="x", padx=16, pady=(8, 0))
        ttk.Button(shot, text="Capturar a tela", command=self.capture).pack(side="left"); ttk.Button(shot, text="Escolher imagem…", command=self.pick).pack(side="left", padx=6)
        self.shot_lbl = ttk.Label(shot, text="sem imagem", foreground="#666"); self.shot_lbl.pack(side="left", padx=6)
        ttk.Label(r, text="Servidor do feedback").pack(anchor="w", **pad)
        self.server = ttk.Entry(r); self.server.insert(0, server); self.server.pack(fill="x", padx=16)
        self.send_btn = ttk.Button(r, text="Enviar", command=self.send); self.send_btn.pack(pady=(14, 4))
        self.status = ttk.Label(r, text="", wraplength=520); self.status.pack(padx=16, pady=(0, 12))
        r.after(100, self.poll)

    def capture(self):
        self.root.withdraw(); self.root.update(); self.root.after(350, self._grab)   # esconde a janela para ela nao sair na foto
    def _grab(self):
        try: self.shot = grab_screen()
        except Exception as e: self.shot = None; messagebox.showinfo("Captura", "Não consegui capturar a tela aqui (precisa do pacote Pillow). Use \"Escolher imagem…\".\n" + str(e)[:100])
        self.root.deiconify(); self._shot_label()
    def pick(self):
        f = filedialog.askopenfilename(filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
        if f:
            self.shot = shrink(open(f, "rb").read())
            if self.shot is None: messagebox.showinfo("Imagem", "Essa imagem é grande demais (limite ~1,4 MB).")
            self._shot_label()
    def _shot_label(self): self.shot_lbl.config(text=("imagem anexada (%d KB)" % (len(self.shot) // 1024)) if self.shot else "sem imagem")

    def send(self):
        text = self.msg.get("1.0", "end").strip()
        if len(text) < 3: self.status.config(text="Escreva pelo menos algumas palavras."); return
        cat = CATS[self.cat.current()][0]; server = self.server.get().strip()
        pay = {"category": cat, "message": text, "contact": self.contact.get().strip(), "version": self.ver.get().strip(), "os": platform.system() + " " + platform.release() if self.sysinfo.get() else "", "log": system_info() if self.sysinfo.get() else "", "screenshot": self.shot}
        self.send_btn.config(state="disabled"); self.status.config(text="Enviando…")
        def work(): self.q.put((send_feedback(server, pay, self.conf.get("key", "")), server, pay))   # a rede roda numa thread; quem mexe na janela e so a principal (fila)
        threading.Thread(target=work, daemon=True).start()
    def poll(self):
        try:
            (ok, m), server, pay = self.q.get_nowait(); self.done(ok, m, server, pay)
        except queue.Empty: pass
        self.root.after(100, self.poll)
    def done(self, ok, m, server, pay):
        self.send_btn.config(state="normal"); self.status.config(text=m, foreground="#2a9d3f" if ok else "#d33")
        if ok:
            self.conf.update(server=server, contact=pay["contact"], version=pay["version"]); save_conf(self.conf)
            self.msg.delete("1.0", "end"); self.shot = None; self._shot_label()

    def run(self): self.root.mainloop()


def main():
    ap = argparse.ArgumentParser(description="Lume Feedback")
    ap.add_argument("--server"); ap.add_argument("--message", help="manda uma mensagem sem abrir a janela"); ap.add_argument("--category", default="outro", choices=[c for c, _ in CATS])
    a = ap.parse_args(); conf = load_conf()
    if a.server: conf["server"] = a.server; save_conf(conf)
    server = a.server or default_server(conf)
    if a.message:
        ok, m = send_feedback(server, {"category": a.category, "message": a.message, "os": platform.system() + " " + platform.release(), "log": system_info()}, conf.get("key", "")); print(m); sys.exit(0 if ok else 1)
    if tk is None: print("Sem tkinter neste computador. Use: lume_feedback.py --message \"texto\" --server URL"); sys.exit(2)
    App(server).run()


if __name__ == "__main__":
    main()
