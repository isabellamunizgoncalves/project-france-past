# Noël 1962 — original solo-piano score synthesized in numpy, ducked under the narration.
#   python3 render/music.py out/mix.wav
# Slow 3/4 at 50 bpm, soft piano only. Themes A and B in D major, B minor during the cold wave
# (≈186–252 s), every third phrase only chords (breathing room), final rolled D chord at the end.
import json, os, sys, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
BPM = 50
BEAT = 60 / BPM
BAR = 3 * BEAT
DUR = 484.23

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)

# ------------------------------------------------------------ themes (midi, beats) per bar + chord per bar
A = [[(78, 2), (76, .5), (74, .5)], [(69, 3)], [(71, 1), (73, 1), (74, 1)], [(76, 3)],
     [(78, 2), (79, .5), (81, .5)], [(78, 2), (74, 1)], [(76, 1), (74, 1), (73, 1)], [(74, 3)]]
A_CH = ["D", "D", "G", "A", "D", "Bm", "A", "D"]
B = [[(71, 1), (73, 1), (74, 1)], [(76, 2), (78, 1)], [(79, 2), (78, 1)], [(76, 3)],
     [(74, 1), (76, 1), (78, 1)], [(71, 2), (73, 1)], [(74, 2), (76, 1)], [(73, 3)]]
B_CH = ["G", "A", "Em", "A", "Bm", "G", "G", "A"]
M = [[(78, 3)], [(74, 3)], [(76, 2), (73, 1)], [(71, 3)], [(79, 3)], [(78, 2), (76, 1)], [(74, 2), (73, 1)], [(71, 3)]]
M_CH = ["Bm", "G", "F#", "Bm", "Em", "Bm", "F#", "Bm"]
CHORDS = {"D": [50, 57, 62, 66], "G": [43, 55, 59, 62], "A": [45, 57, 61, 64], "Bm": [47, 54, 59, 62],
          "Em": [40, 55, 59, 64], "F#": [42, 54, 58, 61]}

# ------------------------------------------------------------ instruments
def musicbox(f, dur, vel=1.0):
    n = int(SR * min(dur + 2.5, 4.0)); t = np.arange(n) / SR
    out = np.zeros(n)
    for k, (mult, amp, dec) in enumerate([(1, 1.0, 2.2), (2.0, 0.22, 3.5), (3.01, 0.18, 5.0), (5.4, 0.07, 8.0), (8.9, 0.03, 12.0)]):
        out += amp * np.sin(2 * np.pi * f * mult * t + k) * np.exp(-t * dec)
    att = np.minimum(1, t / 0.002)
    return out * att * vel * 0.5

def piano(f, dur, vel=1.0):
    n = int(SR * (dur + 1.2)); t = np.arange(n) / SR
    out = np.zeros(n)
    for h in range(1, 7):
        if f * h > 5000: break
        inh = 1 + 0.0004 * h * h
        out += (1 / h ** 1.6) * np.sin(2 * np.pi * f * h * inh * t + h) * np.exp(-t * (0.9 + 0.5 * h))
    att = np.minimum(1, t / 0.008)
    rel = np.clip(1 - (t - dur) / 1.0, 0, 1)  # damper after note length
    return out * att * rel * vel * 0.35

def soft_piano(f, dur, vel=1.0):
    """Warm, felt-like piano: few harmonics, two slightly detuned strings, pedal-long release."""
    n = int(SR * (dur + 3.0)); t = np.arange(n) / SR
    out = np.zeros(n)
    bright = np.clip(1.4 - f / 900, 0.3, 1.0)
    for h in range(1, 6):
        if f * h > 3500: break
        a = (1 / h ** 2.4) * (bright if h > 1 else 1)
        dec = 0.55 + 0.35 * h + f / 2000
        for det in (-0.0004, 0.0004):
            out += 0.5 * a * np.sin(2 * np.pi * f * h * (1 + det) * (1 + 0.0003 * h * h) * t + h) * np.exp(-t * dec)
    att = np.minimum(1, t / 0.012)
    rel = np.clip(1 - (t - dur) / 2.5, 0, 1) ** 2
    return out * att * rel * vel * 0.4

def pad(f, dur, vel=1.0):
    n = int(SR * (dur + 1.5)); t = np.arange(n) / SR
    out = sum((1 / h ** 2) * np.sin(2 * np.pi * f * h * t + 0.3 * h + 0.002 * np.sin(2 * np.pi * 4.5 * t)) for h in (1, 2, 3))
    env = np.minimum(1, t / 1.2) * np.clip(1 - (t - dur) / 1.5, 0, 1)
    return out * env * vel * 0.18

def place(buf, sig, t0):
    i = int(t0 * SR)
    if i >= len(buf): return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[:j - i]

# ------------------------------------------------------------ arrangement
def phrase_kind(t):
    if 186 <= t < 252: return "minor"
    if t > 440: return "end"
    return None

def compose():
    L = int(SR * (DUR + 4)); mel = np.zeros(L); acc = np.zeros(L)
    t = 0.8
    i = 0
    rng = np.random.default_rng(62)
    while t + 8 * BAR <= DUR - 4.5:
        kind = phrase_kind(t)
        if kind == "minor": notes, chords = M, M_CH
        elif kind == "end" or i == 0: notes, chords = A, A_CH
        else: notes, chords = (A, A_CH) if i % 2 == 0 else (B, B_CH)
        sing = (i % 3 != 2) or kind == "end"     # every third phrase: chords only
        for b, (bar, ch) in enumerate(zip(notes, chords)):
            tb = t + b * BAR
            # melody one octave lower than written: soft middle register
            if sing:
                tt = tb + 0.03
                for m, beats in bar:
                    v = 0.55 + 0.08 * rng.random()
                    place(mel, soft_piano(hz(m - 12), beats * BEAT, v), tt + rng.normal(0, 0.008))
                    tt += beats * BEAT
            # left hand: low bass held for the bar, chord gently broken over beats 1-2-3
            cn = CHORDS[ch]
            bass = cn[0] - 12 if cn[0] >= 45 else cn[0]
            place(acc, soft_piano(hz(bass), BAR, 0.42), tb)
            for k, m in enumerate(cn[1:]):
                place(acc, soft_piano(hz(m), BAR - k * BEAT, 0.22 + 0.03 * rng.random()), tb + k * BEAT + 0.02)
        t += 8 * BAR
        i += 1
    # final D major chord, slowly rolled, right after the last phrase
    tf = t
    for k, m in enumerate([38, 50, 57, 62, 66, 69]):
        place(acc, soft_piano(hz(m), 4.0, 0.36), tf + 0.12 * k)
    return mel, acc

def reverb(x, seed, secs=3.2, wet=0.38):
    rng = np.random.default_rng(seed)
    n = int(SR * secs); t = np.arange(n) / SR
    ir = rng.normal(0, 1, n) * np.exp(-t * 6.9 / secs)
    ir[:int(0.012 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    N = 1 << int(np.ceil(np.log2(len(x) + n)))
    y = np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(ir, N), N)[:len(x)]
    return x * (1 - wet) + y * wet * 1.4

def voice_activity(L):
    """1 where the narrator speaks (words merged across gaps < 0.7 s), from audio/words.json."""
    W = json.load(open(os.path.join(ROOT, "audio/words.json")))["words"]
    act = np.zeros(L, np.float32)
    segs = []
    for w in W:
        s, e = w["s"], max(w["e"], w["s"] + 0.05)
        if segs and s - segs[-1][1] < 0.7: segs[-1][1] = max(segs[-1][1], e)
        else: segs.append([s, e])
    for s, e in segs: act[int((s - 0.15) * SR):int((e + 0.1) * SR)] = 1
    return act

def smooth_env(target, attack=0.25, release=0.8):
    """One-pole smoothing with different down/up speeds (vectorized in blocks of 10 ms)."""
    blk = SR // 100
    tb = target[::blk]
    out = np.empty_like(tb); g = tb[0]
    a_dn, a_up = 1 - np.exp(-0.01 / attack), 1 - np.exp(-0.01 / release)
    for i, v in enumerate(tb):
        g += (v - g) * (a_dn if v < g else a_up); out[i] = g
    return np.interp(np.arange(len(target)), np.arange(len(out)) * blk, out)

def main(out):
    mel, acc = compose()
    music_l = reverb(mel * 0.9 + acc * 1.0, 1)
    music_r = reverb(mel * 1.0 + acc * 0.9, 2)
    music = np.stack([music_l, music_r], 1)
    music /= np.abs(music).max() + 1e-9
    # narration
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", os.path.join(ROOT, "audio/noel_1962_narration.mp3"),
                          "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True, check=True).stdout
    voice = np.frombuffer(raw, np.float32).astype(np.float64)
    L = max(len(voice), int(DUR * SR)) + SR
    voice = np.pad(voice, (0, L - len(voice)))
    music = np.pad(music, ((0, max(0, L - len(music))), (0, 0)))[:L]
    # ducking: music sits ~30 dB under the voice while speaking, ~21 dB under in pauses
    act = voice_activity(L)
    vr = np.sqrt(np.mean(voice[act > 0] ** 2))
    mr = np.sqrt(np.mean(music ** 2))
    g_speak = vr / mr * 10 ** (-30 / 20)
    g_free = vr / mr * 10 ** (-21 / 20)
    g = smooth_env(np.where(act > 0, g_speak, g_free))
    t = np.arange(L) / SR
    g *= np.clip(t / 1.5, 0, 1) * np.clip((DUR + 0.3 - t) / 2.0, 0, 1)  # fade in / out
    mix = music * g[:, None] + voice[:, None]
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)
    mix = mix[:int(DUR * SR)]
    import wave
    tmp = out + ".raw.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())
    # louder, steadier voice: gentle compression, then loudness to -14 LUFS (YouTube) with -1.5 dBTP ceiling
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", tmp, "-af",
                    "acompressor=threshold=-20dB:ratio=3:attack=5:release=150:makeup=2,"
                    "loudnorm=I=-14:TP=-1.5:LRA=8", "-ar", str(SR), out], check=True)
    os.remove(tmp)
    print("wrote", out, f"music gain speak {20*np.log10(g_speak):.1f} dB, free {20*np.log10(g_free):.1f} dB")

if __name__ == "__main__":
    main(sys.argv[1])
