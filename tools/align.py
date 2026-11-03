# Word-level alignment of the narration with faster-whisper.
import json, sys
from faster_whisper import WhisperModel
audio, script, out = sys.argv[1], sys.argv[2], sys.argv[3]
prompt = open(script, encoding='utf-8').read()[:800]
m = WhisperModel("medium", device="cpu", compute_type="int8")
segs, info = m.transcribe(audio, language="fr", word_timestamps=True, beam_size=5,
                          initial_prompt=prompt, vad_filter=False)
words = []
for s in segs:
    for w in s.words:
        words.append({"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)})
    print(f"{s.start:7.2f} {s.text}", flush=True)
json.dump({"duration": info.duration, "words": words}, open(out, "w"), ensure_ascii=False, indent=0)
