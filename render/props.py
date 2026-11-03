# Noël 1962 — everything drawn in code. Design units: 3840x2160 canvas.
import json, math, os, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from engine import (CTX, ROOT, CACHE, Canvas, Cam, Photo, font, clamp, ease, ease_out, lerp, img_base)

INK = (38, 32, 28)
PAPER = (236, 226, 204)
RED = (150, 32, 30)

def noise(w, h, cell, seed):
    """Smooth value noise in [0,1], size (h,w)."""
    rng = np.random.default_rng(seed)
    g = rng.random((max(2, h // cell + 2), max(2, w // cell + 2))).astype(np.float32)
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255

def paper_texture(w, h, color=PAPER, seed=3, amt=0.07):
    n = noise(w, h, max(4, w // 60), seed) * 0.6 + noise(w, h, max(2, w // 400), seed + 1) * 0.4
    a = np.array(color, np.float32)[None, None, :] * (1 - amt + amt * 2 * n[..., None])
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def wood_texture(w, h, base=(122, 82, 48), seed=5, vertical=False, plank=None):
    """Procedural oak: long fibres along x, faint growth rings, optional planks."""
    rng = np.random.default_rng(seed)
    def streak(cy, cx, sd):  # anisotropic noise: long along x
        g = np.random.default_rng(sd).random((max(2, h // cy), max(2, w // cx))).astype(np.float32)
        return np.asarray(Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255
    fib = streak(3, 90, seed) * 0.45 + streak(8, 240, seed + 1) * 0.35 + streak(40, 600, seed + 2) * 0.2
    y = np.arange(h, dtype=np.float32)[:, None]
    warp = (streak(30, 400, seed + 3) - 0.5) * 3.0
    rings = (np.sin(y / max(h, 1) * 90 + warp * 3) * 0.5 + 0.5) ** 6
    v = fib * 0.8 + rings * 0.25
    if plank:
        idx = (np.arange(h)[:, None] // plank)
        v = v * (0.88 + 0.24 * ((idx * 0.618) % 1.0))
        seam = (np.arange(h)[:, None] % plank) < max(1, plank * 0.01)
        v = np.where(seam, 0.1, v)
    b = np.array(base, np.float32)
    a = b[None, None, :] * (0.55 + 0.7 * v[..., None])
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return im.transpose(Image.ROTATE_90).resize((w, h)) if vertical else im

def radial_glow(w, h, cx, cy, r, color, power=2.0):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** power
    return a

def shade(im, top=0.0, bottom=0.35):
    """Darken towards bottom/top for a lit-from-above feel."""
    w, h = im.size
    g = np.linspace(1 - top, 1 - bottom, h, dtype=np.float32)[:, None, None]
    return Image.fromarray(np.clip(np.asarray(im, np.float32) * g, 0, 255).astype(np.uint8))

def drop_shadow(base, shape_mask, offset, blur, opacity=0.55):
    sh = shape_mask.filter(ImageFilter.GaussianBlur(blur))
    sh = ImageChops.offset(sh, int(offset[0]), int(offset[1])).point(lambda v: int(v * opacity))
    base.paste((0, 0, 0), (0, 0), sh)

def paste_shadowed(im, spr, x, y, off, blur, opacity=0.55, alpha=1.0):
    """Paste RGBA sprite with a soft drop shadow computed locally at 1/4 res."""
    A = spr.getchannel("A")
    q = 4
    pad = int(blur * 2) + 2
    sm = Image.new("L", ((spr.width + 2 * pad) // q + 1, (spr.height + 2 * pad) // q + 1), 0)
    sm.paste(A.resize((max(1, spr.width // q), max(1, spr.height // q))), (pad // q, pad // q))
    sm = sm.filter(ImageFilter.GaussianBlur(max(0.5, blur / q))).resize((spr.width + 2 * pad, spr.height + 2 * pad), Image.BILINEAR)
    sm = sm.point(lambda v: int(v * opacity * alpha))
    im.paste((0, 0, 0), (int(x - pad + off[0]), int(y - pad + off[1])), sm)
    im.paste(spr, (int(x), int(y)), A if alpha >= 0.999 else A.point(lambda v: int(v * alpha)))

def rrect(d, box, r, **kw):
    d.rounded_rectangle([int(v) for v in box], radius=int(r), **kw)

# =============================================================== MAP
MAP_C = (2.6, 46.6)
KY = 190.0
KX = KY * math.cos(math.radians(46.5))
def proj(lon, lat):
    return (1920 + (lon - MAP_C[0]) * KX, 1080 - (lat - MAP_C[1]) * KY)

CITIES = {
    "Paris": (2.35, 48.86), "Strasbourg": (7.75, 48.58), "Bordeaux": (-0.58, 44.84),
    "Clermont-Ferrand": (3.08, 45.78), "Mouthe": (6.19, 46.71), "Marseille": (5.37, 43.30),
    "Lyon": (4.84, 45.76), "Libourne": (-0.24, 44.92),
}

@functools.lru_cache(maxsize=1)
def map_data():
    return json.load(open(os.path.join(ROOT, "assets/france_map.json")))

def france_mask(u):
    """L mask of mainland France + Corsica at u px/unit (flood fill once at 1 px/unit, cached)."""
    path = os.path.join(CACHE, "france_mask_1x.png")
    if not os.path.exists(path):
        M = map_data()
        im = Image.new("L", (3840, 2160), 0)
        d = ImageDraw.Draw(im)
        for p in M["land"]:
            if len(p) >= 4: d.polygon([proj(*q) for q in p], fill=255)
        for p in M["lakes"]:
            if len(p) >= 4: d.polygon([proj(*q) for q in p], fill=0)
        for p in M["borders"]: d.line([proj(*q) for q in p], fill=0, width=3)
        for seed in [proj(2.35, 48.86), proj(9.05, 42.1)]:
            ImageDraw.floodfill(im, (int(seed[0]), int(seed[1])), 128)
        im = im.point(lambda v: 255 if v == 128 else 0)
        im.save(path)
    m = Image.open(path)
    W, H = round(3840 * u), round(2160 * u)
    return m.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(0.6 * u))

class SchoolMap(Canvas):
    """Vintage French school wall map. Overlays: frost front, pins, Mouthe highlight."""
    OVERS = 2.6
    def __init__(self, cam=None, frost=None, pins=(), mouthe=None, glow_paris=False):
        super().__init__(cam)
        self.frost, self.pins, self.mouthe = frost, pins, mouthe
    def base(self, u):
        W, H = round(3840 * u), round(2160 * u)
        M = map_data()
        sea = (186, 207, 206)
        im = paper_texture(W, H, (214, 222, 210), seed=11, amt=0.05)
        # land mask
        land = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(land)
        P = lambda q: tuple(v * u for v in proj(*q))
        for p in M["land"]:
            if len(p) >= 4: d.polygon([P(q) for q in p], fill=255)
        for p in M["lakes"]:
            if len(p) >= 4: d.polygon([P(q) for q in p], fill=0)
        # sea tint + concentric coastal water lines (classic school-map look), computed at 1/4 res
        q = 4
        lm = land.resize((W // q, H // q), Image.BILINEAR)
        seaimg = Image.new("RGB", (W, H), sea)
        im = Image.blend(im, seaimg, 0.55)
        rings = Image.new("L", (W // q, H // q), 0)
        prev = lm
        for i, r in enumerate([5, 9, 15, 23]):
            big = lm.filter(ImageFilter.MaxFilter(2 * int(r * u / q * 1.0) + 1 if int(r * u / q) > 0 else 3))
            edge = ImageChops.subtract(big, big.filter(ImageFilter.MinFilter(3)))
            rings = ImageChops.lighter(rings, edge.point(lambda v, i=i: int(v * (0.55 - 0.1 * i))))
        rings = rings.resize((W, H), Image.BILINEAR)
        im.paste((92, 128, 140), (0, 0), rings)
        # neighbours
        neigh = paper_texture(W, H, (232, 226, 206), seed=12, amt=0.05)
        im.paste(neigh, (0, 0), land)
        # France
        fm = france_mask(u)
        fr = paper_texture(W, H, (228, 196, 138), seed=13, amt=0.08)
        im.paste(fr, (0, 0), fm)
        d = ImageDraw.Draw(im)
        for p in M["lakes"]:
            if len(p) >= 4: d.polygon([P(q) for q in p], fill=sea)
        # borders: dashed dark red
        for p in M["borders"]:
            pts = [P(q) for q in p]
            acc = 0
            for a, b in zip(pts[:-1], pts[1:]):
                seg = math.dist(a, b)
                if int(acc / (9 * u)) % 2 == 0:
                    d.line([a, b], fill=(140, 60, 50), width=max(1, int(2.2 * u)))
                acc += seg
        for p in M["land"]:
            if len(p) >= 4: d.line([P(q) for q in p] + [P(p[0])], fill=(52, 70, 80), width=max(1, int(2.0 * u)))
        # cartouche & frame
        d.rectangle([60 * u, 60 * u, W - 60 * u, H - 60 * u], outline=INK, width=int(5 * u))
        d.rectangle([80 * u, 80 * u, W - 80 * u, H - 80 * u], outline=INK, width=int(2 * u))
        f = font("title", 150 * u / CTX.S)
        d.text((3330 * u, 200 * u), "FRANCE", font=f, fill=INK, anchor="mm")
        f2 = font("italic", 54 * u / CTX.S)
        d.text((3330 * u, 330 * u), "Carte physique et politique", font=f2, fill=INK, anchor="mm")
        d.line([3050 * u, 280 * u, 3610 * u, 280 * u], fill=INK, width=int(3 * u))
        # sea names
        fi = font("italic", 62 * u / CTX.S)
        for name, lon, lat in [("Océan Atlantique", -4.2, 45.6), ("Manche", -1.6, 50.2), ("Mer Méditerranée", 6.0, 42.4)]:
            d.text(P((lon, lat)), name, font=fi, fill=(70, 100, 112), anchor="mm")
        # light paper wear
        im = Image.blend(im, paper_texture(W, H, (240, 232, 214), seed=14, amt=0.15), 0.12)
        return im

    def overlay(self, im, t, k, P, s):
        W, H = CTX.W, CTX.H
        if self.frost:  # (T0, T1, T_abs_start) ice front sweeping east -> west over France
            t0, t1 = self.frost
            if not hasattr(self, "_fm") or self._fm[0] != (W, H):
                fm = france_mask(1.0)
                # static camera assumed for the frost shot: map mask through the current crop
                x0, y0 = P(0, 0); x1, y1 = P(3840, 2160)
                fm = fm.resize((round(x1 - x0), round(y1 - y0)), Image.BILINEAR)
                big = Image.new("L", (W, H), 0); big.paste(fm, (round(x0), round(y0)))
                n = noise(W, H, max(8, W // 30), 21)
                self._fm = ((W, H), np.asarray(big, np.float32) / 255, n)
            fm, n = self._fm[1][::2, ::2], self._fm[2][::2, ::2]
            e = ease(clamp((t - t0) / (t1 - t0)))
            lon_front = lerp(10.5, -6.0, e)
            fx = P(*proj(lon_front, 46))[0] / 2
            xs = np.arange(fm.shape[1], dtype=np.float32)[None, :]
            ramp = np.clip((xs - fx + (n - 0.5) * 250 * CTX.S) / (130 * CTX.S), 0, 1)
            a = fm * ramp * (0.72 + 0.18 * n)
            mask = Image.fromarray((a * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
            im.paste((205, 226, 246), (0, 0), mask)
        d = ImageDraw.Draw(im)
        for (name, label, tp) in self.pins:
            if t < tp: continue
            e = ease_out(clamp((t - tp) / 0.45))
            x, y = P(*proj(*CITIES[name]))
            y = y - (1 - e) * 140 * CTX.S
            r = 15 * CTX.S * (1 + 0.15 * (s / CTX.S - 1))
            d.line([x, y, x, y - 70 * CTX.S], fill=INK, width=int(5 * CTX.S))
            d.ellipse([x - r, y - 70 * CTX.S - r * 1.6, x + r * 1.6 - r * 0.6, y - 70 * CTX.S + r * 0.6], fill=RED, outline=INK, width=int(3 * CTX.S))
            d.ellipse([x - 6 * CTX.S, y - 6 * CTX.S, x + 6 * CTX.S, y + 6 * CTX.S], fill=INK)
            if label:
                f = font("type", 74)
                tx, ty = x + 40 * CTX.S, y - 120 * CTX.S
                if name in ("Bordeaux",): tx, ty = x - 40 * CTX.S, y - 120 * CTX.S
                anchor = "rm" if name == "Bordeaux" else "lm"
                a = clamp((t - tp - 0.1) / 0.35)
                if a <= 0: continue
                bb = d.textbbox((0, 0), label, font=f, anchor="lt")
                pad = int(18 * CTX.S)
                lay = Image.new("RGBA", (bb[2] + 2 * pad + 4, bb[3] + 2 * pad + 4), (0, 0, 0, 0))
                ld = ImageDraw.Draw(lay)
                ld.rounded_rectangle([1, 1, lay.width - 2, lay.height - 2], radius=10 * CTX.S, fill=(246, 240, 226, 235), outline=(38, 32, 28, 255), width=int(3 * CTX.S))
                ld.text((pad + 2, pad + 2), label, font=f, fill=(150, 28, 26, 255), anchor="lt")
                lx = tx if anchor == "lm" else tx - lay.width
                A = lay.getchannel("A") if a >= 1 else lay.getchannel("A").point(lambda v: int(v * a))
                im.paste(lay, (int(lx), int(ty - lay.height / 2)), A)
                d = ImageDraw.Draw(im)
        if self.mouthe and t >= self.mouthe:
            x, y = P(*proj(*CITIES["Mouthe"]))
            a = clamp((t - self.mouthe) / 0.5)
            for i in range(3):
                rr = (60 + 50 * i + 30 * math.sin(t * 3 + i)) * CTX.S
                d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(150, 28, 26), width=int((6 - i * 1.5) * CTX.S * a + 1))
            d.ellipse([x - 14 * CTX.S, y - 14 * CTX.S, x + 14 * CTX.S, y + 14 * CTX.S], fill=RED, outline=INK, width=int(3 * CTX.S))

# =============================================================== CALENDARS
MOIS = ["JANVIER", "FÉVRIER", "MARS", "AVRIL", "MAI", "JUIN", "JUILLET", "AOÛT", "SEPTEMBRE", "OCTOBRE", "NOVEMBRE", "DÉCEMBRE"]
JOURS = ["LUNDI", "MARDI", "MERCREDI", "JEUDI", "VENDREDI", "SAMEDI", "DIMANCHE"]

def month_sheet(year, month, u, w=1500, h=1900):
    """A wall-calendar month page (design w x h) at u px/unit, RGBA."""
    import calendar
    W, H = round(w * u), round(h * u)
    im = paper_texture(W, H, (242, 236, 222), seed=year * 13 + month, amt=0.05).convert("RGBA")
    d = ImageDraw.Draw(im)
    # header band
    d.rectangle([0, 0, W, 330 * u], fill=(150, 30, 28, 255))
    d.text((W / 2, 150 * u), MOIS[month - 1], font=font("title", 170 * u / CTX.S), fill=(246, 238, 222), anchor="mm")
    d.text((W / 2, 280 * u), str(year), font=font("serif", 80 * u / CTX.S), fill=(246, 230, 210), anchor="mm")
    cols = ["L", "M", "M", "J", "V", "S", "D"]
    cw = (w - 120) / 7
    for i, c in enumerate(cols):
        d.text(((60 + cw * (i + 0.5)) * u, 420 * u), c, font=font("title", 64 * u / CTX.S), fill=(150, 30, 28) if i == 6 else INK, anchor="mm")
    d.line([60 * u, 470 * u, (w - 60) * u, 470 * u], fill=INK, width=max(1, int(3 * u)))
    weeks = calendar.Calendar(0).monthdayscalendar(year, month)
    rh = (h - 560) / max(5, len(weeks))
    for r, wk in enumerate(weeks):
        for i, dd in enumerate(wk):
            if dd == 0: continue
            x, y = (60 + cw * (i + 0.5)) * u, (540 + rh * r + rh * 0.4) * u
            d.text((x, y), str(dd), font=font("serif", 110 * u / CTX.S), fill=(150, 30, 28) if i == 6 else INK, anchor="mm")
        d.line([60 * u, (520 + rh * (r + 1)) * u, (w - 60) * u, (520 + rh * (r + 1)) * u], fill=(190, 180, 160), width=max(1, int(2 * u)))
    # binding rings strip
    for i in range(6):
        x = (w / 2 - 375 + 150 * i) * u
        d.ellipse([x - 22 * u, -10 * u, x + 22 * u, 34 * u], fill=(60, 55, 50))
    return im

def ephemeride_page(dayname, day, monthyear, u, w=1300, h=1500):
    W, H = round(w * u), round(h * u)
    im = paper_texture(W, H, (244, 238, 226), seed=day * 7, amt=0.04).convert("RGBA")
    d = ImageDraw.Draw(im)
    d.text((W / 2, 200 * u), dayname, font=font("title", 130 * u / CTX.S), fill=INK, anchor="mm")
    d.line([200 * u, 300 * u, (w - 200) * u, 300 * u], fill=INK, width=max(1, int(3 * u)))
    d.text((W / 2, 760 * u), str(day), font=font("title", 720 * u / CTX.S), fill=(150, 30, 28), anchor="mm")
    d.text((W / 2, 1290 * u), monthyear, font=font("serif", 110 * u / CTX.S), fill=INK, anchor="mm")
    return im

def wall(u, color=(96, 70, 52), seed=31):
    """Old wallpaper with faint stripes/fleurs, lit from top-left."""
    W, H = round(3840 * u), round(2160 * u)
    im = paper_texture(W, H, color, seed=seed, amt=0.10)
    d = ImageDraw.Draw(im)
    for x in range(0, 3840, 160):
        d.line([x * u, 0, x * u, H], fill=tuple(int(c * 0.9) for c in color), width=max(1, int(26 * u)))
    for x in range(80, 3840, 160):
        for y in range(80, 2160, 200):
            r = 10 * u
            d.ellipse([x * u - r, y * u - r, x * u + r, y * u + r], fill=tuple(min(255, int(c * 1.15)) for c in color))
    g = radial_glow(W, H, W * 0.45, H * 0.35, W * 0.8, None, 1.2)
    a = np.asarray(im, np.float32) * (0.45 + 0.65 * g[..., None])
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

def paste_sheet(base, sheet, cx, cy, u, angle=0.0, shadow=True):
    sh = sheet.rotate(angle, expand=True, resample=Image.BICUBIC) if angle else sheet
    x, y = int(cx * u - sh.width / 2), int(cy * u - sh.height / 2)
    if shadow:
        m = Image.new("L", base.size, 0); m.paste(sh.getchannel("A"), (x, y))
        drop_shadow(base, m, (25 * u, 35 * u), 30 * u, 0.6)
    base.paste(sh, (x, y), sh)

class MonthCalendar(Canvas):
    """Wall calendar. months: list of (year, month, t_flip) — page flips at t_flip (shot-relative)."""
    def __init__(self, months, cam=None):
        super().__init__(cam); self.months = months; self._sheets = {}
    def base(self, u):
        return wall(u)
    def sheet(self, i, u):
        key = (i, u)
        if key not in self._sheets: self._sheets[key] = month_sheet(*self.months[i][:2], u)
        return self._sheets[key]
    def overlay(self, im, t, k, P, s):
        cur = 0
        for i, m in enumerate(self.months):
            if t >= m[2]: cur = i
        x0, y0 = P(1920, 1100)
        sh = self.sheet(cur, s)
        im.paste(sh, (int(x0 - sh.width / 2), int(y0 - sh.height / 2)), sh)
        # previous page flying away
        if cur > 0:
            e = clamp((t - self.months[cur][2]) / 0.9)
            if e < 1:
                prev = self.sheet(cur - 1, s)
                ang = 25 * ease(e)
                pr = prev.rotate(ang, expand=True, resample=Image.BILINEAR)
                a = pr.getchannel("A").point(lambda v: int(v * (1 - e)))
                im.paste(pr, (int(x0 - pr.width / 2 + 900 * e * s), int(y0 - pr.height / 2 - 1300 * ease(e) * s)), a)

class Ephemeride(Canvas):
    """Tear-off day calendar: page `prev` tears away at t_flip to reveal `cur`."""
    def __init__(self, prev, cur, t_flip, cam=None):
        super().__init__(cam); self.prev, self.cur, self.t_flip = prev, cur, t_flip; self._p = {}
    def base(self, u):
        im = wall(u, (70, 82, 92), seed=41)
        d = ImageDraw.Draw(im)
        # wooden backing board
        rrect(d, [1180 * u, 220 * u, 2660 * u, 2000 * u], 30 * u, fill=(92, 60, 36))
        d.ellipse([1890 * u, 250 * u, 1950 * u, 310 * u], fill=(40, 30, 24))
        return im
    def page(self, which, s):
        key = (which, s)
        if key not in self._p:
            self._p[key] = ephemeride_page(*(self.prev if which == 0 else self.cur), s)
        return self._p[key]
    def overlay(self, im, t, k, P, s):
        x0, y0 = P(1920, 1180)
        cur = self.page(1, s)
        im.paste(cur, (int(x0 - cur.width / 2), int(y0 - cur.height / 2)), cur)
        e = clamp((t - self.t_flip) / 1.0)
        if e < 1:
            pv = self.page(0, s)
            ang = -18 * ease(e)
            pr = pv.rotate(ang, expand=True, resample=Image.BILINEAR)
            a = pr.getchannel("A").point(lambda v: int(v * (1 - e ** 2)))
            im.paste(pr, (int(x0 - pr.width / 2 - 300 * ease(e) * s), int(y0 - pr.height / 2 + 1500 * ease(e) ** 2 * s)), a)

# =============================================================== TITLE CARD
class TitleCard(Canvas):
    def base(self, u):
        W, H = round(3840 * u), round(2160 * u)
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        top, bot = np.array([10, 16, 34], np.float32), np.array([30, 40, 66], np.float32)
        a = top * (1 - y) + bot * y
        a = np.broadcast_to(a, (H, W, 3)).copy()
        g = radial_glow(W, H, W / 2, H * 0.48, W * 0.55, None, 1.6)
        a += g[..., None] * np.array([40, 34, 24], np.float32)
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        gold = (226, 196, 130)
        d.text((W / 2, H * 0.43), "NOËL", font=font("title", 420 * u / CTX.S), fill=gold, anchor="mm")
        d.text((W / 2, H * 0.66), "1962", font=font("serif", 230 * u / CTX.S), fill=(236, 228, 210), anchor="mm")
        d.line([W * 0.40, H * 0.555, W * 0.60, H * 0.555], fill=gold, width=max(1, int(4 * u)))
        return im

# =============================================================== PAYSLIP & COINS
class Payslip(Canvas):
    CH = 3000  # taller than the frame: the camera tilts down the sheet
    def base(self, u):
        im = wood_texture(round(3840 * u), round(self.CH * u), (110, 74, 44), seed=51, plank=round(540 * u))
        W, H = im.size
        sheet = paper_texture(round(1900 * u), round(2600 * u), (238, 232, 214), seed=52, amt=0.05).convert("RGBA")
        d = ImageDraw.Draw(sheet)
        t = lambda xy, s_, txt, sz=64, face="type", fill=INK, anchor="la": d.text((xy[0] * u, xy[1] * u), txt, font=font(face, sz * u / CTX.S), fill=fill, anchor=anchor)
        t((950, 150), None, "BULLETIN DE PAIE", 110, anchor="mm")
        d.line([120 * u, 240 * u, 1780 * u, 240 * u], fill=INK, width=max(1, int(4 * u)))
        rows = [("Établissement", "....................................."),
                ("Nom", "....................................."),
                ("Emploi", "....................................."),
                ("Période", "Décembre 1962"),
                ("Durée hebdomadaire", "46 heures"),
                ("Heures supplémentaires", "..........."),
                ("Salaire de base", "........... NF"),
                ("Retenues Sécurité sociale", "........... NF"),
                ("NET À PAYER", "........... NF")]
        y = 360
        for a, b in rows:
            hi = b in ("46 heures",)
            t((140, y), None, a, 62)
            t((1760, y), None, b, 62, fill=RED if hi else INK, anchor="ra")
            d.line([140 * u, (y + 95) * u, 1760 * u, (y + 95) * u], fill=(170, 160, 140), width=max(1, int(2 * u)))
            y += 200
        # rubber stamp
        d.ellipse([1180 * u, 2200 * u, 1700 * u, 2480 * u], outline=(70, 70, 150, 200), width=int(10 * u))
        t((1440, 2340), None, "PAYÉ", 90, fill=(70, 70, 150), anchor="mm")
        sheet = sheet.rotate(-3, expand=True, resample=Image.BICUBIC)
        paste_sheet(im, sheet, 1920, 1500, u, 0)
        return shade(im, 0, 0.25)

COINS = [  # label, sub, metal, radius, centre
    ("1", "FRANC", "nickel", 240, (1350, 900)),
    ("50", "CENTIMES", "bronze", 225, (2050, 760)),
    ("20", "CENTIMES", "bronze", 210, (2600, 1150)),
    ("10", "CENTIMES", "bronze", 190, (1800, 1430)),
    ("5", "CENTIMES", "bronze", 170, (2350, 1650)),
    ("1", "FRANC", "nickel", 240, (1100, 1500)),
]
def coin(r, metal, label, sub, u):
    R = round(r * u)
    y, x = np.mgrid[-R:R, -R:R].astype(np.float32)
    d = np.sqrt(x * x + y * y) / R
    col = np.array((200, 200, 196) if metal == "nickel" else (214, 180, 96), np.float32)
    light = 0.75 + 0.35 * (-(x + y) / (2 * R)) + 0.1 * np.cos(d * 9)
    rim = (d > 0.86) & (d < 1)
    light = np.where(rim, light * 1.15, light)
    a = np.clip(col[None, None, :] * light[..., None], 0, 255)
    alpha = np.clip((1 - d) * R, 0, 1) * 255
    im = Image.fromarray(np.dstack([a, alpha]).astype(np.uint8), "RGBA")
    dd = ImageDraw.Draw(im)
    dark = tuple(int(c * 0.45) for c in col)
    dd.text((R, R * 0.92), label, font=font("title", r * 0.85 * u / CTX.S), fill=dark, anchor="mm")
    dd.text((R, R * 1.45), sub, font=font("title", r * 0.17 * u / CTX.S), fill=dark, anchor="mm")
    dd.ellipse([R * 0.1, R * 0.1, R * 1.9, R * 1.9], outline=dark, width=max(1, int(3 * u)))
    return im

class Coins(Canvas):
    def base(self, u):
        im = wood_texture(round(3840 * u), round(2160 * u), (78, 50, 32), seed=61, plank=round(700 * u))
        for lab, sub, metal, r, (cx, cy) in COINS:
            c = coin(r, metal, lab, sub, u)
            m = Image.new("L", im.size, 0); m.paste(c.getchannel("A"), (int(cx * u - c.width / 2), int(cy * u - c.height / 2)))
            drop_shadow(im, m, (14 * u, 20 * u), 14 * u, 0.6)
            im.paste(c, (int(cx * u - c.width / 2), int(cy * u - c.height / 2)), c)
        g = radial_glow(im.width, im.height, im.width * 0.48, im.height * 0.45, im.width * 0.7, None, 1.0)
        a = np.asarray(im, np.float32) * (0.35 + 0.8 * g[..., None])
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

# =============================================================== TELEVISION
TV_SCREEN = (1400, 640, 2320, 1340)  # design box of the picture tube
class TV(Canvas):
    """1960s TV set in a dim room. mode: 'off', 'on', 'turnon' (at t_on), 'night' (stars/moon/cloud)."""
    def __init__(self, mode="on", t_on=0.0, cam=None, room=(64, 50, 40)):
        super().__init__(cam); self.mode, self.t_on, self.room = mode, t_on, room
    def base(self, u):
        im = wall(u, self.room, seed=71)
        im = Image.fromarray((np.asarray(im, np.float32) * 0.55).astype(np.uint8))
        d = ImageDraw.Draw(im)
        # sideboard
        d.rectangle([700 * u, 1640 * u, 3140 * u, 2160 * u], fill=(70, 44, 26))
        d.rectangle([700 * u, 1640 * u, 3140 * u, 1690 * u], fill=(98, 64, 38))
        # lace doily
        d.ellipse([1420 * u, 1600 * u, 2440 * u, 1700 * u], fill=(214, 206, 190))
        # cabinet
        cab = wood_texture(round(1500 * u), round(1180 * u), (104, 66, 36), seed=72)
        m = Image.new("L", cab.size, 0); rrect(ImageDraw.Draw(m), [0, 0, cab.width - 1, cab.height - 1], 70 * u, fill=255)
        mm = Image.new("L", im.size, 0); mm.paste(m, (round(1180 * u), round(470 * u)))
        drop_shadow(im, mm, (30 * u, 40 * u), 40 * u, 0.7)
        im.paste(cab, (round(1180 * u), round(470 * u)), m)
        d = ImageDraw.Draw(im)
        x0, y0, x1, y1 = TV_SCREEN
        rrect(d, [(x0 - 60) * u, (y0 - 60) * u, (x1 + 60) * u, (y1 + 60) * u], 120 * u, fill=(38, 30, 24))
        rrect(d, [x0 * u, y0 * u, x1 * u, y1 * u], 110 * u, fill=(46, 50, 50))
        # knobs + speaker grille
        for i, yy in enumerate([760, 980]):
            d.ellipse([2420 * u, yy * u, 2560 * u, (yy + 140) * u], fill=(210, 200, 180), outline=(60, 50, 40), width=int(5 * u))
            d.line([2490 * u, (yy + 20) * u, 2490 * u, (yy + 70) * u], fill=(60, 50, 40), width=int(8 * u))
        for yy in range(1200, 1500, 34):
            d.line([2400 * u, yy * u, 2580 * u, yy * u], fill=(60, 42, 26), width=int(10 * u))
        # antenna
        d.line([1930 * u, 470 * u, 1650 * u, 100 * u], fill=(170, 170, 170), width=int(9 * u))
        d.line([1930 * u, 470 * u, 2250 * u, 120 * u], fill=(170, 170, 170), width=int(9 * u))
        d.ellipse([1860 * u, 420 * u, 2000 * u, 490 * u], fill=(40, 34, 30))
        # legs
        for lx in (1300, 2560):
            d.polygon([(lx * u, 1650 * u), ((lx + 50) * u, 1650 * u), ((lx + 30) * u, 1640 * u)], fill=(40, 26, 16))
        return im
    def screen(self, w, h, t):
        """Screen content (RGB) w x h at time t (shot-relative)."""
        mode = self.mode
        level = 1.0
        if mode == "turnon":
            e = clamp((t - self.t_on) / 1.2)
            if t < self.t_on: mode = "off"
            level = e
        if mode == "off":
            a = np.full((h, w, 3), 52, np.float32)
            g = radial_glow(w, h, w * 0.35, h * 0.3, w * 0.6, None, 2)
            a += g[..., None] * 40
            return Image.fromarray(a.astype(np.uint8))
        rng = np.random.default_rng(abs(int(t * 30)))
        y = np.arange(h, dtype=np.float32)[:, None]
        scan = 0.88 + 0.12 * np.sin(y * math.pi / max(2, h / 260))
        if mode == "night":
            a = np.full((h, w), 70, np.float32)
            a += radial_glow(w, h, w * 0.7, h * 0.3, w * 0.5, None, 1.5) * 90
            im = Image.fromarray(a.astype(np.uint8))
            d = ImageDraw.Draw(im)
            srng = np.random.default_rng(3)
            for sx, sy, sr in srng.random((40, 3)):
                tw = 0.6 + 0.4 * math.sin(t * 3 + sx * 20)
                r = (2 + sr * 4) * w / 920
                d.ellipse([sx * w - r, sy * h * 0.6 - r, sx * w + r, sy * h * 0.6 + r], fill=int(200 * tw + 40))
            # crescent moon
            mx, my, mr = w * 0.72, h * 0.28, h * 0.13
            d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=235)
            d.ellipse([mx - mr * 0.55, my - mr * 1.1, mx + mr * 1.45, my + mr * 0.9], fill=int(a[int(my), int(mx)]))
            # a cloud drifting
            cx = w * (0.25 + 0.05 * math.sin(t * 0.2)); cy = h * 0.7
            for ox, oy, rr in [(0, 0, 0.12), (0.12, -0.05, 0.15), (0.26, 0, 0.12), (0.13, 0.04, 0.13)]:
                d.ellipse([cx + (ox - rr) * w, cy + (oy - rr) * w, cx + (ox + rr) * w, cy + (oy + rr) * w * 0.7], fill=215)
            a = np.asarray(im, np.float32)
        else:
            a = np.full((h, w), 150, np.float32)
            a += radial_glow(w, h, w * 0.5, h * 0.5, w * 0.7, None, 1.2) * 70
        a = a * scan + rng.normal(0, 7, (h, w)).astype(np.float32)
        a *= 0.97 + 0.03 * math.sin(t * 37)
        a = 52 + (a - 52) * level
        if self.mode == "turnon" and t >= self.t_on:
            e = clamp((t - self.t_on) / 0.5)
            yy = np.abs(np.arange(h, dtype=np.float32) - h / 2)[:, None] / (h / 2)
            a = np.where(yy <= e + 0.02, a, 52)
        # subtle bluish tint like phosphor
        rgb = np.dstack([a * 0.96, a * 0.99, a * 1.03])
        return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
    def overlay(self, im, t, k, P, s):
        x0, y0 = P(TV_SCREEN[0], TV_SCREEN[1]); x1, y1 = P(TV_SCREEN[2], TV_SCREEN[3])
        w, h = int(x1 - x0), int(y1 - y0)
        scr = self.screen(max(8, w // 2), max(8, h // 2), t).resize((w, h), Image.BILINEAR)
        mk = (w, h, round(s, 3))
        if getattr(self, "_mk", None) != mk:
            m = Image.new("L", (w, h), 0)
            rrect(ImageDraw.Draw(m), [0, 0, w - 1, h - 1], 110 * s, fill=255)
            m = m.filter(ImageFilter.GaussianBlur(3 * s))
            hl = Image.new("L", (w // 4, h // 4), 0)  # glass reflection highlight
            ImageDraw.Draw(hl).ellipse([w * 0.05 / 4, h * 0.04 / 4, w * 0.55 / 4, h * 0.30 / 4], fill=40)
            hl = hl.filter(ImageFilter.GaussianBlur(30 * s / 4)).resize((w, h), Image.BILINEAR)
            self._mk, self._masks = mk, (m, hl)
        m, hl = self._masks
        scr.paste((255, 255, 255), (0, 0), hl)
        im.paste(scr, (int(x0), int(y0)), m)
        # light spill on room when on
        if self.mode != "off" and (self.mode != "turnon" or t > self.t_on):
            lvl = 1.0 if self.mode != "turnon" else clamp((t - self.t_on) / 1.2)
            if not hasattr(self, "_spill") or self._spill[0] != im.size:
                W, H = im.size
                g = radial_glow(W // 4, H // 4, (x0 + x1) / 8, (y0 + y1) / 8, W / 4 * 0.6, None, 1.8)
                self._spill = (im.size, Image.fromarray((g * 70).astype(np.uint8)).resize(im.size, Image.BILINEAR))
            sp = self._spill[1].point(lambda v: int(v * lvl * (0.95 + 0.05 * math.sin(t * 23))))
            im.paste((200, 214, 230), (0, 0), sp)

# =============================================================== TYPED INDEX CARD
def photo_print(path, h, s, crop=None, angle=3.0):
    """Old black & white print with a white border, h design units tall -> RGBA."""
    from PIL import ImageOps
    im = Image.open(os.path.join(ROOT, path)).convert("L")
    if crop: im = im.crop(crop)
    im = ImageOps.autocontrast(im, cutoff=1)
    H = round(h * s); W = round(H * im.width / im.height)
    im = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2 * s + 0.5, percent=40, threshold=2))
    im = ImageOps.colorize(im, (24, 20, 18), (238, 232, 218))
    b = round(h * 0.05 * s)
    pr = Image.new("RGBA", (W + 2 * b, H + 3 * b), (244, 240, 230, 255))
    pr.paste(im, (b, b))
    return pr.rotate(angle, expand=True, resample=Image.BICUBIC)

class TypedCard(Canvas):
    """Index card on a desk; lines typed at `cps` chars/s starting at t0 (shot-relative).
    Optional photo=(path, crop, angle): a period print laid on the card when typing starts."""
    def __init__(self, lines, t0=0.3, cps=16, cam=None, photo=None):
        super().__init__(cam); self.lines, self.t0, self.cps, self.photo = lines, t0, cps, photo
        self._pr = None
    def base(self, u):
        im = wood_texture(round(3840 * u), round(2160 * u), (96, 62, 36), seed=81, plank=round(600 * u))
        card = paper_texture(round(2500 * u), round(1500 * u), (240, 234, 216), seed=82, amt=0.04).convert("RGBA")
        d = ImageDraw.Draw(card)
        d.line([0, 260 * u, card.width, 260 * u], fill=(190, 60, 60), width=int(5 * u))
        for y in range(380, 1500, 120):
            d.line([0, y * u, card.width, y * u], fill=(150, 170, 200), width=max(1, int(2 * u)))
        d.text((2380 * u, 130 * u), "P.T.T. — 1962", font=font("type", 56 * u / CTX.S), fill=(110, 100, 90), anchor="rm")
        paste_sheet(im, card.rotate(1.5, expand=True, resample=Image.BICUBIC), 1920, 1080, u)
        g = radial_glow(im.width, im.height, im.width * 0.5, im.height * 0.42, im.width * 0.65, None, 1.0)
        a = np.asarray(im, np.float32) * (0.4 + 0.75 * g[..., None])
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    def overlay(self, im, t, k, P, s):
        if self.photo:
            a = ease_out(clamp((t - self.t0 + 0.6) / 0.7))
            if a > 0:
                if self._pr is None or self._pr[0] != round(s, 4):
                    path, crop, ang = self.photo
                    self._pr = (round(s, 4), photo_print(path, 1150, s, crop, ang))
                pr = self._pr[1]
                x, y = P(2660, 1080 - (1 - a) * 120)
                paste_shadowed(im, pr, x - pr.width / 2, y - pr.height / 2, (22 * s, 30 * s), 26 * s, 0.6, a)
        n = int((t - self.t0) * self.cps)
        if n <= 0: return
        lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        y = 760
        for i, (txt, sz) in enumerate(self.lines):
            show = txt[:max(0, n)]; n -= len(txt) + 4
            x, yy = P(860, y if i == 0 else y)
            d.text((x, yy), show, font=font("type", sz * s / CTX.S), fill=(30, 28, 34, 245) if i == 0 else (60, 56, 64, 240), anchor="ls")
            y += 210 if i == 0 else 130
        lay = lay.rotate(-1.5, center=P(1920, 1080), resample=Image.BICUBIC)
        im.paste(lay, (0, 0), lay)

# =============================================================== LETTER
class Letter(Canvas):
    """Envelope 'Au Père Noël' and a hand-written reply sliding out (illegible ink lines, no invented text)."""
    def __init__(self, t_out=0.5, cam=None):
        super().__init__(cam); self.t_out = t_out
    def base(self, u):
        im = wood_texture(round(3840 * u), round(2160 * u), (104, 70, 42), seed=91, plank=round(560 * u))
        g = radial_glow(im.width, im.height, im.width * 0.5, im.height * 0.45, im.width * 0.7, None, 1.0)
        return Image.fromarray(np.clip(np.asarray(im, np.float32) * (0.4 + 0.75 * g[..., None]), 0, 255).astype(np.uint8))
    @functools.lru_cache(maxsize=4)
    def sheets(self, s):
        letter = paper_texture(round(1500 * s), round(1900 * s), (246, 242, 230), seed=92, amt=0.03).convert("RGBA")
        d = ImageDraw.Draw(letter)
        rng = np.random.default_rng(5)
        y = 260
        while y < 1700:
            x = 150 + (60 if y == 260 else 0)
            xe = 1350 - rng.random() * (500 if rng.random() < 0.2 else 120)
            pts = []
            while x < xe:
                pts.append(((x) * s, (y + math.sin(x * 0.09 + y) * 14 + rng.normal(0, 4)) * s))
                x += 9
                if rng.random() < 0.06: x += 30; d.line(pts, fill=(36, 54, 120), width=max(1, int(5 * s)), joint="curve"); pts = []
            if len(pts) > 1: d.line(pts, fill=(36, 54, 120), width=max(1, int(5 * s)), joint="curve")
            y += 120
        env = paper_texture(round(2000 * s), round(1150 * s), (226, 214, 186), seed=93, amt=0.05).convert("RGBA")
        d = ImageDraw.Draw(env)
        d.text((1000 * s, 620 * s), "Au Père Noël", font=font("italic", 150 * s / CTX.S), fill=(36, 54, 120), anchor="mm")
        d.rectangle([1650 * s, 90 * s, 1890 * s, 380 * s], fill=(160, 50, 40), outline=(240, 230, 210), width=int(10 * s))
        d.text((1770 * s, 235 * s), "0,25", font=font("title", 70 * s / CTX.S), fill=(240, 230, 210), anchor="mm")
        return letter, env
    def overlay(self, im, t, k, P, s):
        letter, env = self.sheets(round(s, 4))
        e = ease_out(clamp((t - self.t_out) / 2.5))
        ex, ey = P(1450, 1420)
        lx, ly = P(1450 + 1000 * e, 1380 - 330 * e)
        key = round(e, 2)
        if getattr(self, "_lk", None) != (key, round(s, 4)):
            lr = letter.rotate(-5 * key, expand=True, resample=Image.BILINEAR)
            self._lr = lr.resize((int(lr.width * 0.88), int(lr.height * 0.88)), Image.BILINEAR); self._lk = (key, round(s, 4))
        lr = self._lr
        ep = (ex - env.width / 2, ey - env.height / 2); lp = (lx - lr.width / 2, ly - lr.height / 2)
        if e < 0.5:  # letter starts behind the envelope
            paste_shadowed(im, lr, *lp, (15 * s, 22 * s), 25 * s, 0.4)
            paste_shadowed(im, env, *ep, (20 * s, 30 * s), 25 * s, 0.6)
        else:
            paste_shadowed(im, env, *ep, (20 * s, 30 * s), 25 * s, 0.6)
            paste_shadowed(im, lr, *lp, (20 * s, 30 * s), 25 * s, 0.5)

# =============================================================== SHOES
SHOE_COLORS = [(52, 34, 24), (88, 46, 30), (30, 30, 34), (120, 40, 36), (70, 52, 40), (96, 30, 40), (40, 56, 80), (130, 90, 60), (150, 50, 60)]
def shoe(L, color, s, kind=0):
    """Side-view child's shoe/boot of length L design units -> RGBA (toe to the right)."""
    w, h = round(L * 1.12 * s), round(L * 0.9 * s)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    X = lambda v: v * L * s
    top = 0.18 if kind != 2 else 0.02
    upper = [(X(0.04), X(0.78)), (X(0.03), X(top + 0.14)), (X(0.10), X(top + 0.02)), (X(0.34), X(top)),
             (X(0.40), X(0.40)), (X(0.66), X(0.44)), (X(0.90), X(0.50)), (X(1.04), X(0.62)), (X(1.05), X(0.78))]
    d.polygon(upper, fill=color)
    d.chord([X(0.62), X(0.42), X(1.08), X(1.0)], 180, 360, fill=color)  # rounded toe
    hi = tuple(min(255, int(c * 1.5 + 30)) for c in color)
    lo = tuple(int(c * 0.6) for c in color)
    d.chord([X(0.70), X(0.48), X(1.03), X(0.86)], 200, 320, fill=hi)  # toe shine
    d.line([(X(0.05), X(0.60)), (X(0.38), X(0.62)), (X(0.68), X(0.66))], fill=lo, width=max(1, int(L * 0.02 * s)))  # stitching
    d.rounded_rectangle([X(0.0), X(0.76), X(1.08), X(0.86)], radius=X(0.04), fill=(34, 26, 20))  # sole
    d.rectangle([X(0.02), X(0.82), X(0.26), X(0.90)], fill=(34, 26, 20))  # heel
    if kind == 1:  # strap
        d.line([(X(0.34), X(0.24)), (X(0.56), X(0.44))], fill=lo, width=max(1, int(L * 0.06 * s)))
        d.ellipse([X(0.36), X(0.25), X(0.43), X(0.32)], fill=(214, 200, 150))
    else:  # laces
        for i in range(4):
            x = 0.40 + i * 0.06
            d.line([(X(x), X(0.28 + i * 0.03)), (X(x + 0.06), X(0.44 + i * 0.01))], fill=(226, 216, 196), width=max(1, int(L * 0.016 * s)))
    return im

class Shoes(Canvas):
    """Row of shoes by the fireplace. n pairs appear between appear=(t0,t1); filled=True adds gifts."""
    def __init__(self, n=8, appear=None, filled=False, single=False, cam=None):
        super().__init__(cam); self.n, self.appear, self.filled, self.single = n, appear, filled, single
        self._sprites = {}
    def base(self, u):
        W, H = round(3840 * u), round(2160 * u)
        im = Image.new("RGB", (W, H))
        # fireplace stone wall upper part
        st = paper_texture(W, round(1300 * u), (120, 108, 94), seed=101, amt=0.18)
        d = ImageDraw.Draw(st)
        for yy in range(0, 1300, 140):
            d.line([0, yy * u, W, yy * u], fill=(80, 70, 60), width=max(1, int(6 * u)))
            off = 0 if (yy // 140) % 2 else 160
            for xx in range(off, 3840, 320):
                d.line([xx * u, yy * u, xx * u, (yy + 140) * u], fill=(80, 70, 60), width=max(1, int(6 * u)))
        im.paste(st, (0, 0))
        # hearth opening with ember glow
        hearth = Image.new("RGB", (round(1500 * u), round(900 * u)), (20, 12, 8))
        g = radial_glow(hearth.width, hearth.height, hearth.width / 2, hearth.height * 0.95, hearth.width * 0.55, None, 1.4)
        ha = np.asarray(hearth, np.float32) + g[..., None] * np.array([190, 80, 20], np.float32)
        im.paste(Image.fromarray(np.clip(ha, 0, 255).astype(np.uint8)), (round(1170 * u), round(400 * u)))
        # floor: parquet
        fl = wood_texture(W, round(860 * u), (128, 86, 50), seed=102, plank=round(110 * u))
        im.paste(fl, (0, round(1300 * u)))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 1270 * u, W, 1320 * u], fill=(70, 60, 52))  # hearth stone ledge
        # warm light from the fire
        g = radial_glow(W, H, W * 0.5, H * 0.45, W * 0.75, None, 1.1)
        a = np.asarray(im, np.float32) * (0.25 + 0.8 * g[..., None]) * np.array([1.05, 0.95, 0.85], np.float32)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    def layout(self):
        if self.single: return [(1700, 1560, 1100, 1, 0)]
        out = []
        x = 220
        for i in range(self.n):
            L = 660 - i * 50
            out.append((x + L * 0.55, 1760 - i * 6, L, SHOE_COLORS[i % len(SHOE_COLORS)], i))
            x += L * 0.82 + 30
        return out
    def overlay(self, im, t, k, P, s):
        items = self.layout()
        for idx, (cx, cy, L, col, i) in enumerate(items):
            if isinstance(col, int): col = SHOE_COLORS[col]
            if self.appear:
                t0, t1 = self.appear
                ti = t0 + (t1 - t0) * idx / max(1, len(items) - 1)
                a = clamp((t - ti) / 0.35)
                if a <= 0: continue
            else: a = 1.0
            kind = 1 if i in (3, 5, 8) else 2 if i in (7,) else 0
            key = (round(s, 4), L, i)
            if key not in self._sprites:
                sh = shoe(L, col, s, kind)
                pair = Image.new("RGBA", (int(sh.width * 1.25), int(sh.height * 1.12)), (0, 0, 0, 0))
                back = Image.fromarray((np.asarray(sh, np.float32) * np.array([0.7, 0.7, 0.7, 1])).astype(np.uint8), "RGBA")
                pair.paste(back, (int(sh.width * 0.22), 0), back)
                pair.paste(sh, (0, int(sh.height * 0.1)), sh)
                if self.filled:
                    dd = ImageDraw.Draw(pair)
                    X = lambda v: v * L * s
                    gift = [(255, 140, 20), (190, 30, 40), (220, 200, 80), (40, 120, 60)][i % 4]
                    dd.ellipse([X(0.14), X(0.12), X(0.40), X(0.38)], fill=gift)
                    dd.ellipse([X(0.18), X(0.15), X(0.24), X(0.21)], fill=tuple(min(255, c + 60) for c in gift))
                    if i % 2 == 0:
                        dd.rectangle([X(0.30), X(0.05), X(0.52), X(0.33)], fill=(180, 30, 40), outline=(230, 200, 90), width=max(1, int(X(0.015))))
                self._sprites[key] = pair
            sp = self._sprites[key]
            x, y = P(cx - L * 0.55, cy - L * 0.80)
            sh_m = Image.new("L", (sp.width, int(sp.height * 0.25)), 0)
            ImageDraw.Draw(sh_m).ellipse([0, 0, sp.width, sh_m.height], fill=int(120 * a))
            sh_m = sh_m.filter(ImageFilter.GaussianBlur(12 * s))
            im.paste((0, 0, 0), (int(x + 10 * s), int(y + sp.height * 0.78)), sh_m)
            if a < 1:
                al = sp.getchannel("A").point(lambda v: int(v * a))
                im.paste(sp, (int(x), int(y + (1 - a) * -30 * s)), al)
            else:
                im.paste(sp, (int(x), int(y)), sp)

# =============================================================== GARLAND
BULBS = [(255, 70, 50), (60, 200, 90), (70, 120, 255), (255, 200, 60), (255, 140, 40)]
class Garland(Canvas):
    def base(self, u):
        W, H = round(3840 * u), round(2160 * u)
        small = Image.new("RGB", (W // 4, H // 4), (8, 14, 10))
        d = ImageDraw.Draw(small)
        rng = np.random.default_rng(111)
        for _ in range(240):  # fir branches (blurred, out of focus)
            x, y = rng.random() * W / 4, rng.random() * H / 4
            ang = rng.uniform(-0.5, 0.5) + (math.pi if rng.random() < 0.5 else 0)
            L = rng.uniform(260, 620) * u / 4
            c = (int(rng.uniform(16, 40)), int(rng.uniform(48, 80)), int(rng.uniform(28, 46)))
            x2, y2 = x + math.cos(ang) * L, y + math.sin(ang) * L * 0.4
            d.line([x, y, x2, y2], fill=c, width=max(1, int(14 * u / 4)))
            for j in range(14):
                f = j / 14
                px, py = lerp(x, x2, f), lerp(y, y2, f)
                for sgn in (-1, 1):
                    d.line([px, py, px + math.cos(ang + sgn * 0.9) * L * 0.22, py + math.sin(ang + sgn * 0.9) * L * 0.22], fill=c, width=max(1, int(9 * u / 4)))
        small = small.filter(ImageFilter.GaussianBlur(7 * u))
        return small.resize((W, H), Image.BICUBIC)
    def bulbs(self):
        out = []
        for row, (y0, sag) in enumerate([(520, 260), (1180, 300), (1800, 220)]):
            for i in range(11):
                f = (i + 0.5) / 11
                x = 120 + f * 3600
                y = y0 + sag * 4 * f * (1 - f) + (row * 37 % 50)
                out.append((x, y, BULBS[(i + row * 2) % len(BULBS)], (i + row) % 3))
        return out
    def overlay(self, im, t, k, P, s):
        d = ImageDraw.Draw(im)
        bl = self.bulbs()
        for row in range(3):
            pts = [P(x, y) for (x, y, c, g) in bl[row * 11:(row + 1) * 11]]
            d.line(pts, fill=(20, 30, 20), width=max(1, int(6 * s)), joint="curve")
        glow = Image.new("RGB", (im.width // 4, im.height // 4), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for (x, y, c, grp) in bl:
            on = 0.25 + 0.75 * (0.5 + 0.5 * math.tanh(4 * math.sin(t * 2.3 - grp * 2.09)))
            X, Y = P(x, y)
            r = 26 * s
            col = tuple(int(v * on) for v in c)
            d.rectangle([X - r * 0.5, Y - r * 1.6, X + r * 0.5, Y - r * 0.8], fill=(70, 60, 40))  # socket
            d.ellipse([X - r * 0.8, Y - r, X + r * 0.8, Y + r * 1.4], fill=tuple(min(255, int(v * 0.4 + 140 * on)) for v in c))
            R = 120 * s / 4 * on
            gd.ellipse([X / 4 - R, Y / 4 - R, X / 4 + R, Y / 4 + R], fill=col)
        glow = glow.filter(ImageFilter.GaussianBlur(28 * s / 4)).resize(im.size, Image.BILINEAR)
        im.paste(ImageChops.add(im, glow))

# =============================================================== OAK TABLE
class OakTable(Canvas):
    """Top-down oak table; toy car, papillotes, clementine pop in at shot-relative times."""
    def __init__(self, times, cam=None):
        super().__init__(cam); self.times = times; self._spr = {}
    def base(self, u):
        im = wood_texture(round(3840 * u), round(2160 * u), (140, 96, 56), seed=121, plank=round(430 * u))
        g = radial_glow(im.width, im.height, im.width * 0.5, im.height * 0.5, im.width * 0.7, None, 1.0)
        return Image.fromarray(np.clip(np.asarray(im, np.float32) * (0.45 + 0.7 * g[..., None]), 0, 255).astype(np.uint8))
    def sprite(self, which, s):
        key = (which, round(s, 4))
        if key in self._spr: return self._spr[key]
        if which == "car":
            w, h = round(900 * s), round(460 * s)
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            X = lambda v: v * s
            for wx in (190, 700):  # wheels (seen from above: dark tyres sticking out)
                for wy in (20, 380):
                    rrect(d, [X(wx - 80), X(wy), X(wx + 80), X(wy + 60)], X(20), fill=(20, 20, 20))
            rrect(d, [X(40), X(60), X(860), X(400)], X(120), fill=(170, 30, 30))
            rrect(d, [X(300), X(100), X(640), X(360)], X(60), fill=(120, 160, 190))
            rrect(d, [X(340), X(130), X(600), X(330)], X(40), fill=(150, 20, 22))
            d.line([X(80), X(230), X(820), X(230)], fill=(220, 200, 180), width=int(X(10)))
            for hx in (60, 820):
                d.ellipse([X(hx - 25), X(110), X(hx + 25), X(160)], fill=(250, 240, 200))
                d.ellipse([X(hx - 25), X(300), X(hx + 25), X(350)], fill=(250, 240, 200))
        elif which.startswith("pap"):
            col = {"pap0": (200, 40, 40), "pap1": (40, 140, 70), "pap2": (210, 170, 60)}[which]
            w, h = round(560 * s), round(220 * s)
            im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
            X = lambda v: v * s
            for sgn in (-1, 1):  # fringed twisted ends
                cx = 280 + sgn * 190
                for j in range(9):
                    yy = 30 + j * 20
                    d.line([X(280 + sgn * 120), X(110), X(cx + sgn * 60), X(yy)], fill=tuple(min(255, int(c * 1.3)) for c in col), width=int(X(8)))
            rrect(d, [X(150), X(50), X(410), X(170)], X(55), fill=col)
            d.ellipse([X(190), X(70), X(300), X(110)], fill=tuple(min(255, c + 100) for c in col))
        else:  # clementine
            w = h = round(420 * s)
            R = w / 2
            y, x = np.mgrid[0:h, 0:w].astype(np.float32)
            dd = np.sqrt((x - R) ** 2 + (y - R) ** 2) / (R * 0.92)
            light = 0.65 + 0.45 * np.clip(1 - np.sqrt((x - R * 0.7) ** 2 + (y - R * 0.7) ** 2) / R, 0, 1)
            dimp = noise(w, h, max(2, int(6 * s)), 9) * 0.12
            col = np.array([240, 120, 20], np.float32) * (light - dimp)[..., None]
            alpha = np.clip((1 - dd) * R * 0.5, 0, 1) * 255
            im = Image.fromarray(np.dstack([np.clip(col, 0, 255), alpha]).astype(np.uint8), "RGBA")
            d = ImageDraw.Draw(im)
            d.polygon([(R, R * 0.2), (R + 120 * s, R * 0.05), (R + 220 * s, R * 0.25), (R + 90 * s, R * 0.35)], fill=(50, 110, 40))
        self._spr[key] = im
        return im
    def overlay(self, im, t, k, P, s):
        items = [("car", self.times[0], (1250, 980), -12), ("pap0", self.times[1], (2250, 760), 18),
                 ("pap1", self.times[1] + 0.15, (2500, 1080), -25), ("pap2", self.times[1] + 0.3, (2150, 1340), 5),
                 ("clem", self.times[2], (2950, 1500), 0)]
        for which, t0, (cx, cy), rot in items:
            if t < t0: continue
            e = ease_out(clamp((t - t0) / 0.45))
            sp = self.sprite(which, s)
            sc = 0.75 + 0.25 * e + 0.06 * math.sin(clamp((t - t0) / 0.45) * math.pi)
            ck = (which, round(sc, 3), round(s, 4))
            if ck not in self._spr:
                self._spr[ck] = sp.resize((max(2, int(sp.width * sc)), max(2, int(sp.height * sc))), Image.BILINEAR).rotate(rot, expand=True, resample=Image.BILINEAR)
            spr = self._spr[ck]
            x, y = P(cx, cy)
            paste_shadowed(im, spr, x - spr.width / 2, y - spr.height / 2, (18 * s, 26 * s), 14 * s, 0.55, e)

# =============================================================== FROST over a photo
class FrostPhoto(Photo):
    """Photo with code-drawn frost crystals creeping in from the edges between t0 and t1."""
    def __init__(self, n, t0, t1, cam=None):
        super().__init__(n, cam); self.t0, self.t1 = t0, t1; self._f = None
    def frost(self, W, H):
        w, h = W // 2, H // 2
        im = Image.new("L", (w, h), 0); d = ImageDraw.Draw(im)
        rng = np.random.default_rng(131)
        def branch(x, y, ang, L, depth):
            if depth == 0 or L < 4: return
            x2, y2 = x + math.cos(ang) * L, y + math.sin(ang) * L
            d.line([x, y, x2, y2], fill=int(120 + 40 * depth), width=max(1, depth // 2))
            for sgn in (-1, 1):
                if rng.random() < 0.8: branch(lerp(x, x2, 0.5), lerp(y, y2, 0.5), ang + sgn * 1.05, L * 0.45, depth - 1)
            branch(x2, y2, ang + rng.normal(0, 0.25), L * 0.8, depth - 1)
        for _ in range(140):
            side = rng.integers(4)
            if side == 0: x, y, a = rng.random() * w, 0, math.pi / 2
            elif side == 1: x, y, a = rng.random() * w, h, -math.pi / 2
            elif side == 2: x, y, a = 0, rng.random() * h, 0
            else: x, y, a = w, rng.random() * h, math.pi
            branch(x, y, a + rng.normal(0, 0.5), rng.uniform(40, 110) * w / 1920, 6)
        im = ImageChops.lighter(im, im.filter(ImageFilter.GaussianBlur(3)))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        edge = np.minimum(np.minimum(xx, w - xx) / w, np.minimum(yy, h - yy) / h) * 2  # 0 at edge, 1 at centre
        nz = noise(w, h, max(8, w // 25), 132)
        return np.asarray(im.resize((W, H), Image.BILINEAR), np.float32) / 255, Image.fromarray(((edge + nz * 0.25) * 200).astype(np.uint8)).resize((W, H), Image.BILINEAR)
    def frame(self, t, k, dur):
        im = super().frame(t, k, dur)
        W, H = im.size
        if self._f is None or self._f[0] != (W, H):
            self._f = ((W, H),) + self.frost(W, H)
        cry, edge = self._f[1], np.asarray(self._f[2], np.float32) / 200
        g = ease(clamp((t - self.t0) / (self.t1 - self.t0))) * 0.55
        a = np.clip((g - edge) / 0.08, 0, 1) * cry * 0.85
        arr = np.asarray(im, np.float32)
        arr = arr * (1 - a[..., None]) + np.array([235, 244, 252], np.float32) * a[..., None]
        return Image.fromarray(arr.astype(np.uint8))
