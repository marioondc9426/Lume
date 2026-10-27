"""Servidor lume-feedback + cliente: sobe o servidor de verdade numa porta livre, com banco temporario."""
import base64
import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lume-feedback")); sys.path.insert(0, os.path.join(ROOT, "feedback-app"))
os.environ["FEEDBACK_DATA"] = tempfile.mkdtemp(); os.environ["FEEDBACK_PASSWORD"] = "senha-teste"
import server as fb          # noqa: E402
import lume_feedback as cli  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


class FeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fb.DATA = os.environ["FEEDBACK_DATA"]; fb.DB = os.path.join(fb.DATA, "feedback.db")
        with fb.db(): pass
        cls.port = free_port(); cls.srv = fb.ThreadingHTTPServer(("127.0.0.1", cls.port), fb.H)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start(); cls.url = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()

    def req(self, path, data=None, method=None, cookie=None):
        r = urllib.request.Request(self.url + path, data=json.dumps(data).encode() if data is not None else None, method=method, headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})})
        try:
            with urllib.request.urlopen(r, timeout=10) as x: return x.status, x.read(), x.headers
        except urllib.error.HTTPError as e: return e.code, e.read(), e.headers

    def login(self):
        code, _, h = self.req("/api/login", {"password": "senha-teste"}); self.assertEqual(code, 200)
        return h["Set-Cookie"].split(";")[0]

    def test_fluxo_completo(self):
        ok, msg = cli.send_feedback(self.url, {"category": "bug", "message": "<script>alert(1)</script> o botão não abre", "contact": "a@b.c", "version": "4.0", "os": "Linux", "screenshot": PNG})
        self.assertTrue(ok, msg)
        self.assertEqual(self.req("/api/admin/items")[0], 401, "o dashboard precisa de login")
        ck = self.login()
        code, body, _ = self.req("/api/admin/items", cookie=ck); items = json.loads(body)["items"]
        self.assertEqual(len(items), 1); i = items[0]; self.assertEqual(i["category"], "bug"); self.assertTrue(i["has_shot"]); self.assertIn("<script>", i["message"])   # guardado como texto; o dashboard escreve com textContent
        code, body, h = self.req(f"/api/admin/shot/{i['id']}", cookie=ck); self.assertEqual((code, h["Content-Type"]), (200, "image/png"))
        self.assertEqual(self.req(f"/api/admin/item/{i['id']}", {"status": "resolvido"}, cookie=ck)[0], 200)
        self.assertEqual(json.loads(self.req("/api/admin/items?status=resolvido", cookie=ck)[1])["items"][0]["status"], "resolvido")
        self.assertIn(b"script", self.req("/api/admin/export.csv", cookie=ck)[1])
        self.assertEqual(self.req(f"/api/admin/item/{i['id']}", method="DELETE", cookie=ck)[0], 200)
        self.assertEqual(json.loads(self.req("/api/admin/items", cookie=ck)[1])["items"], [])

    def test_validacao(self):
        self.assertEqual(self.req("/api/feedback", {"message": "oi"})[0], 400)                       # curto demais
        self.assertEqual(self.req("/api/feedback", {"message": "mensagem valida", "screenshot_b64": base64.b64encode(b"nao e imagem").decode()})[0], 400)
        self.assertEqual(self.req("/api/login", {"password": "errada"})[0], 401)

    def test_limite_por_hora(self):
        fb._hits.clear()
        codes = [self.req("/api/feedback", {"message": "mensagem %d" % n})[0] for n in range(12)]
        self.assertEqual(codes[:10], [201] * 10); self.assertEqual(codes[10:], [429, 429]); fb._hits.clear()

    def test_cliente_erro_de_rede(self):
        ok, msg = cli.send_feedback("http://127.0.0.1:1", {"category": "outro", "message": "x" * 5}, timeout=2)
        self.assertFalse(ok); self.assertIn("servidor", msg)


if __name__ == "__main__":
    unittest.main()
