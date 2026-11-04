# Word-level alignment of the narration with faster-whisper.
# usage: align.py audio.mp3 script.txt out.json [--head SECONDS]
#   --head N : re-transcribe only the first N seconds WITHOUT initial_prompt
#              (the prompt makes Whisper skip the opening) and splice the
#              result into an existing out.json.
import json, sys
from faster_whisper import WhisperModel, decode_audio
audio, script, out = sys.argv[1], sys.argv[2], sys.argv[3]
head = float(sys.argv[sys.argv.index("--head") + 1]) if "--head" in sys.argv else None
m = WhisperModel("medium", device="cpu", compute_type="int8")
def run(src, prompt):
    segs, info = m.transcribe(src, language="fr", word_timestamps=True, beam_size=5,
                              initial_prompt=prompt, vad_filter=False)
    ws = []
    for s in segs:
        for w in s.words:
            ws.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
        print(f"{s.start:7.2f} {s.text}", flush=True)
    return ws, info.duration
if head is None:
    prompt = open(script, encoding='utf-8').read()[:800]
    words, dur = run(audio, prompt)
    json.dump({"duration": dur, "words": words}, open(out, "w"), ensure_ascii=False, indent=0)
else:
    pcm = decode_audio(audio, sampling_rate=16000)[: int(head * 16000)]
    hw, _ = run(pcm, None)
    raw = json.load(open(out))
    # cut point: first full-pass word starting in the last 2 s of the head window;
    # head-pass words before it replace everything the full pass had there.
    cut = next(w["s"] for w in raw["words"] if w["s"] >= head - 2)
    hw = [w for w in hw if w["e"] <= cut]
    raw["words"] = hw + [w for w in raw["words"] if w["s"] >= cut]
    json.dump(raw, open(out, "w"), ensure_ascii=False, indent=0)
    print("spliced", len(hw), "words before", cut)
