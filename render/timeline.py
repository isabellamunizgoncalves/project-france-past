# Noël 1962 — the approved beat table (BEATS.md) as code. Times in seconds (audio/words.json).
from engine import Cam, Photo, Text, Snow, ease, ease_out
from props import (SchoolMap, MonthCalendar, Ephemeride, TitleCard, Payslip, Coins, TV, TypedCard,
                   Letter, Shoes, Garland, OakTable, FrostPhoto)

DURATION = 484.23

def cap(at, txt, until=None, **kw):
    """Standard lower-left caption (typewriter face)."""
    kw.setdefault("size", 112)
    return Text(at, txt, until=until, pos=kw.pop("pos", "lowleft"), face=kw.pop("face", "type"), **kw)

def big(at, txt, until=None, size=360, **kw):
    return Text(at, txt, until=until, pos=kw.pop("pos", "center"), face="title", size=size, **kw)

class Shot:
    def __init__(self, start, hero, texts=(), snow=0.0, cont=False):
        self.start, self.hero, self.texts, self.snow, self.cont = start, hero, list(texts), snow, cont
        self.end = None

PUSH = lambda a=1.0, b=1.08, **kw: Cam(z=(a, b), **kw)
PULL = lambda a=1.08, b=1.0, **kw: Cam(z=(a, b), **kw)
PANR = lambda z=1.14, **kw: Cam(z=(z, z), x=(-1, 1), **kw)   # pan left -> right
PANL = lambda z=1.14, **kw: Cam(z=(z, z), x=(1, -1), **kw)

def shots():
    S = []
    add = lambda *a, **k: S.append(Shot(*a, **k))
    # 1–2  orange (one continuous shot: push in, then slow pull back)
    orange = Photo(1, Cam(z=(1.0, 1.10)))
    add(0.0, orange, [Text(0.3, "Certaines images sont des reconstitutions", until=4.6, pos="lowcenter", face="type", size=64, fade=0.5)])
    add(7.85, Photo(1, Cam(z=(1.10, 1.0))), [cap(8.12, "XIXe siècle", until=11.9), cap(12.08, "… jusqu'aux années 1950", until=19.0)], cont=True)
    # 3  calendar Décembre 1962
    add(19.65, MonthCalendar([(1962, 12, 0)], cam=PUSH(1.0, 1.10)),
        [cap(20.58, "6 ans", until=21.05, pos="lowright", size=150), cap(21.12, "8 ans", until=21.85, pos="lowright", size=150),
         cap(21.90, "10 ans", until=23.1, pos="lowright", size=150), cap(23.20, "Décembre 1962", pos="lowright", size=150)])
    # 4–6
    add(28.10, Photo(6, PUSH(1.02, 1.10)))
    add(29.60, Photo(7, PANR(1.12)))
    add(34.80, TV("on", cam=PUSH(1.0, 1.10)))
    # 7  frost on window — 25 décembre 1962
    add(39.00, FrostPhoto(91, 0.0, 9.0, cam=PUSH(1.0, 1.12)),
        [cap(39.56, "25 décembre 1962", until=45.8), cap(46.40, "Le Noël le plus froid du XXe siècle")])
    # 8  title
    add(49.20, TitleCard(cam=PUSH(1.0, 1.04)), snow=0.9)
    # 9  map — Algeria
    add(52.20, SchoolMap(cam=PUSH(1.0, 1.06)),
        [cap(53.00, "Décembre 1962", until=55.9), cap(56.12, ["Printemps 1962 :", "fin de la guerre d'Algérie"])])
    # 10 rapatriés
    add(58.95, Photo(13, PANR(1.12)), [cap(60.98, "environ 700 000", size=150)])
    # 11–12 work & money
    add(71.25, Payslip(cam=Cam(z=(1.0, 1.06), y=(-1, 0.7))), [cap(73.96, "46 h / semaine", size=150)])
    add(75.60, Coins(cam=PUSH(1.0, 1.08)), [cap(76.18, "Nouveaux francs", size=130)])
    # 13 TV luxury
    add(79.50, TV("on", cam=Cam(z=(1.12, 1.0), span=(0.55, 1.0))),  # dolly out from ~87.6
        [cap(82.32, "Moins d'1 foyer sur 4", until=85.6, size=130), cap(85.76, "1 seule chaîne", size=130, until=93.9)])
    # 14 families
    add(94.15, Photo(20, PANR(1.12)), [cap(97.04, "Baby-boom", until=98.0, size=130), cap(98.18, "4 · 6 · 9 enfants", size=130)])
    # 15–16 shop windows
    add(110.05, Photo(23, PUSH(1.0, 1.10)))
    add(125.10, Photo(24, PUSH(1.02, 1.12)), [cap(131.12, "1962 : achats record", size=130, until=141.2)])
    # 17–21 letters
    add(141.65, Photo(28, PUSH(1.0, 1.08)))
    add(147.05, TypedCard([("MARETTE, Jacques", 120), ("Ministre des Postes", 92)], t0=1.6, cps=15, cam=PUSH(1.0, 1.05),
                    photo=("assets/people/marette_b.jpg", None, 2.5)))
    add(153.95, TypedCard([("DOLTO, Françoise", 120), ("Psychanalyste", 92), ("Sœur de Jacques Marette", 92)], t0=3.4, cps=15, cam=PUSH(1.0, 1.05),
                    photo=("assets/people/dolto.jpg", (125, 60, 475, 527), -2.5)))
    add(163.50, Letter(t_out=0.4, cam=PUSH(1.0, 1.06)),
        [cap(165.18, "environ 5 000 enfants", until=170.4, size=130), cap(170.60, ["Libourne", "+ d'1 million de lettres / an"], size=120)])
    add(174.50, TV("night", cam=PUSH(1.0, 1.12)),
        [Text(186.24, [("« Bonne nuit les petits »", 120, "italic", (244, 236, 220)), ("1re diffusion : décembre 1962", 90, "type", (230, 222, 205))], pos="lowleft")])
    # 22 éphéméride 22 décembre
    add(192.05, Ephemeride(("VENDREDI", 21, "DÉCEMBRE 1962"), ("SAMEDI", 22, "DÉCEMBRE 1962"), t_flip=0.45, cam=PUSH(1.0, 1.06)))
    # 23–25 map: frost, temperatures, Mouthe
    add(198.45, SchoolMap(frost=(0.2, 4.2), cam=Cam(z=(1.0, 1.0))), [cap(207.86, "Les plus froids du XXe siècle", size=120)])
    pins = [("Paris", "Paris  −8 °C", 0.60), ("Strasbourg", "Strasbourg  −12 °C", 2.40), ("Bordeaux", "Bordeaux  −13 °C", 4.08),
            ("Clermont-Ferrand", "Clermont-Ferrand  −16 °C", 5.56)]
    add(208.98, SchoolMap(pins=pins, cam=Cam(z=(1.0, 1.0))), cont=False)
    import props
    mx, my = props.proj(*props.CITIES["Mouthe"])
    add(216.20, SchoolMap(pins=[(p[0], p[1], -1) for p in pins], mouthe=0.3,
                          cam=Cam(z=(1.0, 2.3), c=((0.5, 0.5), (mx / 3840, my / 2160)), curve=ease, span=(0, 0.55))),
        [cap(216.48, "Mouthe (Doubs)", until=219.9, size=120), big(220.08, "−29 °C", size=420, pos="lowright")], cont=True)
    # 26–29 Marseille, trains, Cassis, rapatriés
    add(221.10, Photo(45, PANR(1.12)), [cap(221.64, "Marseille", until=223.8, size=130), cap(223.96, "30 à 40 cm de neige", size=130)], snow=0.8)
    add(228.35, Photo(46, PUSH(1.0, 1.10)), snow=0.5)
    add(232.45, Photo(47, PANL(1.12)), [cap(232.72, "Cassis", size=130)], snow=0.6)
    add(237.50, Photo(48, PUSH(1.0, 1.08)), snow=0.35)
    # 30 long winter: months flip
    add(245.50, MonthCalendar([(1962, 12, 0), (1963, 1, 3.3), (1963, 2, 6.6), (1963, 3, 10.4)], cam=PUSH(1.0, 1.05)),
        [cap(252.68, "Paris : le plus froid depuis 1879", until=256.5, size=110, pos="lowleft"), cap(256.68, "… jusqu'en mars 1963", size=110)])
    # 31 one pair of shoes
    add(258.25, Shoes(single=True, cam=PUSH(1.0, 1.12)))
    # 32–36 Christmas Eve
    add(266.10, Photo(57, PUSH(1.0, 1.08)), [cap(266.92, "Lundi 24 décembre", size=130)])
    add(273.95, Photo(56, Cam(z=(1.0, 1.18), span=(0, 0.75))))
    add(283.35, Garland(cam=PUSH(1.0, 1.05)))
    add(289.20, Photo(58, PANR(1.12)))
    add(298.45, Photo(60, PANL(1.12)), snow=0.55)
    # 37 row of shoes, 39 filled
    add(307.20, Shoes(appear=(8.0, 14.6), cam=Cam(z=(1.06, 1.06), x=(-1, 1))))
    # 38 door
    add(322.75, Photo(65, PUSH(1.0, 1.12)), [cap(323.08, "Mardi 25 décembre", size=130)])
    add(337.10, Shoes(filled=True, cam=PUSH(1.0, 1.10)))
    # 40–46 gifts
    add(340.35, Photo(68, PUSH(1.0, 1.08)))
    add(346.70, Photo(6, PUSH(1.02, 1.10)))
    add(349.35, Photo(69, PANR(1.12)))
    add(353.10, Photo(7, PUSH(1.0, 1.08)))
    add(358.10, Photo(1, PULL(1.10, 1.0)))
    add(366.60, Photo(73, PUSH(1.0, 1.08)))
    add(372.05, Photo(74, PANR(1.12)))
    # 47–49 meal
    add(379.70, Photo(77, PANR(1.12)))
    add(384.05, Photo(76, PUSH(1.0, 1.08)))
    add(386.80, Photo(77, PULL(1.10, 1.0)))
    # 50–51 snow games
    add(390.70, Photo(78, PANR(1.12)), [cap(395.04, "Lyon", size=130)], snow=0.3)
    add(398.10, Photo(79, PANL(1.12)), [cap(400.90, "Lac d'Enghien", size=130)], snow=0.3)
    # 52–53 evening
    add(407.20, TV("turnon", t_on=1.0, cam=PUSH(1.0, 1.06)))
    add(413.15, Photo(20, PULL(1.10, 1.0)))
    # 54 étrennes
    add(418.30, Photo(84, PUSH(1.0, 1.08)), [cap(421.32, "1er janvier : les étrennes", size=120)])
    # 55 oak table
    add(429.95, OakTable(times=(437.36 - 429.95, 438.24 - 429.95, 439.20 - 429.95), cam=PUSH(1.0, 1.06)),
        [cap(444.60, "46 h / semaine", size=130)])
    # 56–58 memory, CTA
    add(448.80, Photo(65, PUSH(1.0, 1.06)))
    add(461.70, Photo(91, PUSH(1.0, 1.06)),
        [Text(462.58, [("Et vous, quel cadeau", 150, "title", (246, 238, 222)), ("a marqué votre enfance ?", 150, "title", (246, 238, 222))], pos="center", align="center", until=465.6),
         Text(466.52, [("Racontez-le en commentaire", 130, "title", (246, 238, 222))], pos="center", align="center", until=473.3)])
    # 59 teaser
    add(474.15, Photo(94, PUSH(1.0, 1.08)),
        [Text(478.60, [("Prochainement", 90, "type", (230, 222, 205)), ("L'hiver 1963", 200, "title", (246, 238, 222))], pos="lowleft", until=483.3, scrim=0.9)], snow=0.7)
    for a, b in zip(S, S[1:]): a.end = b.start
    S[-1].end = DURATION
    return S
