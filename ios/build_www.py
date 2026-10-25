"""Monta ios/www (a pagina do app) e o icone a partir do index.html, icons/ e fonts/ da raiz.
Uso: python ios/build_www.py   (depois: cd ios && xcodegen generate)"""
import json, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
WWW = os.path.join(HERE, "www")
shutil.rmtree(WWW, ignore_errors=True); os.makedirs(WWW)

html = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
html = html.replace("url(/fonts/", "url(fonts/")                      # arquivo local: sem "/" na frente
assert "url(/fonts/" not in html
for a, b in (("<b>Modelos locais e na nuvem</b><span>Rode no seu PC com o Ollama ou use modelos da nuvem quando precisar.</span>", "<b>Modelos na nuvem</b><span>Converse com modelos da nuvem direto no iPhone, sem PC ligado. Se quiser, conecte ao Ollama do seu PC.</span>"),
             ("<span>A IA pesquisa na web, lê PDFs e textos e entende imagens.</span>", "<span>A IA pesquisa na web, lê arquivos de texto e entende imagens.</span>")):
    assert a in html, a[:40]; html = html.replace(a, b, 1)
html = html.replace("Digite... (Shift+Enter quebra a linha, / para comandos)", "Digite sua mensagem...").replace("Type... (Shift+Enter for a new line, / for commands)", "Type a message...")   # no iPhone nao ha Shift+Enter
inject = '<script src="backend-data.js"></script><script src="lume-backend.js"></script>'
assert html.count("<head>") == 1, "esperava uma tag <head>"
html = html.replace("<head>", "<head>" + inject, 1)                  # antes de qualquer script da pagina: o fetch ja nasce trocado
open(os.path.join(WWW, "index.html"), "w", encoding="utf-8").write(html)
for f in ("backend-data.js", "lume-backend.js"): shutil.copy2(os.path.join(HERE, f), WWW)
for d in ("icons", "fonts"):
    src = os.path.join(ROOT, d); dst = os.path.join(WWW, d)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("originals", "*.ico"))

# icone do app (1024x1024, sem transparencia)
try:
    from PIL import Image
    png = os.path.join(ROOT, "icons", "lume.png")
    cat = os.path.join(HERE, "Lume", "Assets.xcassets"); app = os.path.join(cat, "AppIcon.appiconset"); os.makedirs(app, exist_ok=True)
    im = Image.open(png).convert("RGBA"); bg = Image.new("RGBA", im.size, (27, 27, 31, 255)); bg.alpha_composite(im)
    bg.convert("RGB").resize((1024, 1024), Image.LANCZOS).save(os.path.join(app, "icon-1024.png"))
    json.dump({"images": [{"filename": "icon-1024.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}], "info": {"author": "xcode", "version": 1}}, open(os.path.join(app, "Contents.json"), "w"), indent=1)
    json.dump({"info": {"author": "xcode", "version": 1}}, open(os.path.join(cat, "Contents.json"), "w"), indent=1)
except Exception as e:
    print("sem icone:", e, file=sys.stderr)
print("ok: ios/www pronto,", sum(len(f) for _, _, f in os.walk(WWW)), "arquivos")
