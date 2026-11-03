# Noël 1962 — rendering core: camera, image heroes, text, transitions, film look.
# Every size is expressed in 3840x2160 design units and multiplied by S at runtime.
import math, os, glob, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache")
os.makedirs(CACHE, exist_ok=True)
FPS = 30

class Ctx:
    """Output geometry. S = scale relative to 3840x2160."""
    def __init__(self, W=3840, H=2160):
        self.W, self.H, self.S = W, H, W / 3840
CTX = Ctx()

def set_size(W, H):
    CTX.__init__(W, H)
    font.cache_clear()

# ---------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x
def ease(x):  # sine in-out
    x = clamp(x); return 0.5 - 0.5 * math.cos(math.pi * x)
def ease_out(x):
    x = clamp(x); return 1 - (1 - x) ** 3
def lerp(a, b, k): return a + (b - a) * k

# ---------------------------------------------------------------- fonts
FONTS = {
    "title": "fonts/playfair-display-latin-700-normal.woff2",
    "serif": "fonts/playfair-display-latin-400-normal.woff2",
    "italic": "fonts/playfair-display-latin-400-italic.woff2",
    "bolditalic": "fonts/playfair-display-latin-700-italic.woff2",
    "type": "fonts/special-elite-latin-400-normal.woff2",
}
@functools.lru_cache(maxsize=256)
def font(name, size):
    return ImageFont.truetype(os.path.join(ROOT, FONTS[name]), max(6, int(round(size * CTX.S))))

# ---------------------------------------------------------------- image heroes
def img_path(n):
    return glob.glob(os.path.join(ROOT, f"{n}_{n}_*.jpg"))[0]

@functools.lru_cache(maxsize=8)
def img_base(n, W, H):
    """Source upscaled once (Lanczos + gentle sharpen) to cover 1.3x the frame."""
    im = Image.open(img_path(n)).convert("RGB")
    k = max(W * 1.3 / im.width, H * 1.3 / im.height)
    k = min(k, 2.4)  # beyond this, let per-frame bicubic do the rest
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    im = im.filter(ImageFilter.UnsharpMask(radius=2 * CTX.S + 0.6, percent=60, threshold=2))
    return im

def cam_box(bw, bh, W, H, z, x, y):
    """Crop box in a (bw,bh) base for zoom z>=1 and pan x,y in [-1,1]."""
    cover = max(W / bw, H / bh)       # base->frame scale at zoom 1
    cw, ch = W / (cover * z), H / (cover * z)
    cx = bw / 2 + x * (bw - cw) / 2
    cy = bh / 2 + y * (bh - ch) / 2
    return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)

class Cam:
    """Camera move: z, x, y each (start, end); eased over the shot.
    Optional c=((u0,v0),(u1,v1)): frame centre in normalized base coords (overrides x,y).
    Optional span=(k0,k1): the move happens inside that part of the shot."""
    def __init__(self, z=(1.0, 1.06), x=(0, 0), y=(0, 0), c=None, curve=ease, span=(0, 1)):
        self.z, self.x, self.y, self.c, self.curve, self.span = z, x, y, c, curve, span
    def ek(self, k):
        return self.curve((k - self.span[0]) / max(1e-6, self.span[1] - self.span[0]))
    def box(self, bw, bh, W, H, k):
        e = self.ek(k)
        z = lerp(*self.z, e)
        if self.c is None:
            return cam_box(bw, bh, W, H, z, lerp(*self.x, e), lerp(*self.y, e))
        cover = max(W / bw, H / bh)
        cw, ch = W / (cover * z), H / (cover * z)
        u, v = lerp(self.c[0][0], self.c[1][0], e) * bw, lerp(self.c[0][1], self.c[1][1], e) * bh
        u = clamp(u, cw / 2, bw - cw / 2); v = clamp(v, ch / 2, bh - ch / 2)
        return (u - cw / 2, v - ch / 2, u + cw / 2, v + ch / 2)

class Hero:
    """Something that fills the frame. frame(t, k) -> RGB image W x H.
    t = seconds since shot start, k = progress 0..1 over the shot."""
    def frame(self, t, k, dur): raise NotImplementedError

class Photo(Hero):
    def __init__(self, n, cam=None, grade=None):
        self.n, self.cam, self.grade = n, cam or Cam(), grade
    def frame(self, t, k, dur):
        W, H = CTX.W, CTX.H
        base = img_base(self.n, W, H)
        box = self.cam.box(base.width, base.height, W, H, k)
        im = base.resize((W, H), Image.BICUBIC, box=box)
        if self.grade: im = self.grade(im, t, k)
        return im

# ---------------------------------------------------------------- vector heroes helper
class Canvas(Hero):
    """Hero drawn in a fixed design canvas (CWxCH design units) then viewed through a camera.
    Subclasses implement base() (static, cached) and overlay(draw, t, k, to_px) (per frame)."""
    CW, CH = 3840, 2160
    OVERS = 1.12  # supersampling of the static base relative to output (room for zoom)
    def __init__(self, cam=None):
        self.cam = cam or Cam()
        self._base = None
    def base(self, s):  # s: px per design unit
        raise NotImplementedError
    def overlay(self, im, t, k, P, s):  # P(x,y)->screen px, s: screen px per design unit
        pass
    def frame(self, t, k, dur):
        W, H = CTX.W, CTX.H
        s0 = CTX.S * self.OVERS
        if self._base is None or self._base[0] != (W, H):
            self._base = ((W, H), self.base(s0))
        base = self._base[1]
        box = self.cam.box(base.width, base.height, W, H, k)
        im = base.resize((W, H), Image.BICUBIC, box=box)
        sc = W / (box[2] - box[0])  # screen px per base px
        def P(dx, dy):  # design units -> screen px
            return ((dx * s0 - box[0]) * sc, (dy * s0 - box[1]) * sc)
        self.overlay(im, t, k, P, s0 * sc)
        return im

# ---------------------------------------------------------------- text
def text_layer(lines, size=110, face="type", color=(244, 236, 220), shadow=True,
               align="left", spacing=0.25):
    """Render lines of text to an RGBA image (tight) with soft shadow."""
    if isinstance(lines, str): lines = [lines]
    specs = []
    for ln in lines:
        if isinstance(ln, str): ln = (ln, size, face, color)
        specs.append(ln)
    fonts = [font(f, sz) for _, sz, f, _ in specs]
    boxes = [f.getbbox(t) for (t, *_), f in zip(specs, fonts)]
    ws = [b[2] - b[0] for b in boxes]
    hs = [f.getmetrics()[0] + f.getmetrics()[1] for f in fonts]
    gap = [int(sz * spacing * CTX.S) for _, sz, _, _ in specs]
    pad = int(40 * CTX.S)
    Wt = max(ws) + 2 * pad
    Ht = sum(hs) + sum(gap[:-1]) + 2 * pad
    im = Image.new("RGBA", (Wt, Ht), (0, 0, 0, 0))
    sh = Image.new("L", (Wt, Ht), 0)
    d, ds = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    y = pad
    for (t, sz, f_, col), f, w, h, g, b in zip(specs, fonts, ws, hs, gap, boxes):
        x = pad + (0 if align == "left" else (max(ws) - w) // 2 if align == "center" else max(ws) - w) - b[0]
        if shadow: ds.text((x, y + int(4 * CTX.S)), t, font=f, fill=200)
        d.text((x, y), t, font=f, fill=col + (255,))
        y += h + g
    if shadow:
        sh = sh.filter(ImageFilter.GaussianBlur(10 * CTX.S))
        out = Image.new("RGBA", (Wt, Ht), (0, 0, 0, 0))
        out.putalpha(sh)
        out = Image.alpha_composite(out, im)
        return out
    return im

@functools.lru_cache(maxsize=64)
def scrim_mask(w, h):
    W, H = int(w * 1.5) + 2, int(h * 2.2) + 2
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    return Image.fromarray((np.clip(1 - d, 0, 1) ** 1.3 * 255).astype(np.uint8))

class Text:
    """Timed text overlay. at/until are absolute seconds. pos: 'lowleft', 'center', 'top', (x,y) design units."""
    def __init__(self, at, lines, until=None, pos="lowleft", fade=0.4, typing=False, scrim=0.55, **kw):
        self.at, self.lines, self.until, self.pos, self.fade, self.typing, self.kw = at, lines, until, pos, fade, typing, kw
        self.scrim = scrim
        self._cache = {}
    def layer(self, n_chars=None):
        key = (CTX.W, n_chars)
        if key not in self._cache:
            lines = self.lines
            if n_chars is not None:
                out, left = [], n_chars
                for ln in ([lines] if isinstance(lines, str) else lines):
                    t = ln if isinstance(ln, str) else ln[0]
                    cut = t[:max(0, left)]; left -= len(t)
                    out.append(cut if isinstance(ln, str) else (cut,) + tuple(ln[1:]))
                lines = out
            if len(self._cache) > 4: self._cache.clear()
            self._cache[key] = text_layer(lines, **self.kw)
        return self._cache[key]
    def draw(self, im, T, shot_end):
        end = self.until if self.until is not None else shot_end - 0.15
        if T < self.at or T > end: return
        a = min(clamp((T - self.at) / self.fade), clamp((end - T) / self.fade))
        n = None
        if self.typing:
            total = sum(len(l if isinstance(l, str) else l[0]) for l in ([self.lines] if isinstance(self.lines, str) else self.lines))
            n = min(total, int((T - self.at) * self.typing))
            a = clamp((end - T) / self.fade)
            if n <= 0: return
        L = self.layer(n)
        W, H, S = CTX.W, CTX.H, CTX.S
        if self.pos == "lowleft": x, y = int(230 * S), int(H - 300 * S - L.height)
        elif self.pos == "lowright": x, y = int(W - 230 * S - L.width), int(H - 300 * S - L.height)
        elif self.pos == "center": x, y = (W - L.width) // 2, (H - L.height) // 2
        elif self.pos == "lowcenter": x, y = (W - L.width) // 2, int(H - 260 * S - L.height)
        elif self.pos == "top": x, y = (W - L.width) // 2, int(200 * S)
        elif self.pos == "topleft": x, y = int(230 * S), int(220 * S)
        else: x, y = int(self.pos[0] * S), int(self.pos[1] * S)
        if self.typing and n is not None:  # anchor typing at the full-text position
            pass
        if self.scrim:  # soft dark pool behind the text for legibility on bright pictures
            sm = scrim_mask(L.width, L.height)
            im.paste((0, 0, 0), (x + L.width // 2 - sm.width // 2, y + L.height // 2 - sm.height // 2),
                     sm.point(lambda v: int(v * a * self.scrim)))
        if a >= 0.999: im.paste(L, (x, y), L)
        else:
            A = L.getchannel("A").point(lambda v: int(v * a))
            im.paste(L, (x, y), A)

# ---------------------------------------------------------------- film look
# Period grade as a colour matrix (C speed): slight desaturation, warm highlights, lifted blacks.
def _grade_matrix(sat=0.88, mul=(1.03, 1.0, 0.93), off=(6, 4, 2)):
    lw = 1 / 3
    m = []
    for c in range(3):
        row = [(lw * (1 - sat) + (sat if j == c else 0)) * mul[c] for j in range(3)] + [off[c]]
        m += row
    return tuple(m)
GRADE = _grade_matrix()

@functools.lru_cache(maxsize=2)
def vignette(W, H):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = (x - W / 2) / (W / 2), (y - H / 2) / (H / 2)
    r = np.sqrt(nx * nx * 0.85 + ny * ny)
    v = 1 - 0.38 * np.clip((r - 0.55) / 0.9, 0, 1) ** 1.6
    return Image.fromarray((v * 255).astype(np.uint8)).convert("RGB")

@functools.lru_cache(maxsize=2)
def grain_tiles(W, H, amount=4.0):
    rng = np.random.default_rng(7)
    h, w = H // 2, W // 2  # grain at half res then upscaled -> softer, film-like
    tiles = []
    for _ in range(6):
        g = rng.normal(0, amount, (h, w)).astype(np.float32) + 128
        gi = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        tiles.append(gi.convert("RGB"))
    return tiles

def finish(im, frame_idx, amount=4.0, vig=True, fade=1.0):
    """Grade + vignette + grain (+ fade to black). Returns RGB Image."""
    im = im.convert("RGB", GRADE)
    if vig: im = ImageChops.multiply(im, vignette(CTX.W, CTX.H))
    im = ImageChops.add(im, grain_tiles(CTX.W, CTX.H, amount)[frame_idx % 6], 1.0, -128)
    if fade < 1: im = Image.eval(im, lambda v, f=fade: int(v * f))
    return im

# ---------------------------------------------------------------- snow
class Snow:
    """Falling snow overlay in screen space. density: flakes per frame."""
    def __init__(self, n=220, seed=1, speed=1.0, size=1.0, alpha=200):
        rng = np.random.default_rng(seed)
        self.p = rng.random((n, 5))  # x, y phase, depth, sway phase, sway freq
        self.speed, self.size, self.alpha = speed, size, alpha
    def draw(self, im, T, strength=1.0):
        if strength <= 0.01: return
        W, H, S = CTX.W, CTX.H, CTX.S
        h = 2  # draw at half resolution, blur, upscale: cheap at 4K
        lay = Image.new("L", (W // h, H // h), 0)
        d = ImageDraw.Draw(lay)
        for x0, y0, z, ph, fr in self.p:
            depth = 0.35 + 0.65 * z
            vy = (60 + 140 * depth) * self.speed * S
            y = (y0 * (H + 100 * S) + T * vy) % (H + 100 * S) - 50 * S
            x = (x0 * W + math.sin(T * (0.4 + fr) + ph * 6.28) * 40 * S * depth + T * 15 * S) % W
            r = (2.5 + 7 * depth) * self.size * S / h
            x, y = x / h, y / h
            d.ellipse((x - r, y - r, x + r, y + r), fill=int(self.alpha * (0.5 + 0.5 * depth) * strength))
        lay = lay.filter(ImageFilter.GaussianBlur(1.6 * S / h + 0.4)).resize((W, H), Image.BILINEAR)
        im.paste((250, 252, 255), (0, 0), lay)
