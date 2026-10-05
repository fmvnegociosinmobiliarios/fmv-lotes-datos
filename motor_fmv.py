# -*- coding: utf-8 -*-
"""
motor_fmv.py — Motor de factibilidad de lotes en CABA (FMV Soluciones Inmobiliarias).

Uso rápido (desde Python):
    from motor_fmv import analizar
    R = analizar("Cuba 2494", comps=[...], overrides={...})
    # R es un dict serializable (json) con: parcela, normativa, geometria, linderos, fondo, modelo, englobamiento, uso_actual, mapas

Uso por línea de comandos:
    python3 motor_fmv.py "Cuba 2494" [--smp 025-014-001] [--cfg config.json] [--out modelo.json]

Datos: carpeta FMV_DATA (por defecto ./datos) con comuna_XX.sqlite (o los CSV cXX_*.csv para reconstruirla),
indice_calles.csv y mercado.json. Ver README.md.
"""
import os, re, sys, json, math, sqlite3, csv, unicodedata, glob
import numpy as np
from shapely.geometry import Polygon, LineString, MultiLineString, Point
from shapely.ops import unary_union, linemerge

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("FMV_DATA") or (os.path.join(HERE, "datos") if os.path.isdir(os.path.join(HERE, "datos")) else HERE)
REPO_RAW = "https://raw.githubusercontent.com/fmvnegociosinmobiliarios/fmv-lotes-datos/main/"
MERCADO = json.load(open(os.path.join(HERE, "mercado.json"), encoding="utf-8"))

# ----------------------------------------------------------------------------- utilidades
def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"^(AV\.?|AVENIDA|AVDA\.?)\s+", "", s.strip()); s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def titulo_calle(c):
    """'AV. JUAN B. JUSTO' -> 'Av. Juan B. Justo'"""
    small = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "E"}
    out = []
    for i, w in enumerate(c.split()):
        if i and w in small: out.append(w.lower())
        else: out.append(w.capitalize() if not re.match(r"^\d", w) else w)
    return " ".join(out)

def db(comuna):
    """Conexión a la base de la comuna; si falta el .sqlite lo reconstruye desde los CSV cXX_*.csv."""
    c = int(comuna); p = os.path.join(DATA, f"comuna_{c:02d}.sqlite")
    if not os.path.exists(p) and not os.path.exists(p + ".gz"):   # descarga desde el repo público
        import urllib.request
        try: urllib.request.urlretrieve(REPO_RAW + f"comuna_{c:02d}.sqlite.gz", p + ".gz")
        except Exception as e: print("No pude descargar", REPO_RAW + f"comuna_{c:02d}.sqlite.gz", e, file=sys.stderr)
    if not os.path.exists(p) and os.path.exists(p + ".gz"):
        import gzip, shutil
        with gzip.open(p + ".gz", "rb") as g, open(p, "wb") as o: shutil.copyfileobj(g, o)
    if not os.path.exists(p):
        csvs = sorted(glob.glob(os.path.join(DATA, f"c{c:02d}_*.csv")))
        if not csvs: raise FileNotFoundError(f"No encuentro comuna_{c:02d}.sqlite ni los CSV c{c:02d}_*.csv en {DATA}")
        con = sqlite3.connect(p); cur = con.cursor()
        for f in csvs:
            t = os.path.basename(f)[4:-4]
            with open(f, newline="", encoding="utf-8") as fh:
                r = csv.reader(fh); cols = next(r)
                cur.execute(f"CREATE TABLE {t}({','.join(cols)})")
                cur.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * len(cols))})", r)
        cur.executescript("CREATE INDEX IF NOT EXISTS ix_p_sm ON parcelas(sm); CREATE INDEX IF NOT EXISTS ix_rus ON rus(smp); CREATE INDEX IF NOT EXISTS ix_fr ON frentes(smp); CREATE INDEX IF NOT EXISTS ix_fr_calle ON frentes(calle); CREATE INDEX IF NOT EXISTS ix_ob ON obras(smp); CREATE INDEX IF NOT EXISTS ix_aph ON aph(smp); CREATE INDEX IF NOT EXISTS ix_c3 ON cur3d(smp);")
        con.commit(); con.close()
    con = sqlite3.connect(p); con.row_factory = sqlite3.Row
    return con

def f(x, d=None):
    try: return float(x)
    except (TypeError, ValueError): return d

# ----------------------------------------------------------------------------- búsqueda de dirección
def parsear_direccion(texto):
    t = texto.strip()
    m = re.match(r"^(.*?)[\s,]+(\d{1,5})(?:\s*[/\-]\s*(\d{1,5}))?\b", t)
    if not m: raise ValueError(f"No entiendo la dirección '{texto}' (esperaba 'Calle 1234')")
    return norm(m.group(1)), int(m.group(2))

def buscar(direccion, comuna=None):
    """Devuelve lista de candidatos [{smp, calle, num_dom, comuna, barrio, esquina}] para 'Calle 1234'."""
    calle, num = parsear_direccion(direccion)
    idx = list(csv.DictReader(open(os.path.join(DATA, "indice_calles.csv"), encoding="utf-8")))
    cands = [r for r in idx if r["calle_norm"] == calle and int(r["num_min"]) - 150 <= num <= int(r["num_max"]) + 150]
    if not cands:  # búsqueda laxa por contención
        cands = [r for r in idx if calle in r["calle_norm"] and int(r["num_min"]) - 150 <= num <= int(r["num_max"]) + 150]
    if comuna: cands = [r for r in cands if int(r["comuna"]) == int(comuna)]
    out = []
    for com in sorted({r["comuna"] for r in cands}):
        con = db(com)
        nombres = sorted({r["calle"] for r in cands if r["comuna"] == com})
        q = ",".join("?" * len(nombres))
        for row in con.execute(f"SELECT f.smp, f.calle, f.num_dom, f.parc_esq, p.barrio FROM frentes f JOIN parcelas p USING(smp) WHERE f.calle IN ({q})", nombres):
            nums = [int(float(x)) for x in str(row["num_dom"]).split(".") if re.match(r"^\d+(\.0)?$", x)]
            if not nums: continue
            d = min(abs(n - num) for n in nums)
            if d <= 8 and (num % 2 == nums[0] % 2 or d == 0):
                out.append(dict(smp=row["smp"], calle=row["calle"], num_dom=row["num_dom"], comuna=int(com), barrio=row["barrio"], esquina=row["parc_esq"] == "S", dist=d))
        con.close()
    seen = {}; [seen.setdefault(o["smp"], o) for o in sorted(out, key=lambda o: o["dist"])]
    return list(seen.values())

# ----------------------------------------------------------------------------- datos de la parcela
def datos_parcela(smp, comuna=None):
    if comuna is None:
        idx = list(csv.DictReader(open(os.path.join(DATA, "indice_calles.csv"), encoding="utf-8")))
        cands = sorted({r["comuna"] for r in idx if r["seccion"] == smp[:3]}, key=lambda c: -sum(int(r["n"]) for r in idx if r["seccion"] == smp[:3] and r["comuna"] == c))
    else: cands = [comuna]
    for comuna in cands:
        con = db(comuna); P = con.execute("SELECT * FROM parcelas WHERE smp=?", (smp,)).fetchone()
        if P is not None: break
        con.close()
    if P is None: raise ValueError(f"Parcela {smp} no está en las bases de las comunas {cands}")
    d = dict(P); d["geom"] = json.loads(d["geom"]); d["comuna"] = int(comuna)
    d["cu"] = dict(con.execute("SELECT * FROM cu WHERE smp=?", (smp,)).fetchone() or {})
    d["rus"] = [dict(r) for r in con.execute("SELECT DISTINCT * FROM rus WHERE smp=?", (smp,))]
    d["frentes"] = [dict(r) for r in con.execute("SELECT DISTINCT calle, num_dom, parc_esq, ochava FROM frentes WHERE smp=?", (smp,))]
    d["obras"] = [dict(r) for r in con.execute("SELECT DISTINCT fecha, expediente, ubicacion, descripcio FROM obras WHERE smp=? ORDER BY fecha DESC", (smp,))]
    d["aph"] = [dict(r) for r in con.execute("SELECT DISTINCT * FROM aph WHERE smp=?", (smp,))]
    d["cur3d"] = [dict(r) for r in con.execute("SELECT DISTINCT tipo, h_ini, h_fin, edif FROM cur3d WHERE smp=? ORDER BY h_ini", (smp,))]
    # manzana completa
    mz = {}
    for r in con.execute("SELECT p.*, c.uni_edif_1, c.uso_1, c.catalogado, c.dist_1_grp FROM parcelas p LEFT JOIN cu c USING(smp) WHERE p.sm=?", (P["sm"],)):
        x = dict(r); x["geom"] = json.loads(x["geom"]); x["rus"] = []; x["frentes"] = []; mz[x["smp"]] = x
    q = ",".join("?" * len(mz))
    for r in con.execute(f"SELECT DISTINCT smp, tipo1, tipo2, estado, pisos, calle, puerta FROM rus WHERE smp IN ({q})", list(mz)): mz[r["smp"]]["rus"].append(dict(r))
    for r in con.execute(f"SELECT DISTINCT smp, calle, num_dom, parc_esq FROM frentes WHERE smp IN ({q})", list(mz)): mz[r["smp"]]["frentes"].append(dict(r))
    for r in con.execute(f"SELECT smp, count(*) n FROM obras WHERE smp IN ({q}) AND fecha >= '2021' GROUP BY smp", list(mz)): mz[r["smp"]]["obras_recientes"] = r["n"]
    d["manzana"] = mz
    con.close()
    return d

# ----------------------------------------------------------------------------- normativa
UNIDADES = {  # uni_edif_1 (capa CU norma 31/12/2024) -> unidad, altura máxima del cuerpo, plantas tipo sobre PB, retiros habitables, plano límite, basamento (CM/CA)
    0.0: dict(unidad="Normativa especial (U / APH / UP / EE)", cuerpo=0.0, n_tipo=0, retiros=0, plano=0.0, basamento=False, art="Anexo II", nota="La capa oficial no asigna altura genérica: la parcela está en un distrito de normativa especial (Anexo II); hay que consultar la ficha urbanística."),
    9.0: dict(unidad="USAB0 – Sustentabilidad de Altura Baja 0", cuerpo=9.0, n_tipo=2, retiros=0, plano=9.0, basamento=False, art="6.2.5", nota="Planta baja más dos pisos (9 m), sin retiros; se construye hasta la Línea de Frente Interno."),
    12.0: dict(unidad="USAB1 – Sustentabilidad de Altura Baja 1", cuerpo=12.0, n_tipo=3, retiros=0, plano=12.0, basamento=False, art="6.2.5", nota="Planta baja más tres pisos (12 m), sin retiros; se construye hasta la Línea de Frente Interno (modificación de dic-2024)."),
    14.6: dict(unidad="USAB2 – Sustentabilidad de Altura Baja 2", cuerpo=14.6, n_tipo=4, retiros=0, plano=14.6, basamento=False, art="6.2.6", nota="Planta baja más cuatro pisos (14,6 m), sin retiros; se construye hasta la Línea de Frente Interno (modificación de dic-2024)."),
    17.2: dict(unidad="USAM – Sustentabilidad de Altura Media", cuerpo=17.2, n_tipo=5, retiros=2, plano=24.2, basamento=False, art="6.2.4", nota="Planta baja más cinco pisos (17,2 m) y dos retiros habitables hasta el plano límite de 24,2 m."),
    22.8: dict(unidad="USAA – Sustentabilidad de Altura Alta", cuerpo=22.8, n_tipo=7, retiros=2, plano=29.8, basamento=False, art="6.2.3", nota="Planta baja más siete pisos (22,8 m) y dos retiros habitables hasta el plano límite de 29,8 m."),
    31.2: dict(unidad="CM – Corredor Medio", cuerpo=31.2, n_tipo=10, retiros=2, plano=38.2, basamento=True, art="6.2.2", nota="Planta baja más diez pisos (31,2 m), dos retiros habitables hasta 38,2 m y basamento de hasta 6 m que puede llegar a la Línea Interna de Basamento."),
    38.0: dict(unidad="CA – Corredor Alto", cuerpo=38.0, n_tipo=12, retiros=2, plano=45.0, basamento=True, art="6.2.1", nota="Planta baja más doce pisos (38 m), dos retiros habitables hasta 45 m y basamento de hasta 6 m que puede llegar a la Línea Interna de Basamento."),
}
RETIRO_H = [2.0, 4.0]          # retiros horizontales desde la L.O.: 1º 2 m (altura 3 m), 2º 4 m acumulados (altura 4 m) — art. 6.3.1
ESPACIO_FONDO = {9.0: 4.0, 12.0: 4.0, 14.6: 4.0, 17.2: 6.0, 22.8: 6.0, 31.2: 8.0, 38.0: 8.0}   # art. 6.4.2.4: parcelas no alcanzadas por la LFI
BANDA_MINIMA = 16.0            # art. 6.4: banda edificable garantizada desde la L.O.
CONSOLIDADO = 0.75             # art. 6.4.2.3: edificio consolidado = altura de fachada >= 75 % de la altura máxima de su unidad (o catalogado)
H_PISO = 2.9                   # altura NPT a NPT estimada para pisos existentes

MIXTURA = {0: "Sin mixtura asignada", 1: "Mixtura 1 – residencial de baja intensidad", 2: "Mixtura 2 – residencial con comercio diario", 3: "Mixtura 3 – mixto, comercio y servicios", 4: "Mixtura 4 – alta intensidad, corredores"}

def normativa(d):
    cu = d["cu"]; h = f(cu.get("uni_edif_1"), 0.0); u = UNIDADES.get(h, UNIDADES[0.0]).copy()
    u.update(altura_capa=h, altura_2=f(cu.get("uni_edif_2"), 0.0), mixtura=int(f(cu.get("uso_1"), 0)), mixtura_txt=MIXTURA.get(int(f(cu.get("uso_1"), 0)), ""),
             catalogado=int(f(cu.get("catalogado"), 0)) == 1, aph=any("DESESTIM" not in ((a.get("estado") or "") + (a.get("proteccion") or "")).upper() and (a.get("proteccion") or a.get("catalogacion")) for a in d["aph"]) or (cu.get("dist_1_grp") == "APH"), aph_detalle=d["aph"], tipo_mza=cu.get("tipo_mza"),
             rivolta=int(f(cu.get("rivolta"), 0)) == 1, lep=int(f(cu.get("lep"), 0)) == 1, ensanche=int(f(cu.get("ensanche"), 0)) == 1, riesgo_hidrico=int(f(cu.get("rh"), 0)) == 1,
             adps=cu.get("adps") == "SI", dist_cpu=cu.get("dist_cpu_1"), fot_cpu=f(cu.get("fot_em_1"), 0.0), alicuota=f(cu.get("alicuota"), 0.0), inc_uva=f(cu.get("inc_uva_21"), 0.0),
             dist_1_grp=cu.get("dist_1_grp"), dist_1_esp=cu.get("dist_1_esp"), cur3d=d["cur3d"])
    if u["fot_cpu"] is not None and u["fot_cpu"] < 0: u["fot_cpu"] = 0.0
    return u

# ----------------------------------------------------------------------------- geometría y LFI
def _poly(coords): return Polygon(coords).buffer(0)

def _dir_clusters(line, tol_deg=20):
    """Agrupa los segmentos de una línea por dirección (para separar frentes de distintas calles)."""
    segs = []
    geoms = list(line.geoms) if hasattr(line, "geoms") else [line]
    for g in geoms:
        c = list(g.coords)
        for a, b in zip(c[:-1], c[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < 0.3: continue
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
            segs.append((ang, L, LineString([a, b])))
    groups = []
    for ang, L, s in sorted(segs, key=lambda x: -x[1]):
        for g in groups:
            if min(abs(g["ang"] - ang), 180 - abs(g["ang"] - ang)) < tol_deg: g["segs"].append(s); g["L"] += L; break
        else: groups.append(dict(ang=ang, segs=[s], L=L))
    return groups

def _block_of(G, smp):
    block = unary_union(list(G.values())).buffer(0.02).buffer(-0.02)
    if block.geom_type != "Polygon": block = next((b for b in block.geoms if b.intersects(G[smp])), max(block.geoms, key=lambda b: b.area))
    return block

def _street_edge(g, block):
    """Parte del perímetro de la parcela que coincide con el perímetro de la manzana (= línea oficial / frentes)."""
    return g.exterior.intersection(block.exterior.buffer(0.08))

def geo_simple(G, smp, block, lfi):
    g = G[smp]; se = _street_edge(g, block)
    return dict(sup=g.area, frente=se.length, huella=g.intersection(se.buffer(lfi)).area if se.length > 0.5 else 0.0)

def geometria(d, lfi_pct=0.25, lfi_override=None):
    smp = d["smp"]; mz = d["manzana"]
    G = {s: _poly(x["geom"]) for s, x in mz.items() if len(x["geom"]) >= 4}
    tg = G[smp]; others = unary_union([g for s, g in G.items() if s != smp]); block = _block_of(G, smp)
    street_edge = _street_edge(tg, block)
    groups = [g for g in _dir_clusters(street_edge) if g["L"] > 2.5]
    # ochava: grupo corto (2,5–8 m) cuya dirección difiere ~45° de las otras
    ochava_len = 0.0; frentes = []
    for g in groups:
        if 2.5 < g["L"] < 8.5 and len(groups) > 1 and all(30 < min(abs(g["ang"] - h["ang"]), 180 - abs(g["ang"] - h["ang"])) < 60 for h in groups if h is not g and h["L"] >= 8.5):
            ochava_len = g["L"]
        else: frentes.append(g)
    frentes.sort(key=lambda g: -g["L"]); esquina = len(frentes) >= 2 or any(fr.get("parc_esq") == "S" for fr in d["frentes"])
    cateto = ochava_len / math.sqrt(2) if ochava_len else 0.0
    for g in frentes[:2]:
        if cateto: g["L"] += cateto   # frente medido hasta el vértice teórico de la esquina
    # nombre de calle por dirección: comparo con los frentes de los vecinos que tienen esa calle
    calles = sorted({fr["calle"] for fr in d["frentes"]})
    dir_calle = {}
    for c in calles:
        segs = []
        for s, x in mz.items():
            if any(fr["calle"] == c for fr in x["frentes"]) and s in G:
                se = _street_edge(G[s], block)
                segs += [(g["ang"], g["L"]) for g in _dir_clusters(se) if g["L"] > 4]
        if segs:
            # dirección dominante ponderada
            best = max(segs, key=lambda t: t[1])[0]; dir_calle[c] = best
    for g in frentes:
        g["calle"] = min(dir_calle, key=lambda c: min(abs(dir_calle[c] - g["ang"]), 180 - abs(dir_calle[c] - g["ang"]))) if dir_calle else (calles[0] if calles else "")
    # frente principal = el de la dirección pedida (primer frente de la tabla) si existe, si no el más largo
    principal = frentes[0] if frentes else None
    ang = math.radians(principal["ang"]) if principal else 0.0
    dvec = np.array([math.cos(ang), math.sin(ang)]); nvec = np.array([-dvec[1], dvec[0]])
    def extent(geom, v):
        xy = np.array(geom.exterior.coords) if geom.geom_type == "Polygon" else np.array([c for g in geom.geoms for c in g.exterior.coords])
        pr = xy @ v; return pr.max() - pr.min()
    fondo = extent(tg, nvec); frente_len = principal["L"] if principal else 0.0
    # ancho local de manzana: rayo perpendicular al frente, desde su punto medio, hasta salir de la manzana
    ancho_mz = extent(block, nvec)
    if principal:
        mid = unary_union(principal["segs"]).interpolate(0.5, normalized=True) if len(principal["segs"]) == 1 else max(principal["segs"], key=lambda s_: s_.length).interpolate(0.5, normalized=True)
        ray = LineString([(mid.x - nvec[0] * 400, mid.y - nvec[1] * 400), (mid.x + nvec[0] * 400, mid.y + nvec[1] * 400)]).intersection(block)
        parts = list(ray.geoms) if hasattr(ray, "geoms") else [ray]
        parts = [p for p in parts if p.length > 1 and p.distance(mid) < 0.5]
        if parts: ancho_mz = max(p.length for p in parts)
    lfi = lfi_override if lfi_override else max(lfi_pct * ancho_mz, BANDA_MINIMA)   # art. 6.4: 16 m garantizados
    lib = ancho_mz / 3.0                                                               # L.I.B. a los tercios (basamento en CM/CA, subsuelos en todos)
    street_line = unary_union([s for g in frentes for s in g["segs"]])
    band = street_line.buffer(lfi)
    footprint = tg.intersection(band)
    huella_lib = tg.intersection(street_line.buffer(lib)).area
    # proximidad a esquina (art. 6.4.2.3): parcelas a menos de 1/4 + 9 m (máx. 34 m) de la prolongación de las L.O. concurrentes
    bc = list(block.simplify(1.5).exterior.coords)[:-1]; corners = []
    for i in range(len(bc)):   # vértices de la manzana = cambios de dirección mayores a 35°
        a, b, c_ = bc[i - 1], bc[i], bc[(i + 1) % len(bc)]
        a1 = math.atan2(b[1] - a[1], b[0] - a[0]); a2 = math.atan2(c_[1] - b[1], c_[0] - b[0]); dang = abs((math.degrees(a2 - a1) + 180) % 360 - 180)
        if 35 < dang < 150: corners.append(Point(b))
    dist_esq = min(tg.distance(c) for c in corners) if corners else 999.0
    proxima_esquina = (not esquina) and dist_esq < min(lfi_pct * ancho_mz + 9.0, 34.0)
    # banda del fondo: franja edificable de las calles opuestas (parcelas de la manzana que NO tienen las calles del lote)
    opp = []
    for s, x in mz.items():
        if s == smp or s not in G: continue
        if {fr["calle"] for fr in x["frentes"]} & set(calles): continue
        se = _street_edge(G[s], block)
        if se.length > 2: opp.append(se.buffer(lfi).intersection(G[s]))
    opp_band = unary_union(opp) if opp else None
    dist_fondo = tg.distance(opp_band) if opp_band is not None else None
    fondo_libre = max(ancho_mz - lfi - fondo, 0.0)  # distancia entre el contrafrente y la LFI de la calle opuesta (manzana típica)
    # linderos: parcelas con borde compartido > 1 m
    linderos = []
    for s, g in G.items():
        if s == smp: continue
        sh = tg.exterior.intersection(g.buffer(0.05)).length
        if sh > 1.0:
            x = mz[s]; pisos = max([int(f(r["pisos"], 0)) for r in x["rus"]] or [0])
            tipo = sorted({(r["tipo1"] or "") + ("/" + r["tipo2"] if r.get("tipo2") else "") for r in x["rus"]})
            dirs = sorted({f'{titulo_calle(fr["calle"])} {fr["num_dom"].replace(".", "/")}' for fr in x["frentes"]})
            fondo_l = street_edge.distance(g) > 3  # no toca la calle del lote => lindero de fondo
            u_l = f(x.get("uni_edif_1"), 0.0) or 0.0; h_fachada = (3.0 + H_PISO * (pisos - 1)) if pisos else 0.0
            catal = int(f(x.get("catalogado"), 0)) == 1
            consolidado = bool(catal or (u_l and h_fachada >= CONSOLIDADO * u_l))
            linderos.append(dict(smp=s, direccion="; ".join(dirs), area=round(g.area, 1), pisos=pisos, h_fachada=round(h_fachada, 1), uso=", ".join(tipo), uni_edif=u_l,
                                 catalogado=catal, consolidado=consolidado, supera_unidad=bool(h_fachada > u_l + 1.0) if u_l else False,
                                 borde_compartido=round(sh, 1), de_fondo=bool(fondo_l) and not any(fr["calle"] in calles for fr in x["frentes"]),
                                 edificio=bool(consolidado or pisos >= 4 or (pisos >= 3 and any("MULTIFAMILIAR" in t for t in tipo))), obras_recientes=x.get("obras_recientes", 0)))
    # vecinos de fondo (para riesgo de tapado): parcelas de calle opuesta que tocan la parcela
    fondo_vecinos = [l for l in linderos if l["de_fondo"]]
    return dict(sup=round(tg.area, 1), frente=round(frente_len, 2), frentes=[dict(calle=titulo_calle(g["calle"]), largo=round(g["L"], 2)) for g in frentes], esquina=esquina,
                ochava_len=round(ochava_len, 2), ochava_area=round((ochava_len / math.sqrt(2)) ** 2 / 2, 1) if ochava_len else 0.0,
                fondo=round(fondo, 2), ancho_mz=round(ancho_mz, 1), lfi=round(lfi, 2), lib=round(lib, 2), huella=round(footprint.area, 1), huella_lib=round(huella_lib, 1), fuera_lfi=round(tg.area - footprint.area, 1),
                alcanzada_lfi=bool(tg.area - footprint.area > 2.0), proxima_esquina=proxima_esquina, dist_esquina=round(dist_esq, 1),
                linderos_consolidados_abiertos=False,
                dist_fondo_banda_opuesta=None if dist_fondo is None else round(dist_fondo, 1), fondo_libre_teorico=round(fondo_libre, 1),
                linderos=sorted(linderos, key=lambda l: -l["borde_compartido"]), fondo_vecinos=fondo_vecinos,
                _tg=tg, _G=G, _footprint=footprint, _band=band, _opp=opp_band, _street=street_edge, _block=block)

# ----------------------------------------------------------------------------- modelo económico
def mercado_barrio(barrio):
    b = norm(barrio or "")
    for k, v in MERCADO["barrios"].items():
        if norm(k) == b: m = dict(MERCADO["default"]); m.update(v); return m
    m = dict(MERCADO["default"]); m["_fallback"] = True; return m

def proyecto(F, frente_total, n_tipo, retiros, comun, pb_comun, ochava=0.0, min_planta=25.0, basamento_extra=0.0, fondo_retiro=0.0, contrafrente_retiro2=0.0):
    """Balance de superficies de un edificio entre medianeras (o esquina) con huella F (art. 6.3.1: retiros de 2 m y 4 m desde la L.O.).
    basamento_extra: m² adicionales de PB y 1º piso hasta la L.I.B. en corredores (art. 6.4.3); fondo_retiro: m² a dejar libres en el
    contrafrente de plantas tipo cuando la parcela no está alcanzada por la LFI (art. 6.4.2.4); contrafrente_retiro2: m² del 2º retiro en contrafrente (CM/CA)."""
    F = max(F - ochava, 0.0); Ft = max(F - fondo_retiro, 0.0)
    plantas = [dict(nivel="PB (hall, medidores, local/unidad)" + (" + basamento" if basamento_extra else ""), n=1, cub_comun=min(pb_comun, F), cub_vend=max(F + basamento_extra - pb_comun, 0), exp=0.0)]
    if basamento_extra and n_tipo:
        plantas.append(dict(nivel="1 (basamento hasta L.I.B.)", n=1, cub_comun=comun, cub_vend=max(Ft + basamento_extra - comun, 0), exp=0.10 * Ft)); n_rest = n_tipo - 1
    else: n_rest = n_tipo
    if n_rest: plantas.append(dict(nivel=f"{n_tipo - n_rest + 1} a {n_tipo}", n=n_rest, cub_comun=comun, cub_vend=max(Ft - comun, 0), exp=0.16 * Ft))
    usados = 0
    for k in range(retiros):
        rk = Ft - RETIRO_H[k] * frente_total - (contrafrente_retiro2 if k == 1 else 0.0)
        if rk - comun >= min_planta:
            plantas.append(dict(nivel=f"{n_tipo + k + 1} (retiro {k + 1})", n=1, cub_comun=comun, cub_vend=rk - comun, exp=RETIRO_H[k] * frente_total * 0.7 + 0.10 * Ft)); usados += 1
        else:
            plantas.append(dict(nivel=f"{n_tipo + k + 1} (retiro {k + 1}) – terraza / SUM", n=1, cub_comun=max(min(rk, comun), 0), cub_vend=0.0, exp=0.0)); break
    for p in plantas:
        p["cub_total"] = (p["cub_comun"] + p["cub_vend"]) * p["n"]; p["vend_total"] = p["cub_vend"] * p["n"]; p["comun_total"] = p["cub_comun"] * p["n"]; p["exp_total"] = p["exp"] * p["n"]
    cub = sum(p["cub_total"] for p in plantas); vend = sum(p["vend_total"] for p in plantas); exp = sum(p["exp_total"] for p in plantas)
    return dict(huella=F, huella_tipo=Ft, basamento_extra=basamento_extra, fondo_retiro=fondo_retiro, plantas=plantas, cub_total=cub, vend_cub=vend, comun=sum(p["comun_total"] for p in plantas), exp_total=exp, vend_pond=vend + 0.5 * exp,
                retiros_utiles=usados, n_plantas=1 + n_tipo + usados, pb_vend=plantas[0]["cub_vend"], eficiencia=vend / cub if cub else 0)

def modelo(sup, F, frente_total, N, M, ochava=0.0, pb_comun=None, comun=None, cub_exist=None, extras=None, comps=None, margen=0.22, geo=None):
    """N = normativa(), M = mercado del barrio. Devuelve el modelo completo (3 niveles, plusvalía, sensibilidad, valor real)."""
    UVA, MEP = MERCADO["global"]["UVA"], MERCADO["global"]["MEP"]; ind = MERCADO["global"]["indirectos"]
    comun = comun or M.get("nucleo_m2", 26.0); pb_comun = pb_comun if pb_comun is not None else (45.0 if F < 250 else 60.0 if F < 500 else 90.0)
    bas = max((geo or {}).get("huella_lib", F) - F, 0.0) if N.get("basamento") else 0.0
    fondo_ret = 0.0; cf2 = 0.0
    if geo and not geo.get("alcanzada_lfi", True) and not geo.get("esquina") and N["n_tipo"] >= 3:   # parcela entre medianeras no alcanzada por la LFI: espacio urbano de fondo (art. 6.4.2.4)
        fondo_ret = ESPACIO_FONDO.get(N.get("altura_capa", 0.0), 0.0) * frente_total
    if N.get("basamento"): cf2 = 4.0 * frente_total * 0.5      # 2º retiro también en contrafrente en corredores (4 m), ponderado
    pr = proyecto(F, frente_total, N["n_tipo"], N["retiros"], comun, pb_comun, ochava, basamento_extra=bas, fondo_retiro=fondo_ret, contrafrente_retiro2=cf2)
    cub, vend, exp, vp = pr["cub_total"], pr["vend_cub"], pr["exp_total"], pr["vend_pond"]
    cap_cpu = (N["fot_cpu"] or 0) * sup
    # Ley 6.062: base = (superficie sobre rasante sin balcones − 20 %) − FOT del CPU × superficie de parcela; se muestra también el cálculo sin la deducción
    adicional = max(0.8 * cub - cap_cpu, 0); plusv_uva = adicional * N["inc_uva"] * N["alicuota"]; plusv_usd = plusv_uva * UVA / MEP
    adicional_v = max(cub - cap_cpu, 0); plusv_usd_v = adicional_v * N["inc_uva"] * N["alicuota"] * UVA / MEP
    demol = MERCADO["global"]["demolicion_usd_m2"] * (cub_exist if cub_exist else max(sup * 1.2, 150))
    extras = dict(extras or {})
    if N.get("riesgo_hidrico"): extras.setdefault("retardo_pluvial", MERCADO["global"]["retardo_pluvial_usd"])
    extras_tot = sum(extras.values())
    plazo_aprob = MERCADO["global"]["plazo_aprob_base"] + (1 if frente_total > 15 else 0) + (1 if N.get("riesgo_hidrico") else 0) + (1 if plusv_usd > 0 else 0) + (3 if (N.get("aph") or N.get("catalogado")) else 0)
    niveles = ["Estándar", "Alto", "Premium"]; esc = {}
    for i, k in enumerate(niveles):
        pv, pl, cd = M["precio_venta"][i], M["precio_local_pb"][i], M["costo_directo"][i]
        plazo_obra = round(MERCADO["global"]["plazo_obra_base"] + cub * MERCADO["global"]["plazo_obra_por_m2"] + 3 * i)
        ventas = (vend - pr["pb_vend"]) * pv + pr["pb_vend"] * pl + exp * pv * 0.5
        directo = cub * cd + exp * cd * 0.5
        indirectos = directo * (ind["proyecto_direccion"] + ind["derechos_tasas"] + ind["imprevistos"])
        com = ventas * (ind["comercializacion"] + ind["publicidad"] + ind["legales_escrituras"])
        cst = directo + indirectos + com + demol + plusv_usd + extras_tot
        e = dict(precio_m2=pv, precio_local=pl, costo_m2=cd, ventas=ventas, directo=directo, indirectos=indirectos, comercial=com, demolicion=demol, plusvalia=plusv_usd, extras=extras_tot,
                 costo_sin_terreno=cst, terreno_residual=ventas / (1 + margen) - cst, residual_m15=ventas / 1.15 - cst, breakeven_lote=ventas - cst,
                 plazo_obra=plazo_obra, plazo_aprob=plazo_aprob, plazo=plazo_aprob + plazo_obra + 6)
        e["inc_m2_vend"] = e["terreno_residual"] / vp if vp else 0; e["precio_lote_m2"] = e["terreno_residual"] / sup
        esc[k] = e
    # valor de mercado / publicación: comparables (si hay) o incidencias del barrio
    if comps:
        inc_v = [c["precio"] / c["vendibles"] for c in comps if c.get("vendibles")]; lm2 = [c["precio"] / c["sup"] for c in comps if c.get("sup")]
        inc_med = float(np.median(inc_v)) if inc_v else M["inc_vendible"][1]; lm2_med = float(np.median(lm2)) if lm2 else M["lote_m2"][1]
        vml = dict(inc_vend_med=inc_med, lote_m2_med=lm2_med, por_vendible=inc_med * vend, por_m2_lote=lm2_med * sup, fuente="comparables publicados")
    else:
        vml = dict(inc_vend_med=M["inc_vendible"][1], lote_m2_med=M["lote_m2"][1], por_vendible=M["inc_vendible"][1] * vend, por_m2_lote=M["lote_m2"][1] * sup, fuente="incidencias de referencia del barrio (mercado.json)")
    vml_pub = (vml["por_vendible"] + vml["por_m2_lote"]) / 2
    for k, e in esc.items():
        e["margen_lote_pub"] = (e["ventas"] - e["costo_sin_terreno"] - vml_pub) / (e["costo_sin_terreno"] + vml_pub)
        e["permuta_pct"] = max(e["terreno_residual"], 0) / e["ventas"] if e["ventas"] else 0
        e["precio_necesario_m22"] = (e["costo_sin_terreno"] + vml_pub) * (1 + margen) / vp if vp else 0
    E = esc["Estándar"]
    precio_real = dict(piso=E["terreno_residual"], techo=E["residual_m15"], publicacion=vml_pub, viable=E["terreno_residual"] > 0.5 * vml_pub and E["terreno_residual"] > 0)
    # sensibilidad precio × costo (nivel estándar)
    pv0, cd0 = M["precio_venta"][0], M["costo_directo"][0]; sens = []
    for pv in (pv0 - 250, pv0, pv0 + 250, pv0 + 500):
        row = []
        for cd in (cd0 - 100, cd0, cd0 + 150, cd0 + 300):
            ventas = (vend - pr["pb_vend"]) * pv + pr["pb_vend"] * (pv + M["precio_local_pb"][0] - pv0) + exp * pv * 0.5
            directo = cub * cd + exp * cd * 0.5
            cst = directo * (1 + ind["proyecto_direccion"] + ind["derechos_tasas"] + ind["imprevistos"]) + ventas * (ind["comercializacion"] + ind["publicidad"] + ind["legales_escrituras"]) + demol + plusv_usd + extras_tot
            row.append(ventas / (1 + margen) - cst)
        sens.append((pv, row))
    pr.update(sup=sup, frente_total=frente_total, ochava=ochava, cap_cpu=cap_cpu, adicional=adicional, plusv_uva=plusv_uva, plusv_usd=plusv_usd, adicional_vend=adicional_v, plusv_usd_v=plusv_usd_v,
              UVA=UVA, MEP=MEP, esc=esc, vml=vml, vml_pub=vml_pub, precio_real=precio_real, sens=sens, sens_cols=[cd0 - 100, cd0, cd0 + 150, cd0 + 300], plazo_aprob=plazo_aprob,
              demolicion_usd=demol, extras=extras, margen=margen, comps=comps or [], mercado=M)
    return pr

# ----------------------------------------------------------------------------- englobamiento
def englobamiento(d, geo, N, M, umbral=0.10, comps=None):
    """Evalúa englobar con cada lindero apto (no edificio) y con todos juntos. Devuelve lista ordenada por ganancia %."""
    base = modelo(geo["sup"], geo["huella"], sum(fr["largo"] for fr in geo["frentes"]), N, M, geo["ochava_area"], comps=comps)
    aptos = [l for l in geo["linderos"] if not l["edificio"] and not l.get("consolidado") and l["pisos"] <= 3]
    res = []
    combos = [[l] for l in aptos] + ([[a, b] for i, a in enumerate(aptos) for b in aptos[i + 1:]] if len(aptos) > 1 else [])   # de a uno y de a pares: más de dos dueños no es realista
    for combo in combos:
        polys = [geo["_tg"]] + [geo["_G"][l["smp"]] for l in combo]
        u = unary_union(polys).buffer(0.02).buffer(-0.02)
        if u.geom_type != "Polygon": continue
        se_u = _street_edge(u, geo["_block"]); fp = u.intersection(se_u.buffer(geo["lfi"])).area
        fr_tot = se_u.length - geo["ochava_len"] + 2 * (geo["ochava_len"] / math.sqrt(2) if geo["ochava_len"] else 0)
        nuc = 1 if fp < 450 else 2
        sep = [geo_simple(geo["_G"], l["smp"], geo["_block"], geo["lfi"]) for l in combo]
        sep_vend = base["vend_cub"] + sum(modelo(x["sup"], x["huella"], x["frente"], N, M, comun=M.get("nucleo_m2", 26.0) * (1 if x["huella"] < 450 else 2))["vend_cub"] for x in sep)
        mu = modelo(u.area, fp, fr_tot, N, M, geo["ochava_area"], comun=M.get("nucleo_m2", 26.0) * nuc, comps=comps)
        gan = mu["vend_cub"] / sep_vend - 1 if sep_vend else 0
        res.append(dict(con=[dict(smp=l["smp"], direccion=l["direccion"], area=l["area"], pisos=l["pisos"], uso=l["uso"], frente=round(x["frente"], 1), huella=round(x["huella"], 1)) for l, x in zip(combo, sep)], sup=round(u.area, 1), huella=round(fp, 1), frente=round(fr_tot, 1),
                        vend=mu["vend_cub"], cub=mu["cub_total"], vend_separadas=sep_vend, ganancia_pct=gan, residual=mu["esc"]["Estándar"]["terreno_residual"], vend_por_m2_lote=mu["vend_cub"] / u.area,
                        recomendado=bool(gan >= umbral and mu["esc"]["Estándar"]["terreno_residual"] > 0), nucleos=nuc))
    res.sort(key=lambda r: -r["ganancia_pct"])
    excluidos = [dict(smp=l["smp"], direccion=l["direccion"], motivo="edificio consolidado (art. 6.4.2.3: fachada ≥ 75 % de la altura máxima de su unidad)" if l.get("consolidado") else ("edificio en propiedad horizontal o varios dueños" if l["edificio"] else "más de 3 plantas")) for l in geo["linderos"] if l not in aptos]
    return dict(base_vend=base["vend_cub"], opciones=res, excluidos=excluidos, umbral=umbral)

# ----------------------------------------------------------------------------- completamiento de tejido (enrase, art. 6.5.5)
def enrase(geo, N, M, base, comps=None):
    """Escenario con completamiento de tejido: si un lindero consolidado supera la altura máxima de la unidad, la obra nueva puede adosarse
    equiparando niveles (art. 6.5.5). No se admite en USAB para los casos A; en USAB sólo casos B limitados (ancho 5 m, doble altura). Sujeto a consulta."""
    if not N["n_tipo"] or N["cuerpo"] <= 0: return dict(aplica=False, motivo="sin unidad genérica")
    altos = [l for l in geo["linderos"] if l.get("consolidado") and l["h_fachada"] > N["plano"] + 1.0 and not l["de_fondo"]]
    if not altos: return dict(aplica=False, motivo="ningún lindero consolidado supera el plano límite de la unidad")
    if N["altura_capa"] <= 14.6: return dict(aplica=False, motivo="en USAB el completamiento de tejido sólo se admite en casos B muy limitados (ancho máximo 5 m); se deja como consulta", linderos=[l["direccion"] for l in altos])
    l = max(altos, key=lambda x: x["h_fachada"]); h_obj = min(l["h_fachada"], N["plano"] + 4 * H_PISO + 0.1) if len(altos) == 1 else max(x["h_fachada"] for x in altos)
    extra = max(int((h_obj - N["plano"]) // H_PISO), 0)
    if extra <= 0: return dict(aplica=False, motivo="la diferencia de altura no alcanza para una planta completa")
    mu = modelo(geo["sup"], geo["huella"], sum(fr["largo"] for fr in geo["frentes"]) or geo["frente"], dict(N, n_tipo=N["n_tipo"] + extra, retiros=N["retiros"]), M, geo["ochava_area"], comps=comps, geo=geo)
    return dict(aplica=True, caso="A (dos linderos más altos)" if len(altos) > 1 else "B (un lindero más alto)", linderos=[dict(direccion=x["direccion"], h_fachada=x["h_fachada"], pisos=x["pisos"]) for x in altos],
                plantas_extra=extra, altura_objetivo=round(h_obj, 1), vend=mu["vend_cub"], cub=mu["cub_total"], ganancia_vend=mu["vend_cub"] - base["vend_cub"], residual=mu["esc"]["Estándar"]["terreno_residual"],
                plusv_usd=mu["plusv_usd"], nota="Sujeto a consulta ante la DGIUR: el volumen debe adosarse en toda su extensión equiparando techos y retiros del lindero, con tratamiento de fachada en la cara lateral; los metros por encima de la capacidad del CPU pagan plusvalía.")

# ----------------------------------------------------------------------------- tasación por uso actual
def uso_actual(d, geo, M, cub_exist=None, factor_estado=None):
    pisos = max([int(f(r["pisos"], 0)) for r in d["rus"]] or [1]); usos = sorted({(r["tipo1"] or "") + ("/" + r["tipo2"] if r.get("tipo2") else "") for r in d["rus"]})
    cub = cub_exist or round(min(geo["sup"] * 0.8, geo["huella"]) * (1 + 0.7 * (pisos - 1)), 0)
    fe = factor_estado if factor_estado is not None else 0.65   # construcción antigua sin relevar: descuento por estado y obsolescencia
    lo, hi = M["usado_m2"][0] * fe, M["usado_m2"][1] * fe; vlo, vhi = M["lote_m2"][0], M["lote_m2"][1]
    r = dict(pisos=pisos, usos=usos, cub_exist=cub, factor_estado=fe, rango_uso=(cub * lo, cub * hi), rango_lote=(geo["sup"] * vlo, geo["sup"] * vhi), usado_m2=[lo, hi], usado_m2_bruto=M["usado_m2"], lote_m2=M["lote_m2"])
    r["rango"] = (max(r["rango_uso"][0], r["rango_lote"][0]), max(r["rango_uso"][1], r["rango_lote"][1]))
    r["rango_ocupado"] = (r["rango"][0] * 0.6, r["rango"][1] * 0.65)
    return r

# ----------------------------------------------------------------------------- mapas
def mapas(d, geo, prefix):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MPoly
    G, tg, fp = geo["_G"], geo["_tg"], geo["_footprint"]; mz = d["manzana"]
    # portada: fondo oscuro, trazos dorados
    fig, ax = plt.subplots(figsize=(5, 5)); fig.patch.set_facecolor("#141416"); ax.set_facecolor("#141416")
    for s, g in G.items():
        ax.add_patch(MPoly(np.array(g.exterior.coords), closed=True, fc="#1b1b1e", ec="#c9a227", lw=0.8))
    ax.add_patch(MPoly(np.array(tg.exterior.coords), closed=True, fc="#e6c766", ec="#e6c766", lw=1.2))
    ax.set_aspect("equal"); ax.autoscale(); ax.axis("off"); fig.savefig(prefix + "_oro.png", dpi=220, bbox_inches="tight", pad_inches=0.05, facecolor="#141416"); plt.close(fig)
    # interior: pisos por parcela, huella LFI, lote
    fig, ax = plt.subplots(figsize=(7.2, 5.6)); fig.patch.set_facecolor("#f7f5f0"); ax.set_facecolor("#f7f5f0")
    for s, g in G.items():
        x = mz[s]; pisos = max([int(f(r["pisos"], 0)) for r in x["rus"]] or [0])
        col = "#ffffff" if pisos <= 1 else "#ece6d6" if pisos <= 3 else "#d6ccb0" if pisos <= 6 else "#b9a87c"
        ax.add_patch(MPoly(np.array(g.exterior.coords), closed=True, fc=col, ec="#6b6b6b", lw=0.5))
        c = g.representative_point()
        if g.area > 60: ax.text(c.x, c.y, f"{s[-4:].lstrip('0') or '0'}\n{pisos}p", ha="center", va="center", fontsize=5, color="#333333")
    if geo["_opp"] is not None:
        for g in (geo["_opp"].geoms if hasattr(geo["_opp"], "geoms") else [geo["_opp"]]):
            if g.geom_type == "Polygon": ax.add_patch(MPoly(np.array(g.exterior.coords), closed=True, fc="none", ec="#8f7119", lw=0.6, ls=":"))
    fpg = fp if fp.geom_type == "Polygon" else max(fp.geoms, key=lambda p: p.area)
    ax.add_patch(MPoly(np.array(tg.exterior.coords), closed=True, fc="#e6c766", ec="#8f7119", lw=1.5))
    ax.add_patch(MPoly(np.array(fpg.exterior.coords), closed=True, fc="none", ec="#0b0b0c", lw=1.4, ls="--"))
    for l in geo["linderos"]:
        if not l["edificio"] and l["pisos"] <= 3: ax.add_patch(MPoly(np.array(G[l["smp"]].exterior.coords), closed=True, fc="none", ec="#c9a227", lw=1.6))
    ax.set_aspect("equal"); ax.autoscale(); ax.axis("off")
    ax.set_title("Manzana: pisos existentes (RUS 2022-24). Dorado: lote · trazo negro: huella edificable (LFI) · borde dorado: linderos englobables · punteado: franja edificable de la calle opuesta", fontsize=6.3, color="#333333")
    fig.savefig(prefix + "_manzana.png", dpi=200, bbox_inches="tight", pad_inches=0.05, facecolor="#f7f5f0"); plt.close(fig)
    return dict(oro=prefix + "_oro.png", manzana=prefix + "_manzana.png")

# ----------------------------------------------------------------------------- orquestación
def analizar(direccion=None, smp=None, comuna=None, comps=None, overrides=None, workdir=".", umbral_englobe=0.10):
    ov = overrides or {}
    if smp is None:
        c = buscar(direccion, comuna)
        if not c: raise ValueError(f"No encontré '{direccion}' en el índice de calles")
        smp = c[0]["smp"]; comuna = c[0]["comuna"]
        if len({x["smp"] for x in c}) > 1: print("Candidatos:", [(x['smp'], x['calle'], x['num_dom']) for x in c[:6]], file=sys.stderr)
    d = datos_parcela(smp, comuna); N = normativa(d); N.update(ov.get("normativa", {}))
    geo = geometria(d, lfi_override=ov.get("lfi"))
    for k in ("huella", "sup", "frente", "ochava_area"):
        if k in ov: geo[k] = ov[k]
    M = mercado_barrio(d["barrio"]); M.update(ov.get("mercado", {}))
    frente_total = sum(fr["largo"] for fr in geo["frentes"]) if geo["frentes"] else geo["frente"]
    mod = modelo(geo["sup"], geo["huella"], frente_total, N, M, geo["ochava_area"], pb_comun=ov.get("pb_comun"), cub_exist=ov.get("cub_exist"), extras=ov.get("extras"), comps=comps, geo=geo)
    enr = enrase(geo, N, M, mod, comps)
    eng = englobamiento(d, geo, N, M, umbral_englobe, comps) if N["n_tipo"] else dict(base_vend=0, opciones=[], excluidos=[], umbral=umbral_englobe)
    uso = uso_actual(d, geo, M, ov.get("cub_exist"), ov.get("factor_estado"))
    prefix = os.path.join(workdir, "mapa_" + smp.replace("-", "_")); mp = mapas(d, geo, prefix)
    dirs = sorted({f'{titulo_calle(fr["calle"])} {fr["num_dom"].replace(".", "/")}' for fr in d["frentes"]})
    R = dict(smp=smp, partida=d["partida"], barrio=d["barrio"], comuna=d["comuna"], sm=d["sm"], direcciones=dirs, direccion=direccion or dirs[0],
             normativa={k: v for k, v in N.items()}, geometria={k: v for k, v in geo.items() if not k.startswith("_")}, rus=d["rus"], obras=d["obras"], aph=d["aph"],
             manzana_resumen=dict(parcelas=len(d["manzana"]), obras_recientes=sum(x.get("obras_recientes", 0) for x in d["manzana"].values()),
                                  pisos_max=max([int(f(r["pisos"], 0)) for x in d["manzana"].values() for r in x["rus"]] or [0]),
                                  pisos_prom=float(np.mean([max([int(f(r["pisos"], 0)) for r in x["rus"]] or [0]) for x in d["manzana"].values()]))),
             modelo=mod, englobamiento=eng, enrase=enr, uso_actual=uso, mapas=mp, mercado=M, global_=MERCADO["global"])
    R["viable"] = bool(mod["precio_real"]["viable"]) and N["n_tipo"] > 0
    return R

def _ser(o):
    if isinstance(o, (np.floating, np.integer)): return float(o)
    if isinstance(o, tuple): return list(o)
    return str(o)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("direccion", nargs="?"); ap.add_argument("--smp"); ap.add_argument("--comuna"); ap.add_argument("--cfg"); ap.add_argument("--out", default="modelo.json")
    a = ap.parse_args(); cfg = json.load(open(a.cfg, encoding="utf-8")) if a.cfg else {}
    R = analizar(a.direccion, smp=a.smp or cfg.get("smp"), comuna=a.comuna, comps=cfg.get("comps"), overrides=cfg.get("overrides"), workdir=os.path.dirname(os.path.abspath(a.out)))
    json.dump(R, open(a.out, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=_ser)
    g, m, E = R["geometria"], R["modelo"], R["modelo"]["esc"]["Estándar"]
    print(f"{R['direccion']} · {R['smp']} · {R['barrio']} · {R['normativa']['unidad']}")
    print(f"sup {g['sup']} m² · frente {g['frente']} m · fondo {g['fondo']} m · esquina {g['esquina']} · ancho mz {g['ancho_mz']} · LFI {g['lfi']} · huella {g['huella']} m²")
    print(f"cub {m['cub_total']:.0f} · vend {m['vend_cub']:.0f} · exp {m['exp_total']:.0f} · plusvalía USD {m['plusv_usd']:.0f}")
    print(f"residual 22% USD {E['terreno_residual']:.0f} · 15% USD {E['residual_m15']:.0f} · publicación USD {m['vml_pub']:.0f} · viable {R['viable']}")
    print("englobamiento:", [(o['con'][0]['direccion'], round(o['ganancia_pct'] * 100, 1), o['recomendado']) for o in R['englobamiento']['opciones']])
    print("uso actual:", R["uso_actual"]["rango"])
