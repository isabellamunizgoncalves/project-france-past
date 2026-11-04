---
name: narracao-com-tags
description: "Use quando Isabella pedir para preparar um roteiro de narração para voz de IA com pausas e emoções humanas: no Dark Planner (padrão dela) com reticências e pontuação, sem nenhuma tag; no ElevenLabs com <break time=\"1.5s\" /> ou tags como [whispers], [excited], [sighs], [shouts]. Também quando ela disser 'coloca as pausas', 'põe as reticências', 'põe os códigos', 'versão com tags' ou 'humanizar para o Dark Planner'."
---

# Narração com tags: pausas e emoções para voz de IA

Objetivo: pegar um roteiro (já escrito ou já humanizado) e inserir os **códigos** que a voz de IA entende, para que ela pause onde um narrador humano pausaria, pergunte com tom de pergunta, sussurre um segredo, se anime numa surpresa e, quando for preciso, grite.

O texto narrado fica sempre no idioma original do roteiro (francês, alemão, português...). As **tags de emoção ficam sempre em inglês**, porque é assim que o ElevenLabs as reconhece, mesmo num texto em francês. As explicações para Isabella são em português do Brasil.

Esta skill complementa a `humanizacao-roteiro`: aquela cuida da escrita (ritmo, frases de uma respiração, números por extenso); esta cuida dos códigos. Se o roteiro ainda estiver cru (frases picadas, algarismos, listas), aplicar primeiro as regras de escrita da `humanizacao-roteiro` e só depois marcar.

## Passo 0: qual ferramenta? (muda tudo)

**Padrão de Isabella: Dark Planner.** É onde ela gera os áudios. Se ela não citar outra ferramenta, usar sempre o **modo Dark Planner** (seção logo abaixo) e não perguntar.

Testado na prática (roteiro das vinte lembranças dos anos sessenta): o Dark Planner **lê qualquer tag em voz alta**. `[softly]` virou "Softly", `[long pause]` virou "Longues pauses", `[pause]` virou "Pause, numéro un", `[sighs]` virou "Sieg" e `[chuckles]` virou "Chacle". As pausas também não aconteceram. Em compensação, ele **respeita muito bem as reticências (...)**, que viram pausas naturais de hesitação e emoção.

### Modo Dark Planner (padrão)

Nenhum código no texto: nem `[tags]`, nem `<break>`, nem SSML. A humanização vem só da escrita:

| Efeito desejado | Como escrever no Dark Planner |
|---|---|
| Pausa curta, hesitação, lembrança | reticências: "Et puis il y a cette odeur... l'odeur de l'encre violette" |
| Pausa longa, mudança de bloco | linha em branco entre parágrafos; frase curta isolada num parágrafo próprio |
| Silêncio forte (abertura, luto, revelação) | reticências no fim da frase + linha em branco: "Fermez les yeux une seconde..." |
| Pergunta ao ouvinte | `?` e, logo depois, reticências ou frase curta que responde: "Vous vous en souvenez, n'est-ce pas ? ... Il suffit d'y penser." |
| Suspense antes de uma revelação | frases que encurtam + reticências antes da palavra revelada |
| Sussurro, confidência | frase curta e simples, com reticências antes ("Et ce soir-là... personne n'a dormi.") |
| Entusiasmo | um `!` numa frase curta, no máximo um por bloco |
| Grito | exclamação curta (até seis palavras) + linha em branco depois; nunca maiúsculas |
| Ternura, luto | frases lentas, sem `!`, reticências antes da palavra mais pesada, linha em branco depois |

Regras das reticências no Dark Planner:

1. Usar sempre três pontos `...`, logo depois da palavra e com espaço depois.
2. Colocar nos lugares de emoção: abertura, antes da imagem principal, depois de uma pergunta, antes de uma revelação, no fim de um bloco que emociona, e na ponte para o próximo número.
3. **No máximo duas por parágrafo.** Em excesso, a narração fica arrastada e todas as pausas soam iguais.
4. Nunca no meio de uma expressão fixa ("le Père... Noël" está errado).
5. Nas partes informativas, preferir vírgulas: elas mantêm o fluxo.

Seguir também todas as regras de escrita da `humanizacao-roteiro` (frases de uma respiração, números por extenso, nada de markdown nem direções de cena). Validar com `--modo dp`.

### Modos ElevenLabs

Só quando Isabella disser que vai gerar no ElevenLabs. Os códigos dependem do modelo, e **um código errado é lido em voz alta ou ignorado**. Perguntar uma vez: "v3 ou Multilingual v2 (ou Turbo/Flash)?". Se ela não souber, usar o modo **v2**.

| | Modo v2 (Multilingual v2, Turbo v2.5, Flash v2.5) | Modo v3 (Eleven v3) |
|---|---|---|
| Pausas | `<break time="1.2s" />` (máximo 3s) | **não aceita `<break>`**. Pausa com reticências, linha em branco ou `[pause]` |
| Emoções | **não aceita** `[tags]` (lê em voz alta). Emoção só pela escrita e pontuação | `[whispers]`, `[excited]`, `[sighs]`, `[shouts]` etc. |
| Ajuste | Stability por volta de 45 a 55%, Style 15 a 30% | Stability em **Creative** ou **Natural** (em Robust as tags quase não funcionam) |

Outras ferramentas: Google, Azure e Amazon Polly aceitam SSML (`<break time="800ms"/>`, `<prosody rate="slow">`, `<emphasis>`), mas só se o texto inteiro estiver dentro de `<speak>...</speak>`. CapCut e a maioria dos geradores simples **não aceitam nenhum código**: nesse caso não usar esta skill, usar a `humanizacao-roteiro`.

## Passo 1: mapa emocional

Ler o roteiro inteiro antes de marcar e decidir, bloco por bloco, a emoção dominante: contemplação, curiosidade, surpresa, ternura, tensão, gravidade, humor, chamada à ação. As tags só servem para **acentuar** essa curva. Se tudo tiver tag, nada se destaca.

## Passo 2: pausas (`<break>`) — modo v2

Sintaxe exata, sempre igual, com espaço antes da barra:

```
<break time="1.0s" />
```

Tabela de durações (ponto de partida; o ouvido manda):

| Situação | Duração |
|---|---|
| Respiração dentro de uma frase longa, antes de um detalhe | 0.4s a 0.6s |
| Depois de uma pergunta ao ouvinte, antes da resposta (deixar ele pensar) | 0.8s a 1.2s |
| Antes de uma revelação ou de um número marcante | 0.8s a 1.0s |
| Depois de uma frase forte, para o peso assentar | 1.2s a 1.5s |
| Mudança de bloco, transição para o próximo capítulo | 1.5s a 2.0s |
| Abertura: depois do convite a fechar os olhos / voltar no tempo | 1.5s a 2.5s |
| Luto, perda, minuto de silêncio | 2.0s a 3.0s |

Regras:

1. **Máximo 3s** por break. Para mais silêncio, deixar para a edição do vídeo.
2. **Pouco é mais.** Média de **um break a cada 40 a 60 palavras**. Excesso de breaks faz o ElevenLabs acelerar, mudar de timbre ou criar ruído. Onde a vírgula ou o ponto final já resolvem, não pôr break.
3. Nunca dois breaks seguidos, nem break colado em reticências (a pausa duplica).
4. O break vai **entre frases ou depois de vírgula**, nunca no meio de uma expressão ("le Père <break /> Noël" está errado).
5. Não abrir nem fechar o texto com break.
6. Variar as durações. Três `1.0s` seguidos soam como um metrônomo.

## Passo 3: emoções com tags — modo v3

A tag fica **logo antes** do trecho que ela colore e vale até a frase acabar (às vezes um pouco além). Em inglês, minúsculas, entre colchetes.

| Emoção / efeito | Tags | Quando usar |
|---|---|---|
| Sussurro, confidência, segredo | `[whispers]`, `[softly]` | "Et ce soir-là... personne n'a dormi." |
| Curiosidade, pergunta intrigante | `[curious]` | antes de perguntas ao ouvinte que pedem para lembrar |
| Surpresa, entusiasmo, alegria | `[excited]`, `[happy]` | revelação boa, um pico do vídeo |
| Grito, exclamação forte | `[shouts]` | uma frase curta, raríssimo (ver Passo 5) |
| Suspiro, cansaço, nostalgia | `[sighs]`, `[exhales]` | antes de uma lembrança doce-amarga |
| Riso | `[chuckles]`, `[laughs]` | depois de uma confissão engraçada |
| Tristeza, comoção | `[sad]`, `[emotional]` | avós, perdas, despedidas |
| Tensão, suspense | `[nervous]`, `[serious]` | frases que preparam um perigo |
| Ironia, cumplicidade | `[sarcastic]`, `[mischievously]` | "On ne va pas se mentir..." |
| Pausa | `[pause]`, `[short pause]`, `[long pause]` | substitui `<break>` no v3 |

Regras:

1. **No máximo uma tag de emoção a cada 3 ou 4 frases**, e no máximo duas na mesma frase (ex.: `[sighs] [softly]`).
2. A tag precisa **combinar com o texto**. `[excited]` antes de uma frase triste soa falso; a voz obedece mais às palavras do que à tag.
3. Tags que mudam a voz por completo (`[shouts]`, `[crying]`, `[laughs]`) só uma ou duas vezes no vídeo inteiro.
4. Tags que podem ser lidas em voz alta ou falhar dependem da voz escolhida: vozes "calmas" de narração sussurram bem mas gritam mal. Se uma tag sair esquisita no teste, trocar pela escrita (reticências, exclamação).
5. Nunca inventar tags fora desta lista sem avisar Isabella que é experimental.

No v3, ênfase numa palavra pode vir de MAIÚSCULAS (uma palavra, raramente). No v2, **nunca** usar maiúsculas: algumas vozes soletram.

## Passo 4: perguntas e questionamentos

Uma pergunta ao ouvinte só soa humana se a voz **subir o tom e esperar**:

- Terminar sempre com `?` (no francês, com espaço antes: `n'est-ce pas ?`).
- Depois da pergunta, pausa de pensamento e uma frase que responde ou aprofunda. Nunca deixar a pergunta no fim do parágrafo sozinha, porque a voz pula adiante.
- v2: `Vous vous en souvenez ? <break time="1.0s" /> Bien sûr que oui.`
- v3: `[curious] Vous vous en souvenez ? [short pause] Bien sûr que oui.`
- Pergunta retórica dramática (suspense): reticências antes. `Et vous savez ce qui s'est passé ensuite ?`
- Nunca duas perguntas seguidas sem resposta entre elas.

## Passo 5: gritos e intensidade

A voz de IA grita mal e um grito mal feito estraga o vídeo. Então:

- Só gritar quando o roteiro **cita** alguém gritando ou numa exclamação de alegria/alarme bem curta (até 6 palavras).
- Preparar o grito: pausa curta antes, e linha em branco ou pausa longa depois, para a voz "voltar ao normal".
- v3: `[shouts] Il neige !` seguido de linha em branco.
- v2: não existe tag de grito. Usar frase curta + `!` + `<break time="1.0s" />` depois. A intensidade vem da escrita.
- Máximo de **um ponto de exclamação por bloco**. Nunca `!!` nem `?!`.

## Passo 6: o que nunca entra no texto

- Direções de cena em português ou entre parênteses: "(pausa)", "(triste)", "*sussurrando*".
- Markdown: `#`, `**`, listas, travessões longos (—) no lugar de pausa.
- Algarismos: tudo por extenso, como se fala (ver `humanizacao-roteiro`).
- Tags do modo errado: `[tags]` no v2, `<break>` no v3.
- Tags mal fechadas: `<break time=1s>`, `<break time="1s"/>` sem o espaço é aceito, mas manter o padrão `<break time="1.0s" />`.

## Exemplo (francês, modo v2)

Antes:

```
Mais ce 25 décembre 1962, un froid brutal a transformé la fête en épreuve : le Noël le plus glacial de tout le XXe siècle en France.

Voici ce qui s'est réellement passé. Sans rien inventer.
```

Depois:

```
Mais ce vingt-cinq décembre mille neuf cent soixante-deux, <break time="0.5s" /> un froid brutal a transformé la fête en épreuve... le Noël le plus glacial de tout le vingtième siècle en France.

<break time="1.5s" />

Voici ce qui s'est réellement passé, sans rien inventer.
```

## Exemplo (francês, modo v3)

```
[sighs] Mais ce vingt-cinq décembre mille neuf cent soixante-deux, un froid brutal a transformé la fête en épreuve... [serious] le Noël le plus glacial de tout le vingtième siècle en France.

[long pause]

[softly] Voici ce qui s'est réellement passé. Sans rien inventer.
```

## Passo 7: conferir com o script

Salvar o texto marcado num .txt e rodar o validador, que aponta break acima de 3s, breaks em excesso ou colados, tags do modo errado, tags desconhecidas, algarismos, perguntas no fim de parágrafo e exclamações duplas:

```bash
python3 .claude/skills/narracao-com-tags/scripts/validar_tags.py roteiro.txt --modo dp   # Dark Planner
python3 .claude/skills/narracao-com-tags/scripts/validar_tags.py roteiro_tags.txt --modo v2
```

No modo `dp`, qualquer tag ou `<break>` é ERRO, e mais de duas reticências num parágrafo vira AVISO.

Com `--limpo saida.txt` ele também gera a versão sem nenhum código (para legenda ou para ferramentas que não aceitam tags). Corrigir tudo o que aparecer como ERRO; os AVISOS são para pensar caso a caso.

## Checagem antes de entregar

- O modo está certo (Dark Planner por padrão)? No Dark Planner, nenhum código sobrou no texto?
- As pausas estão nos lugares de emoção (abertura, depois de perguntas, antes de revelações, entre blocos) e não espalhadas por todo lado?
- Cada pergunta tem pausa + resposta depois?
- No máximo um grito no vídeo, um `!` por bloco, uma tag de emoção a cada 3 ou 4 frases?
- Nenhum fato, item ou frase do roteiro foi perdido ou inventado? (As tags não acrescentam informação.)
- O validador passou sem ERRO?

## Entrega

- O texto pronto para colar no Dark Planner (ou no ElevenLabs, se for o caso): só o que deve ser falado, parágrafos separados por linha em branco.
- Se o roteiro veio como .txt, devolver em .txt (ex.: `roteiro_tags_v2.txt`). Se for longo, nunca colar só um pedaço na resposta: entregar o arquivo completo.
- O ElevenLabs tem limite de caracteres por geração (os códigos contam). Se o texto for longo, sugerir dividir nas linhas em branco entre blocos, nunca no meio de um bloco.
- Depois do texto, no máximo 3 linhas em português: modo usado, ajuste de voz sugerido (ver tabela do Passo 0) e o lembrete de ouvir os primeiros trinta segundos antes de gerar o resto.
