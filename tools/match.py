# Map every word of the written script onto Whisper word timings (difflib alignment).
import json, re, sys, difflib, unicodedata
raw = json.load(open(sys.argv[1]))
script = open(sys.argv[2], encoding='utf-8').read()
from num2words import num2words
def norm(t):
    # spell digits in French so "6" (Whisper) matches "six" (script)
    t = re.sub(r"\d+", lambda m: num2words(int(m.group()), lang='fr'), t)
    t = unicodedata.normalize('NFD', t.lower())
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r"[^a-z0-9]", "", t)
paras = [p for p in script.split('\n') if p.strip()]
stoks = []
for pi, p in enumerate(paras):
    for t in p.split():
        stoks.append({"w": t, "p": pi})
# Whisper splits elisions/hyphens ("n" + "'était", "celui" + "-là"): glue them back
wt = []
for w in raw["words"]:
    if wt and w["w"][:1] in "'’-" :
        wt[-1] = {"w": wt[-1]["w"] + w["w"], "s": wt[-1]["s"], "e": w["e"]}
    else:
        wt.append(dict(w))
A = [norm(t["w"]) for t in stoks]; B = [norm(w["w"]) for w in wt]
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == 'equal':
        for k in range(i2 - i1):
            stoks[i1+k]["s"], stoks[i1+k]["e"] = wt[j1+k]["s"], wt[j1+k]["e"]
    elif j2 > j1:  # spread replaced span over whisper span
        s, e = wt[j1]["s"], wt[j2-1]["e"]; n = i2 - i1
        for k in range(n):
            stoks[i1+k]["s"] = round(s + (e-s)*k/n, 3); stoks[i1+k]["e"] = round(s + (e-s)*(k+1)/n, 3); stoks[i1+k]["fuzzy"] = 1
# fill gaps (script words with no audio match) by interpolation
for i, t in enumerate(stoks):
    if "s" not in t:
        prev = next((stoks[j]["e"] for j in range(i-1, -1, -1) if "e" in stoks[j]), 0)
        t["s"] = t["e"] = prev; t["fuzzy"] = 1
json.dump({"duration": raw["duration"], "words": stoks}, open(sys.argv[3], "w"), ensure_ascii=False)
print("words", len(stoks), "fuzzy", sum(1 for t in stoks if t.get("fuzzy")), "ratio", round(sm.ratio(), 3))
