"""Gera backend-data.js (listas de modelos e limites) a partir do app.py, para o porte em JavaScript ficar igual ao servidor.
Uso: python ios/gen_data.py  (escreve ios/backend-data.js)"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
os.environ.setdefault("DATA_DIR", os.path.join(HERE, ".gen_tmp")); sys.path.insert(0, ROOT); sys.argv = ["x"]
import app
data = {
    "POL_MODELS": [[mid, ex] for mid, ex in app.POL_MODELS], "POL_MAX_PRICE": app.POL_MAX_PRICE,
    "VERCEL_MODELS": [list(x) for x in app.VERCEL_MODELS], "TDC_MODELS": [list(x) for x in app.TDC_MODELS], "TDC_MAX_CR": app.TDC_MAX_CR,
    "MODEL_EXCLUDE": app.MODEL_EXCLUDE.pattern, "GROQ_EXCLUDE": app.GROQ_EXCLUDE.pattern,
}
with open(os.path.join(HERE, "backend-data.js"), "w", encoding="utf-8") as f:
    f.write("/* gerado por ios/gen_data.py a partir do app.py: nao edite a mao */\nwindow.LUME_DATA = " + json.dumps(data, ensure_ascii=False) + ";\n")
print("ok:", len(data["POL_MODELS"]), "modelos da Pollinations")
