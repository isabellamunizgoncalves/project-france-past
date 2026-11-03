# Noël 1962 — frame compositor and parallel encoder.
#   python3 render/render.py stills OUTDIR T1 T2 ...      [--size 1280x720]
#   python3 render/render.py video OUT.mp4 [--size WxH] [--from T0] [--to T1] [--jobs 4]
import os, sys, math, subprocess, time, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
import engine
from engine import CTX, FPS, clamp, finish, Snow, ease
import timeline

XFADE = 0.5   # crossfade length between shots (s)

_SHOTS = None
def shots():
    global _SHOTS
    if _SHOTS is None: _SHOTS = timeline.shots()
    return _SHOTS

SNOW = None
def hero_frame(sh, T):
    dur = sh.end - sh.start
    t = T - sh.start
    return sh.hero.frame(t, clamp(t / dur), dur)

def grade(a):
    """Gentle period grade: warm highlights, lifted blacks, a touch of desaturation."""
    l = a.mean(axis=2, keepdims=True)
    a = l + (a - l) * 0.88
    a = a * np.array([1.03, 1.0, 0.93], np.float32) + np.array([6, 4, 2], np.float32)
    return a

def render(T, idx):
    global SNOW
    S = shots()
    i = max(j for j, s in enumerate(S) if s.start <= T + 1e-9) if T >= S[0].start else 0
    sh = S[i]
    im = hero_frame(sh, T)
    snow = sh.snow
    # crossfade into the next shot around its start (unless it is a continuation of the same picture)
    nxt = S[i + 1] if i + 1 < len(S) else None
    prv = S[i - 1] if i > 0 else None
    w = None
    if nxt is not None and not nxt.cont and T > nxt.start - XFADE / 2:
        w = ease((T - (nxt.start - XFADE / 2)) / XFADE); other = hero_frame(nxt, T); a, b = im, other; snow = snow * (1 - w) + nxt.snow * w
    elif prv is not None and not sh.cont and T < sh.start + XFADE / 2:
        w = ease((T - (sh.start - XFADE / 2)) / XFADE); other = hero_frame(prv, T); a, b = other, im; snow = prv.snow * (1 - w) + snow * w
    if w is not None:
        im = Image.blend(a, b, w)
    if snow > 0.01:
        if SNOW is None: SNOW = Snow(n=int(260), seed=4)
        SNOW.draw(im, T, snow)
    # texts of current shot (+ previous shot's still fading)
    for s_ in ([prv] if prv else []) + [sh]:
        for tx in s_.texts: tx.draw(im, T, s_.end)
    f = min(clamp(T / 1.0), clamp((timeline.DURATION - T) / 1.8))  # fade from / to black
    return finish(im, idx, amount=4.0, fade=ease(f))

def encode_range(out, f0, f1, crf=17, preset="faster"):
    W, H = CTX.W, CTX.H
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-g", "60", "-threads", "2", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    for n in range(f0, f1):
        p.stdin.write(render(n / FPS, n).tobytes())
        if (n - f0) % 300 == 0:
            el = time.time() - t0
            print(f"[{os.path.basename(out)}] {n - f0}/{f1 - f0}  {el / max(1, n - f0):.2f}s/f", flush=True)
    p.stdin.close(); p.wait()
    return p.returncode

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("out"); ap.add_argument("times", nargs="*", type=float)
    ap.add_argument("--size", default="3840x2160"); ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--chunk", type=int, default=None, help="internal: render chunk index")
    ap.add_argument("--crf", type=int, default=17)
    a = ap.parse_args()
    W, H = map(int, a.size.split("x")); engine.set_size(W, H)
    if a.mode == "stills":
        os.makedirs(a.out, exist_ok=True)
        for T in a.times:
            t = time.time(); arr = render(T, int(T * FPS))
            arr.save(os.path.join(a.out, f"t{T:07.2f}.png")); print(T, f"{time.time() - t:.2f}s")
        return
    t1 = a.t1 if a.t1 is not None else timeline.DURATION
    F0, F1 = int(round(a.t0 * FPS)), int(math.floor(t1 * FPS))
    if a.chunk is not None:
        n = a.jobs; size = math.ceil((F1 - F0) / n)
        f0 = F0 + a.chunk * size; f1 = min(F1, f0 + size)
        sys.exit(encode_range(a.out, f0, f1, a.crf))
    # spawn workers on contiguous ranges, then concat
    base = os.path.splitext(a.out)[0]
    parts = [f"{base}.part{c}.mp4" for c in range(a.jobs)]
    procs = [subprocess.Popen([sys.executable, __file__, "video", parts[c], "--size", a.size, "--from", str(a.t0), "--to", str(t1),
                               "--jobs", str(a.jobs), "--chunk", str(c), "--crf", str(a.crf)]) for c in range(a.jobs)]
    rc = [p.wait() for p in procs]
    if any(rc): sys.exit(f"worker failed: {rc}")
    lst = base + ".parts.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    subprocess.check_call(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", a.out])
    for p in parts: os.remove(p)
    os.remove(lst)
    print("done", a.out)

if __name__ == "__main__":
    main()
