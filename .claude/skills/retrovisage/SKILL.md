---
name: retrovisage
description: Estilo de edição do canal Retrovisage — vídeo documental nostálgico (França dos anos 1950–60) feito 100% em código a partir de uma narração em francês, imagens de reconstituição e elementos desenhados em código. Use quando a usuária pedir um vídeo "no estilo Retrovisage", "estilo do canal" ou mencionar /retrovisage.
---

# Retrovisage — estilo de edição

Canal de história do cotidiano francês para quem viveu a época. Tom: memória afetiva, calma, factual
("sans rien inventer"). A referência completa é o vídeo **Noël 1962** deste repositório:
código em `render/`, beats em `BEATS.md`, decisões em `PROJECT_NOTES.md`.

**Fale com a usuária em português. Textos na tela em francês.**

## Fluxo de trabalho (sempre nesta ordem, com aprovação antes de construir)

1. **Ler** a narração (`audio/*.txt`, texto exato em FR) e o briefing / notas do projeto.
2. **Alinhamento palavra por palavra** (precisa de acesso a `huggingface.co`, `*.huggingface.co`, `*.hf.co`):
   ```
   pip install faster-whisper "av>=14,<16"; pip install --no-deps num2words
   python3 tools/align.py AUDIO.mp3 TEXTO.txt audio/words_raw.json
   python3 tools/align.py AUDIO.mp3 TEXTO.txt audio/words_raw.json --head 30   # Whisper pula o início por causa do prompt
   python3 tools/match.py audio/words_raw.json TEXTO.txt audio/words.json
   ```
   Conferir os trechos `fuzzy`; commit de `audio/words.json`.
3. **Tabela de beats** (`BEATS.md`): `# | Tempo | Narração (FR) | Herói | Texto na tela (FR) | Câmera`,
   com os tempos exatos das palavras-chave (datas, cidades, números, nomes). Listar à parte as decisões
   tomadas por conta própria. **Mostrar à usuária e esperar aprovação.**
4. **Construir**: novo `render/timeline.py` (ou um arquivo de timeline por vídeo) reutilizando
   `engine.py`, `props.py`, `music.py`, `render.py`. Verificar com imagens fixas
   (`render.py stills DIR T1 T2 … --size 1280x720`) e montar contact sheets.
5. **Prévia 720p** completa com áudio → enviar à usuária (SendUserFile).
6. **Render 4K** em segundo plano (`--size 3840x2160 --jobs 4 --crf 18`), depois mux do áudio.
7. **Entrega**: o 4K passa do limite de envio (500 MB) → gerar e enviar **1080p** (`crf 21`, ~250 MB);
   vídeos ficam fora do git (`*.mp4`, `out/`, `cache/` no `.gitignore`). Avisar que o ambiente é temporário.

## Regras de linguagem visual

- **Formato**: 3840x2160, 30 fps, duração = narração.
- **Um único herói por beat**: uma imagem OU um objeto desenhado em código. Cortes no tempo da palavra
  (início do beat ~0,15 s antes da frase), **fundido cruzado de 0,5 s**; planos "continuação" da mesma
  imagem sem fundido. Abertura com fade do preto (1 s), fim com fade para o preto (1,8 s).
- **Câmera**: sempre em movimento lento com easing senoidal — push-in 1.00→1.08/1.12, pull-back,
  panorâmica lateral a zoom 1.12–1.14; zoom forte só para revelar um detalhe (ex.: Mouthe 1→2.3).
- **Look de época**: leve dessaturação (0.88), realces quentes, pretos levantados, vinheta suave,
  grão de filme (amplitude ~4). Neve em partículas nos planos de inverno.
- **Aviso** no início, pequeno, rodapé central: « Certaines images sont des reconstitutions ».
- **Textos na tela**:
  - Legendas de dado/lugar/data: **Special Elite** (máquina de escrever), canto inferior esquerdo
    (ou direito), ~110–150 px a 4K, com sombra suave e "scrim" escuro atrás para legibilidade.
  - Títulos, cartela, CTA: **Playfair Display** (bold/itálico), centralizados.
  - Números grandes de impacto (ex.: « −29 °C »): Playfair 400+ px.
  - As fontes não têm "≈": escrever « environ ». Usar o sinal de menos tipográfico « − » e « °C ».
  - Só fatos ditos na narração — nada de números, datas ou textos inventados (cartas = linhas de tinta
    ilegíveis; valores desconhecidos = pontilhado).
- **Pessoas reais**: foto P&B como tirage com borda branca, levemente girada, sobre uma **ficha
  datilografada** (nome em maiúsculas, função) com efeito de digitação sincronizado com o nome dito.
  Sem foto → só a ficha. Avisar sobre resolução, época da foto e direitos de uso.

## Elementos desenhados em código (catálogo em `render/props.py`)

Mapa escolar da França (contorno GSHHS de `assets/france_map.json`, França ocre, mares com linhas
costeiras, cartucho "FRANCE", alfinetes com etiquetas, avanço de gelo), calendário de parede do mês,
éphéméride (folhinha que arranca), contracheque, moedas, TV preto e branco **sem personagem**, ficha
datilografada (+ foto), carta e envelope « Au Père Noël », fileira de sapatos junto à lareira,
pisca-pisca vintage, mesa de carvalho vista de cima com objetos que aparecem nas palavras, geada que
cresce nas bordas de uma foto, cartela-título noturna com neve. Madeira, papel e parede são texturas
procedurais.

## Música (`render/music.py`)

- **Só piano, bem lento e suave** (preferência da usuária): melodia original em 3/4 a ~50 bpm,
  timbre macio (poucos harmônicos, duas cordas levemente desafinadas, pedal longo), mão esquerda com
  baixo + acorde quebrado; uma frase em cada três só com acordes; tom menor nas partes tristes/frias;
  acorde final lento. Reverb de convolução ~3 s.
- **Volume**: música ~30 dB abaixo da voz durante a fala e ~21 dB nas pausas (ducking pelos tempos de
  `words.json`); voz com compressão suave e mix final normalizada a **−14 LUFS** (−1,5 dBTP).

## Lições técnicas

- `faster-whisper` 1.2.x precisa de `av<16`; `num2words` instalar com `--no-deps`.
- `initial_prompt` faz o Whisper pular a abertura → passar `--head 30` e conferir.
- Caches de sprites devem ter chave arredondada e tamanho limitado (escala da câmera muda a cada
  quadro → vazamento de memória e OOM no render 4K). Se um worker morrer, refazer só aquele
  `--chunk N` (mesmos `--jobs`/`--from`/`--to`) e concatenar as partes com `ffmpeg -f concat -c copy`.
- Ao matar renders, usar `pgrep -f "render/render.py vide[o]"` (o padrão com colchetes não casa com o
  próprio shell).
- Testar todos os planos em 4K (início/meio/fim de cada shot) antes do render longo.
