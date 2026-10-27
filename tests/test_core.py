"""Testes basicos do Lume (rodam no GitHub Actions a cada push: .github/workflows/tests.yml).
    python -m unittest discover tests -v"""
import json
import os
import re
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["LUME_DATA_DIR"] = tempfile.mkdtemp()   # nao mexe nos seus dados
sys.argv = ["x"]
sys.path.insert(0, ROOT)
import app  # noqa: E402


def registry():
    txt = open(os.path.join(ROOT, "libs", "providers.js"), encoding="utf-8").read()
    return json.loads(re.search(r"window\.LUME_PROVIDERS\s*=\s*(\[.*\])\s*;", txt, re.S).group(1))


class RegistryTests(unittest.TestCase):
    def test_campos_obrigatorios_e_ids_unicos(self):
        reg = registry(); ids = [p["id"] for p in reg]
        self.assertEqual(len(ids), len(set(ids)), "ids repetidos")
        for p in reg:
            for k in ("id", "key", "name", "field", "url"): self.assertTrue(p.get(k), f"{p.get('id')}: falta {k}")
            self.assertTrue(p["url"].startswith("https://"), p["id"])
            self.assertTrue(p.get("logo") or p.get("letter"), f"{p['id']}: sem logo nem letra")
            if p.get("logo"): self.assertTrue(os.path.exists(os.path.join(ROOT, "icons", p["logo"])), f"{p['id']}: icons/{p['logo']} nao existe")

    def test_python_le_o_mesmo_registro(self):
        reg = registry()
        self.assertEqual(set(app.X_PROVIDERS), {p["id"] for p in reg})
        self.assertEqual(set(app.X_SHOW_ALL), {p["id"] for p in reg if p.get("showAll")})
        for p in reg: self.assertEqual(app.X_PROVIDERS[p["id"]][:3], (p["field"], p["url"], p["name"]))
        for f in [p["field"] for p in reg] + [p["field"] + "_backup" for p in reg]: self.assertIn(f, app.X_KEY_FIELDS)

    def test_provedor_generico_lista_so_modelos_de_chat(self):
        app.X_PROVIDERS["zz"] = ("zz_key", "https://zz.example/v1", "ZZ", 1.0); app.X_KIND["zz"] = "openai"; app._x_cache["zz"] = [0, []]
        old = app._openai_models
        app._openai_models = lambda base, key: [{"id": "chat-a"}, {"id": "text-embed-3"}, {"id": "v/chat-b", "context_window": 32000}, {"id": "x-image"}]
        try: got = app.extra_models("zz", {"zz_key": "k"}, force=True, raw=True)
        finally: app._openai_models = old; app.X_PROVIDERS.pop("zz"); app.X_KIND.pop("zz"); app._x_cache.pop("zz")
        self.assertEqual([m["id"] for m in got], ["chat-a", "v/chat-b"]); self.assertEqual(got[1]["ctx"], 32000)


class FakeResp:
    headers = {}
    def __init__(self, lines): self.lines = lines
    def __iter__(self): return iter(self.lines)
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def close(self): pass


def sse(lines):
    return list(app._sse_chat(FakeResp(lines), time.time(), {}))


class StreamTests(unittest.TestCase):
    def test_stream_normal(self):
        self.assertEqual(sse([b'data: {"choices":[{"delta":{"content":"oi"}}]}\n', b"data: [DONE]\n"]), [("content", "oi")])

    def test_json_de_erro_com_status_200_vira_erro(self):
        with self.assertRaises(Exception) as c: sse([b'{"error":{"message":"modelo sobrecarregado"}}\n'])
        self.assertIn("modelo sobrecarregado", str(c.exception))

    def test_resposta_inteira_sem_streaming(self):
        self.assertEqual(sse([json.dumps({"choices": [{"message": {"content": "ola"}}]}).encode() + b"\n"]), [("content", "ola")])

    def test_resposta_vazia_vira_erro(self):
        with self.assertRaises(Exception) as c: sse([])
        self.assertIn("vazio", str(c.exception))


class VoiceTests(unittest.TestCase):
    def test_tts_sem_texto_e_stt_sem_audio(self):
        with self.assertRaises(Exception): app.pol_tts("", {}, {})
        with self.assertRaises(Exception): app.pol_stt(b"", "audio/webm", {}, {})

    def test_voz_sem_chave_explica(self):
        with self.assertRaises(Exception) as c: app.pol_tts("oi", {}, {"pollinations_api_key": ""})
        self.assertIn("chave", str(c.exception).lower())


class PageTests(unittest.TestCase):
    def test_scripts_da_pagina_existem(self):
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        for src in re.findall(r'<script src="([^"]+)"', html): self.assertTrue(os.path.exists(os.path.join(ROOT, src)), src)

    def test_container_das_chaves_dos_provedores(self):
        html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        self.assertEqual(html.count('id="xp-keys"'), 1)
        self.assertNotIn('id="ac-key-input"', html)   # os campos sao gerados do registro


class RemovedFeaturesTests(unittest.TestCase):
    def test_rotas_removidas(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        for gone in ("device_sync", "device_pull", "trusted_devices", "def needs_web"): self.assertNotIn(gone, src)


if __name__ == "__main__":
    unittest.main()
