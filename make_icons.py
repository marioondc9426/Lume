"""Desenha a logo do Lume e gera todos os icones (nao precisa de nenhuma imagem de origem):

    icons/lume-mark.png    a marca (hexagono aberto em "catavento" com o centro aceso), fundo transparente
    icons/lume-text.png    a palavra "Lume" em preto, fundo transparente (o tema deixa branca nos escuros)
    icons/lume.png         icone do app (janela, .exe, bandeja), fundo transparente
    icons/lume-mobile.png  icone do celular / aba do navegador: marca branca menor sobre um gradiente "mesh" distorcido

    python make_icons.py [semente]     a semente muda o desenho do gradiente do icone do celular"""
import math
import os
import random
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(ROOT, "icons")
S = 1024   # desenha grande e reduz (bordas suaves)
WARM, PINK, VIOLET = (255, 190, 80), (255, 80, 140), (130, 80, 255)


def _pt(r, deg):
    a = math.radians(deg); return (S / 2 + S * r * math.cos(a), S / 2 + S * r * math.sin(a))


def _lerp(p, q, t): return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)


def _gradient(c0, c1, c2):
    g = Image.new("RGB", (S, S)); px = g.load()
    for y in range(S):
        for x in range(S):
            t = (x * .5 + y * .8) / (S * 1.3)
            u, a, b = (t / .5, c0, c1) if t < .5 else ((t - .5) / .5, c1, c2)
            px[x, y] = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
    return g


def mark_mask(R=.38, w=.14, long=.88, short=.34):
    """Hexagono aberto: tres "V" (um em cada vertice alternado) com uma perna longa e uma curta, como um catavento."""
    m = Image.new("L", (S, S), 0); d = ImageDraw.Draw(m); r = S * w / 2
    for k in range(3):
        a = -90 + k * 120; v = _pt(R, a)
        pts = [_lerp(v, _pt(R, a - 60), short), v, _lerp(v, _pt(R, a + 60), long)]
        d.line(pts, fill=255, width=int(S * w), joint="curve")
        for p in (pts[0], pts[-1]): d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=255)
    return m


def mark(mono=None):
    """A marca pronta (RGBA, 1024x1024): degrade ambar -> rosa -> violeta, ou toda de uma cor (mono), com a luz no centro."""
    m = mark_mask(); im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    im.paste(Image.new("RGB", (S, S), mono) if mono else _gradient(WARM, PINK, VIOLET), (0, 0), m)
    core = Image.new("L", (S, S), 0); ImageDraw.Draw(core).ellipse((S / 2 - 80, S / 2 - 80, S / 2 + 80, S / 2 + 80), fill=255)
    glow = Image.new("RGBA", (S, S), (255, 170, 100, 0)); glow.putalpha(core.filter(ImageFilter.GaussianBlur(48)))
    im = Image.alpha_composite(im, glow); im.paste(Image.new("RGBA", (S, S), (255, 248, 230, 255)), (0, 0), core.filter(ImageFilter.GaussianBlur(2)))
    return im


def crop_pad(im, pad=0.04, square=False):
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox(); im = im.crop(box)
    w, h = im.size; side = max(w, h) if square else None
    cw, ch = (side, side) if square else (w, h); p = int(max(cw, ch) * pad)
    out = Image.new("RGBA", (cw + 2 * p, ch + 2 * p), (0, 0, 0, 0)); out.paste(im, ((cw - w) // 2 + p, (ch - h) // 2 + p)); return out


def wordmark(text="Lume", height=128):
    font = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", 400)
    try: font.set_variation_by_name("SemiBold")
    except Exception: pass
    im = Image.new("RGBA", (1800, 700), (0, 0, 0, 0)); ImageDraw.Draw(im).text((40, 40), text, font=font, fill=(0, 0, 0, 255))
    im = crop_pad(im, 0.02); return im.resize((round(im.width * height / im.height), height), Image.LANCZOS)


def mesh_gradient(size, seed):
    """Fundo escuro com manchas grandes de cor, borradas e depois entortadas (MeshTransform): o visual de gradiente "liquido".
    Desenha maior e corta o centro, para as bordas da distorcao nao aparecerem."""
    rnd = random.Random(seed); s = int(size * 1.4)
    palette = [(124, 77, 255), (59, 130, 246), (236, 72, 153), (34, 211, 238), (99, 102, 241), (168, 85, 247)]; rnd.shuffle(palette)
    layer = Image.new("RGB", (s, s), (16, 14, 44)); d = ImageDraw.Draw(layer)
    for col, (fx, fy) in zip(palette, [(.25, .25), (.75, .25), (.25, .75), (.75, .75), (.5, .5), (.5, .1)]):
        cx, cy, r = int(s * (fx + rnd.uniform(-.1, .1))), int(s * (fy + rnd.uniform(-.1, .1))), int(s * rnd.uniform(.2, .3))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    base = layer.filter(ImageFilter.GaussianBlur(s * .1))
    n = 6; cell = s // n; amp = cell // 2
    pts = {(i, j): (i * cell + (rnd.randint(-amp, amp) if 0 < i < n and 0 < j < n else 0), j * cell + (rnd.randint(-amp, amp) if 0 < i < n and 0 < j < n else 0)) for i in range(n + 1) for j in range(n + 1)}
    mesh = [((i * cell, j * cell, (i + 1) * cell, (j + 1) * cell), (*pts[(i, j)], *pts[(i, j + 1)], *pts[(i + 1, j + 1)], *pts[(i + 1, j)])) for i in range(n) for j in range(n)]
    warped = base.transform((cell * n, cell * n), Image.MESH, mesh, Image.BICUBIC).filter(ImageFilter.GaussianBlur(s * .01))
    o = (warped.width - size) // 2
    return warped.crop((o, o, o + size, o + size))


def mobile_icon(seed, size=512, scale=0.5):
    tile = mesh_gradient(size, seed).convert("RGBA")
    m = crop_pad(mark((255, 255, 255)), 0.0, square=True).resize((int(size * scale),) * 2, Image.LANCZOS)
    pos = ((size - m.width) // 2, (size - m.height) // 2)
    shadow = Image.new("RGBA", tile.size, (0, 0, 0, 0)); sm = Image.new("RGBA", m.size, (20, 0, 60, 255)); sm.putalpha(m.getchannel("A").point(lambda v: v * 150 // 255))
    shadow.paste(sm, (pos[0], pos[1] + size // 40), sm); tile = Image.alpha_composite(tile, shadow.filter(ImageFilter.GaussianBlur(size * .025)))
    tile.alpha_composite(m, pos); return tile.convert("RGB")


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    big = crop_pad(mark(), 0.0, square=True)
    big.resize((512, 512), Image.LANCZOS).save(os.path.join(ICONS, "lume-mark.png"))
    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0)); mk = big.resize((216, 216), Image.LANCZOS); icon.paste(mk, (20, 20), mk); icon.save(os.path.join(ICONS, "lume.png"))
    wordmark().save(os.path.join(ICONS, "lume-text.png"))
    mobile_icon(seed).save(os.path.join(ICONS, "lume-mobile.png"))
    print("ok: lume-mark.png, lume.png, lume-text.png, lume-mobile.png (semente %d)" % seed)
