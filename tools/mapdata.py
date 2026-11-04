# Extract coastlines (GSHHS intermediate) and country borders around France from the
# basemap-data wheel (pip download --no-deps basemap-data) into assets/france_map.json.
# usage: mapdata.py <dir containing gshhs_i.dat, gshhsmeta_i.dat, countries_i.dat, countriesmeta_i.dat>
import json, sys, numpy as np
d = sys.argv[1]
BOX = (-14, 22, 36, 58)  # lon0, lon1, lat0, lat1 kept (wider than the view)
def read(name, want_type=None):
    out = []
    raw = open(f"{d}/{name}_i.dat", "rb").read()
    for line in open(f"{d}/{name}meta_i.dat"):
        f = line.split()
        typ, npts, s, n, off, cnt = int(f[0]), int(f[2]), float(f[3]), float(f[4]), int(f[5]), int(f[6])
        if n < BOX[2] or s > BOX[3] or (want_type and typ != want_type):
            continue
        p = np.frombuffer(raw[off:off+cnt], dtype="<f4").reshape(npts, 2).astype(float)
        m = (p[:, 0] > BOX[0]) & (p[:, 0] < BOX[1]) & (p[:, 1] > BOX[2]) & (p[:, 1] < BOX[3])
        if m.sum() < 3:
            continue
        # clamp (not drop) outside points so big polygons stay closed shapes
        p[:, 0] = p[:, 0].clip(BOX[0], BOX[1]); p[:, 1] = p[:, 1].clip(BOX[2], BOX[3])
        q = [p[0]] + [b for a, b in zip(p[:-1], p[1:]) if (a != b).any()]
        out.append([[round(float(x), 4), round(float(y), 4)] for x, y in q])
    return out
land = read("gshhs", 1)
lakes = read("gshhs", 2)
borders = read("countries")
json.dump({"land": land, "lakes": lakes, "borders": borders}, open("assets/france_map.json", "w"))
print(len(land), len(lakes), len(borders), sum(len(p) for p in land))
