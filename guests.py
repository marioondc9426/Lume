"""Contas de amigos (modo /share): cadastro so com nome de usuario, limites, avisos e liga/desliga pelo /dashboard.

Tudo fica em guests.json (contas e configuracoes) e guest_data/<id>/ (conversas e memorias de cada amigo).
Este modulo so cuida das regras; o servidor HTTP (app.py) chama as funcoes daqui."""
import json
import os
import re
import secrets
import threading
import time

NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,20}$")
FEATURES = {   # o que o dono pode bloquear para cada amigo
    "web": "Pesquisa na web", "files": "Anexar arquivos", "images": "Enviar imagens", "think": "Modo pensar",
    "cloud": "Modelos da nuvem", "local": "Modelos locais (usam a GPU do PC)",
}
DEFAULT_SETTINGS = {
    "open": True,                    # aceita novos cadastros em /share
    "invite_code": "",               # se preenchido, o amigo precisa digitar este codigo para criar a conta
    "max_users": 10,
    "default_blocked_features": ["files", "images", "think"],
    "default_blocked_models": [],
    "daily_limit": 100,              # respostas por dia por amigo (0 = sem limite)
    "per_minute": 6,                 # no maximo isso por minuto
    "max_parallel": 2,               # geracoes de amigos ao mesmo tempo
    "ctx_cap": 8192,                 # tamanho maximo de contexto dos modelos locais para amigos
    "max_tokens": 2048,              # tamanho maximo de cada resposta
    "global_off": False, "shutdown_at": None, "shutdown_msg": "", "banner": "",
}


class Guests:
    def __init__(self, path, data_dir):
        self.path, self.data_dir = path, data_dir
        self.lock = threading.RLock()
        self.codes = {}                  # codigo de acesso -> (id, vence)
        self.reg_times = {}              # ip -> horarios de cadastro (limite por hora)
        self._tok = {}                   # token -> id (indice em memoria)
        self.data = self._load()
        self._reindex()

    # ---------- arquivo ----------
    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f: d = json.load(f)
        except (OSError, ValueError):
            d = {}
        d.setdefault("settings", {}); d.setdefault("users", {})
        for k, v in DEFAULT_SETTINGS.items(): d["settings"].setdefault(k, v)
        return d

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f: json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)

    def _reindex(self):
        self._tok = {t: uid for uid, u in self.data["users"].items() for t in u.get("tokens", {})}

    @property
    def settings(self): return self.data["settings"]

    # ---------- contas ----------
    def find_by_name(self, name):
        n = (name or "").strip().lower()
        for uid, u in self.data["users"].items():
            if u["name"].lower() == n: return uid
        return None

    def _new_token(self, uid, ip, ua):
        tok = secrets.token_hex(24); now = time.time()
        u = self.data["users"][uid]; u.setdefault("tokens", {})[tok] = {"ip": ip, "ua": (ua or "")[:80], "created": now, "last": now}
        while len(u["tokens"]) > 5: del u["tokens"][min(u["tokens"], key=lambda t: u["tokens"][t]["last"])]   # so os 5 aparelhos mais recentes
        self._reindex(); return tok

    def register(self, name, ip, ua="", invite=""):
        """Cria a conta. Retorna (id, token). Levanta ValueError com um codigo: closed, invite, name, taken, full, rate."""
        with self.lock:
            s = self.settings
            if not s["open"]: raise ValueError("closed")
            if s["invite_code"] and (invite or "").strip() != s["invite_code"]: raise ValueError("invite")
            name = (name or "").strip()
            if not NAME_RE.match(name): raise ValueError("name")
            if self.find_by_name(name): raise ValueError("taken")
            if len(self.data["users"]) >= int(s["max_users"]): raise ValueError("full")
            now = time.time(); hist = [t for t in self.reg_times.get(ip, []) if now - t < 3600]
            if len(hist) >= 5: raise ValueError("rate")
            hist.append(now); self.reg_times[ip] = hist
            uid = secrets.token_hex(4)
            self.data["users"][uid] = {"name": name, "created": now, "last": now, "enabled": True, "tokens": {}, "disable_at": None, "message": "", "message_id": 0,
                                       "blocked_models": list(s["default_blocked_models"]), "blocked_features": list(s["default_blocked_features"]), "daily_limit": None, "note": ""}
            tok = self._new_token(uid, ip, ua); self.save()
            return uid, tok

    def new_code(self, uid):
        """Codigo de 6 caracteres (valido por 10 min) para o amigo entrar com a mesma conta em outro aparelho."""
        with self.lock:
            code = "".join(secrets.choice("ABCDEFGHJKMNPQRSTUVWXYZ23456789") for _ in range(6))
            self.codes = {c: v for c, v in self.codes.items() if v[1] > time.time()}
            self.codes[code] = (uid, time.time() + 600); return code

    def login_with_code(self, name, code, ip, ua=""):
        with self.lock:
            uid = self.find_by_name(name); entry = self.codes.get((code or "").strip().upper())
            if not uid or not entry or entry[0] != uid or entry[1] < time.time(): raise ValueError("code")
            del self.codes[(code or "").strip().upper()]
            tok = self._new_token(uid, ip, ua); self.save(); return uid, tok

    def by_token(self, tok):
        """(id, conta) do dono do token, ou (None, None). Atualiza o 'visto por ultimo'."""
        uid = self._tok.get(tok or "")
        if not uid or uid not in self.data["users"]: return None, None
        u = self.data["users"][uid]; now = time.time()
        if now - u.get("last", 0) > 20: u["last"] = now
        t = u["tokens"].get(tok)
        if t and now - t.get("last", 0) > 300: t["last"] = now; self.save()
        return uid, u

    def drop_token(self, tok):
        with self.lock:
            uid = self._tok.get(tok or "")
            if uid and tok in self.data["users"][uid]["tokens"]: del self.data["users"][uid]["tokens"][tok]; self._reindex(); self.save()

    def delete(self, uid):
        with self.lock:
            self.data["users"].pop(uid, None); self._reindex(); self.save()

    # ---------- liga / desliga ----------
    def state(self, u, now=None):
        """(ligado?, motivo). Executa os desligamentos agendados que ja venceram."""
        now = now or time.time(); s = self.settings; changed = False
        if s["shutdown_at"] and now >= s["shutdown_at"]: s["global_off"] = True; s["shutdown_at"] = None; changed = True
        if u.get("disable_at") and now >= u["disable_at"]: u["enabled"] = False; u["disable_at"] = None; changed = True
        if changed: self.save()
        if s["global_off"]: return False, "global"
        if not u.get("enabled", True): return False, "user"
        return True, ""

    def notice_for(self, u, now=None):
        """O que mostrar ao amigo: aviso de desligamento (com contagem), recado do dono."""
        now = now or time.time(); s = self.settings; out = {}
        if s["shutdown_at"]: out["shutdown_in"] = max(0, int(s["shutdown_at"] - now)); out["shutdown_msg"] = s.get("shutdown_msg", "")
        elif u.get("disable_at"): out["shutdown_in"] = max(0, int(u["disable_at"] - now)); out["shutdown_msg"] = u.get("message", "")
        if s.get("banner"): out["banner"] = s["banner"]
        if u.get("message") and not out.get("shutdown_msg"): out["message"] = u["message"]
        return out

    def shutdown_user(self, uid, seconds=0, msg=""):
        with self.lock:
            u = self.data["users"][uid]; u["message"] = msg or ""
            if seconds and seconds > 0: u["disable_at"] = time.time() + seconds
            else: u["enabled"] = False; u["disable_at"] = None
            self.save()

    def enable_user(self, uid):
        with self.lock:
            u = self.data["users"][uid]; u["enabled"] = True; u["disable_at"] = None; u["message"] = ""; self.save()

    def shutdown_all(self, seconds=0, msg=""):
        with self.lock:
            s = self.settings; s["shutdown_msg"] = msg or ""
            if seconds and seconds > 0: s["shutdown_at"] = time.time() + seconds
            else: s["global_off"] = True; s["shutdown_at"] = None
            self.save()

    def enable_all(self):
        with self.lock:
            s = self.settings; s["global_off"] = False; s["shutdown_at"] = None; s["shutdown_msg"] = ""
            for u in self.data["users"].values(): u["enabled"] = True; u["disable_at"] = None; u["message"] = ""
            self.save()

    # ---------- regras de uso ----------
    def policy(self, u):
        s = self.settings
        lim = u.get("daily_limit"); lim = s["daily_limit"] if lim is None else lim
        return {"blocked_models": set(u.get("blocked_models", [])), "blocked_features": set(u.get("blocked_features", [])), "daily_limit": int(lim or 0)}

    def check_model(self, u, model):
        """Motivo (texto curto) se este amigo nao pode usar o modelo, ou None."""
        p = self.policy(u)
        if (model or "").startswith("groq"): return "model"
        if model in p["blocked_models"]: return "model"
        cloud = bool(re.search(r"(:|-)cloud$", model or ""))
        if cloud and "cloud" in p["blocked_features"]: return "cloud"
        if not cloud and "local" in p["blocked_features"]: return "local"
        return None

    # ---------- pastas de cada amigo ----------
    def user_dir(self, uid):
        d = os.path.join(self.data_dir, uid); os.makedirs(d, exist_ok=True); return d

    def history_file(self, uid): return os.path.join(self.user_dir(uid), "history.json")
    def state_file(self, uid): return os.path.join(self.user_dir(uid), "state.json")


def usage_by_user(events, users, now=None):
    """Resume o uso de cada amigo a partir dos eventos de estatistica (cada evento de chat tem o campo 'user')."""
    now = now or time.time(); day0 = time.mktime(time.strptime(time.strftime("%Y-%m-%d", time.localtime(now)), "%Y-%m-%d"))
    out = {uid: {"requests": 0, "today": 0, "tokens": 0, "seconds": 0.0, "last_ts": 0, "models": {}, "last_model": "", "minute": 0} for uid in users}
    for e in events:
        uid = e.get("user")
        if e.get("type") != "chat" or uid not in out: continue
        o = out[uid]; o["requests"] += 1; o["tokens"] += e.get("tokens", 0); o["seconds"] += e.get("seconds", 0.0)
        m = o["models"].setdefault(e.get("model", "?"), {"requests": 0, "tokens": 0}); m["requests"] += 1; m["tokens"] += e.get("tokens", 0)
        if e["ts"] >= day0: o["today"] += 1
        if now - e["ts"] < 60: o["minute"] += 1
        if e["ts"] >= o["last_ts"]: o["last_ts"] = e["ts"]; o["last_model"] = e.get("model", "")
    return out
