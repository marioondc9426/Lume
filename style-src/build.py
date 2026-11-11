"""Gera libs/lume-look.css (o "Visual novo") a partir de look.src.css com o Tailwind.

    cd style-src
    npm install          # uma vez (so para quem vai regerar o CSS)
    python build.py

No look.src.css o simbolo § vira `body[data-look="tw"][data-ui="modern"]`: tudo so vale com o Visual novo LIGADO (Configuracoes > Aparencia)
e na interface nova. O app usa so o libs/lume-look.css pronto: nao precisa de Node nem de internet.
"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
PREFIX = 'body[data-look="tw"][data-ui="modern"]'
src = open(os.path.join(HERE, 'look.src.css'), encoding='utf-8').read().replace('§', PREFIX)
gen = os.path.join(HERE, '.look.gen.css')
open(gen, 'w', encoding='utf-8').write(src)
cli = os.path.join(HERE, 'node_modules', 'tailwindcss', 'lib', 'cli.js')
if not os.path.isfile(cli): sys.exit('Falta instalar: rode `npm install` nesta pasta (style-src).')
out = os.path.join(HERE, '..', 'libs', 'lume-look.css')
r = subprocess.run(['node', cli, '-c', os.path.join(HERE, 'tailwind.config.js'), '-i', gen, '-o', out, '--minify'], cwd=HERE)
try: os.remove(gen)
except OSError: pass
if r.returncode: sys.exit(r.returncode)
print('ok:', os.path.normpath(out), os.path.getsize(out), 'bytes')
