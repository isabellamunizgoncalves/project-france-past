#!/usr/bin/env python3
"""Confere um roteiro marcado com tags de narração (ElevenLabs) antes de gerar o áudio.

Uso:
    python3 validar_tags.py roteiro.txt --modo v2|v3 [--limpo saida.txt]

Mostra ERROS (corrigir sempre) e AVISOS (avaliar caso a caso) e um resumo.
--limpo grava a versão sem nenhum código (para legenda ou ferramentas sem tags).
"""
import argparse
import re
import sys

BREAK_RE = re.compile(r'<break\s+time="(\d+(?:\.\d+)?)(s|ms)"\s*/>')
ANY_ANGLE_RE = re.compile(r"<[^>]*>")
SQUARE_RE = re.compile(r"\[([^\]]+)\]")

TAGS_V3 = {
    "whispers", "whispering", "softly", "curious", "excited", "happy", "shouts",
    "shouting", "sighs", "exhales", "chuckles", "laughs", "laughs harder",
    "starts laughing", "sad", "emotional", "crying", "nervous", "serious",
    "sarcastic", "mischievously", "pause", "short pause", "long pause",
}
FORTES = {"shouts", "shouting", "crying", "laughs", "laughs harder", "starts laughing"}
PAUSAS_V3 = {"pause", "short pause", "long pause"}


def segundos(valor, unidade):
    v = float(valor)
    return v / 1000 if unidade == "ms" else v


def limpar(texto):
    t = ANY_ANGLE_RE.sub("", texto)
    t = SQUARE_RE.sub("", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r" +([,.])", r"\1", t)
    linhas = [l.strip() for l in t.split("\n")]
    t = "\n".join(linhas)
    return re.sub(r"\n{3,}", "\n\n", t).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo")
    ap.add_argument("--modo", choices=["v2", "v3"], required=True)
    ap.add_argument("--limpo", help="grava a versão sem códigos neste arquivo")
    a = ap.parse_args()

    texto = open(a.arquivo, encoding="utf-8").read()
    erros, avisos = [], []

    def onde(pos):
        return f"linha {texto.count(chr(10), 0, pos) + 1}"

    # Tags de ângulo
    breaks = list(BREAK_RE.finditer(texto))
    for m in ANY_ANGLE_RE.finditer(texto):
        if not BREAK_RE.fullmatch(m.group(0)):
            erros.append(f"{onde(m.start())}: código mal escrito ou não suportado: {m.group(0)}"
                         ' (use <break time="1.0s" />)')
    if a.modo == "v3" and breaks:
        erros.append(f"{len(breaks)} <break> no modo v3: o Eleven v3 não aceita break. "
                     "Troque por [pause], [short pause], [long pause] ou reticências.")
    for m in breaks:
        s = segundos(*m.groups())
        if s > 3:
            erros.append(f"{onde(m.start())}: break de {s:g}s (máximo 3s)")
        elif s < 0.2:
            avisos.append(f"{onde(m.start())}: break de {s:g}s é curto demais para notar")
        depois = texto[m.end():m.end() + 40]
        if BREAK_RE.match(depois.lstrip()):
            erros.append(f"{onde(m.start())}: dois breaks seguidos")
        antes = texto[max(0, m.start() - 4):m.start()].rstrip()
        if antes.endswith("...") or antes.endswith("…") or depois.lstrip().startswith(("...", "…")):
            avisos.append(f"{onde(m.start())}: break colado em reticências (pausa dupla)")
        ant = texto[max(0, m.start() - 2):m.start()].strip()
        prox = depois.lstrip()[:1]
        if ant and ant[-1].isalpha() and prox and prox.islower():
            avisos.append(f"{onde(m.start())}: break no meio de expressão, sem pontuação antes")
    if texto.strip().startswith("<break") or texto.strip().endswith("/>"):
        avisos.append("o texto começa ou termina com break")
    tempos = [segundos(*m.groups()) for m in breaks]
    for i in range(len(tempos) - 2):
        if tempos[i] == tempos[i + 1] == tempos[i + 2]:
            avisos.append(f"três breaks seguidos de {tempos[i]:g}s: varie as durações")
            break

    # Tags de colchete
    tags = list(SQUARE_RE.finditer(texto))
    if a.modo == "v2" and tags:
        erros.append(f"{len(tags)} [tags] no modo v2: o Multilingual v2 lê em voz alta. "
                     "Exemplo: " + tags[0].group(0))
    if a.modo == "v3":
        for m in tags:
            nome = m.group(1).strip()
            if nome.lower() not in TAGS_V3:
                avisos.append(f"{onde(m.start())}: tag [{nome}] fora da lista (experimental)")
            elif nome != nome.lower():
                avisos.append(f"{onde(m.start())}: escreva a tag em minúsculas: [{nome.lower()}]")
            if re.search(r"[a-zà-ÿ]", nome) is None:
                erros.append(f"{onde(m.start())}: tag vazia ou inválida {m.group(0)}")
        fortes = [m for m in tags if m.group(1).strip().lower() in FORTES]
        if len(fortes) > 2:
            avisos.append(f"{len(fortes)} tags fortes ({', '.join(m.group(0) for m in fortes)}): "
                          "o ideal é no máximo duas no vídeo")

    # Texto falado
    falado = limpar(texto)
    palavras = len(falado.split())
    for m in re.finditer(r"\d", ANY_ANGLE_RE.sub("", SQUARE_RE.sub("", texto))):
        erros.append("há algarismos no texto falado: escreva os números por extenso")
        break
    if re.search(r"[!?]{2,}|\?!|!\?", falado):
        erros.append("pontuação dupla (!!, ?!, ??): use um sinal só")
    if re.search(r"\(\s*(pausa|pause|triste|sussurr|grit)", texto, re.I) or re.search(r"\*[^*]+\*", texto):
        erros.append("direção de cena no texto (parênteses ou *asteriscos*): a voz vai ler")
    if re.search(r"^\s*#|\*\*", texto, re.M):
        erros.append("marcação markdown (# ou **) no texto")
    for par in [p.strip() for p in falado.split("\n\n") if p.strip()]:
        if par.endswith("?"):
            avisos.append(f"parágrafo termina em pergunta sem resposta: «…{par[-60:]}»")
        if par.count("!") > 1:
            avisos.append(f"mais de um ! no mesmo parágrafo: «{par[:60]}…»")

    pausas = len(breaks) + sum(1 for m in tags if m.group(1).strip().lower() in PAUSAS_V3)
    if palavras and pausas:
        dens = palavras / pausas
        if dens < 30:
            avisos.append(f"uma pausa a cada {dens:.0f} palavras: pausas demais "
                          "(ideal entre 40 e 60); a voz pode acelerar ou distorcer")
    emocoes = [m for m in tags if m.group(1).strip().lower() not in PAUSAS_V3]
    frases = max(1, len(re.findall(r"[.!?…]+", falado)))
    if a.modo == "v3" and emocoes and frases / len(emocoes) < 3:
        avisos.append(f"{len(emocoes)} tags de emoção para {frases} frases: "
                      "o ideal é uma a cada 3 ou 4 frases")

    print(f"Modo {a.modo} | {palavras} palavras | {len(breaks)} breaks | "
          f"{len(tags)} [tags] | {len(falado)} caracteres falados, {len(texto)} com códigos")
    for e in erros:
        print("ERRO  ", e)
    for w in avisos:
        print("AVISO ", w)
    if not erros and not avisos:
        print("Tudo certo.")

    if a.limpo:
        open(a.limpo, "w", encoding="utf-8").write(falado)
        print(f"Versão sem códigos gravada em {a.limpo}")
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
