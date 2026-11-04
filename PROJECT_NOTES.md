# Noël 1962 — notes de projet (état actuel)

## Fichiers
- `audio/noel_1962_narration.mp3` (484,23 s) et `audio/noel_1962_narration.txt` (texte FR exact)
- `fonts/` : Playfair Display (titres), Special Elite (machine à écrire)
- `tools/align.py` (faster-whisper, timestamps par mot) puis `tools/match.py` (cale le texte exact sur les mots Whisper)
  - `python3 tools/align.py audio/noel_1962_narration.mp3 audio/noel_1962_narration.txt audio/words_raw.json`
  - `python3 tools/match.py audio/words_raw.json audio/noel_1962_narration.txt audio/words.json`
  - nécessite l'accès réseau à huggingface.co (+ *.huggingface.co, *.hf.co)

## Décisions validées par l'utilisatrice
- Format : 3840x2160, 30 fps, durée = narration.
- Images : celles du dépôt (générées par IA) — sélection approuvée :
  1 (orange), 13 (rapatriés), 20 (famille nombreuse), 23/24 (vitrines), 28 (lettre), 45 (Vieux-Port neige),
  46 (trains), 47 (Cassis), 48 (rapatriés + neige), 57/56 (sapin, boule fêlée), 58 (crèche), 60 (messe),
  65 (porte), 6/68/69 (jouets), 7 (papillotes), 73/74 (écharpe, laine), 76/77 (bûche, repas),
  78 (Lyon), 79 (Enghien), 84 (étrennes), 91 (givre), 94 (école sous la neige, teaser).
- Avertissement à l'écran au début : « Certaines images sont des reconstitutions ».
- Musique de fond : composée en code (boîte à musique / piano, mélodie originale), ducking sous la voix.
- Jacques Marette / Françoise Dolto : photos fournies par l'utilisatrice (assets/people/), posées en tirage N&B sur la fiche tapée à la machine.
  (Photos refusées : aperçu Bridgeman filigrané ; portraits < 320 px ; Dolto âgée, source inconnue.)
- Tout le reste dessiné en code : table en chêne, carte scolaire de France, calendrier, fiche de paie,
  pièces, lettre, TV N&B (sans personnage), épingles de température, rangée de souliers, givre, neige.

## Construction (fait)
- `audio/words.json` : timings mot à mot ; `BEATS.md` : tableau des beats **validé**.
- `render/` : `engine.py` (caméra, textes, fondus, grain), `props.py` (tout ce qui est dessiné en code),
  `timeline.py` (les 59 beats), `music.py` (musique originale + ducking), `render.py` (rendu parallèle).
- Carte : contours GSHHS/frontières (paquet pip basemap-data) -> `assets/france_map.json` via `tools/mapdata.py`.
- Commandes :
  - `python3 render/music.py out/mix.wav`
  - `python3 render/render.py video out/noel_1962_4k_video.mp4 --size 3840x2160 --jobs 4 --crf 18`
  - `ffmpeg -i out/noel_1962_4k_video.mp4 -i out/mix.wav -c:v copy -c:a aac -b:a 256k -shortest out/noel_1962_4k.mp4`
  - prévisualisation : `--size 1280x720` ; images fixes : `python3 render/render.py stills DIR T1 T2 ... --size 1280x720`
- `out/` et `cache/` ne sont pas versionnés (vidéo trop lourde pour git).
