"""Construye la base compacta fmv_parcelas.sqlite a partir de los CSV del GCBA."""
import sqlite3, json, os, time
import pandas as pd, numpy as np
from shapely import wkt
from shapely.ops import transform
import pyproj
D = "/mnt/user-data/uploads/Downloads/"
OUT = "/home/claude/gcba/fmv_parcelas.sqlite"
if os.path.exists(OUT): os.remove(OUT)
con = sqlite3.connect(OUT); cur = con.cursor()
cur.executescript("""
CREATE TABLE parcelas(smp TEXT PRIMARY KEY, sm TEXT, seccion TEXT, manzana TEXT, parcela TEXT, partida TEXT, barrio TEXT, comuna TEXT, area REAL, geom TEXT);
CREATE TABLE cu(smp TEXT PRIMARY KEY, uni_edif_1 REAL, uni_edif_2 REAL, uso_1 INTEGER, dist_1_grp TEXT, dist_1_esp TEXT, dist_2_grp TEXT, catalogado INTEGER, tipo_mza TEXT, rivolta INTEGER, plano_l REAL, lep INTEGER, ensanche INTEGER, rh INTEGER, anac INTEGER, dist_cpu_1 TEXT, fot_em_1 REAL, alicuota REAL, inc_uva_21 REAL, adps TEXT, barrio TEXT, comuna TEXT);
CREATE TABLE rus(smp TEXT, tipo1 TEXT, tipo2 TEXT, estado TEXT, pisos INTEGER, calle TEXT, puerta TEXT, anio TEXT);
CREATE TABLE frentes(smp TEXT, calle TEXT, num_dom TEXT, parc_esq TEXT, ochava TEXT);
CREATE TABLE obras(smp TEXT, fecha TEXT, expediente TEXT, ubicacion TEXT, descripcio TEXT);
CREATE TABLE aph(smp TEXT, direccion TEXT, denominacion TEXT, catalogacion TEXT, proteccion TEXT, estado TEXT);
CREATE TABLE cur3d(smp TEXT, tipo TEXT, h_ini REAL, h_fin REAL, edif TEXT);
CREATE TABLE meta(k TEXT, v TEXT);
""")
t0 = time.time()
proj = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:5347", always_xy=True).transform
n = 0
for ch in pd.read_csv(D + "parcelas_catastrales.csv", dtype=str, chunksize=50000):
    rows = []
    for r in ch.itertuples():
        try:
            g = transform(proj, wkt.loads(r.geometry))
        except Exception:
            continue
        if g.geom_type == "MultiPolygon": g = max(g.geoms, key=lambda p: p.area)
        g = g.simplify(0.05, preserve_topology=True)
        coords = [[round(x, 1), round(y, 1)] for x, y in g.exterior.coords]
        smp = r.smp.replace(" ", "")
        rows.append((smp, smp[:7], r.seccion, r.manzana, r.parcela, r.partida_ma, r.barrio, r.comuna, round(g.area, 1), json.dumps(coords, separators=(",", ":"))))
    cur.executemany("INSERT OR REPLACE INTO parcelas VALUES (?,?,?,?,?,?,?,?,?,?)", rows); con.commit(); n += len(rows); print("parcelas", n, round(time.time() - t0))
cu = pd.read_csv(D + "codigo-urbanistico.csv", dtype=str, low_memory=False)
def f(x):
    try: return float(x)
    except: return None
def i(x):
    try: return int(float(x))
    except: return None
cur.executemany("INSERT OR REPLACE INTO cu VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(r.smp, f(r.uni_edif_1), f(r.uni_edif_2), i(r.uso_1), r.dist_1_grp if isinstance(r.dist_1_grp, str) else None, r.dist_1_esp if isinstance(r.dist_1_esp, str) else None,
                  r.dist_2_grp if isinstance(r.dist_2_grp, str) else None, i(r.catalogado), r.tipo_mza, i(r.rivolta), f(r.plano_l), i(r.lep), i(r.ensanche), i(r.rh), i(r.anac),
                  r.dist_cpu_1 if isinstance(r.dist_cpu_1, str) else None, f(r.fot_em_1), f(r.alicuota), f(r.inc_uva_21), r.adps if isinstance(r.adps, str) else None, r.barrio, r.comuna) for r in cu.itertuples()])
con.commit(); print("cu", len(cu))
rus = pd.read_csv(D + "relevamiento-usos-del-suelo-2022-2024.csv", dtype=str, low_memory=False)
cur.executemany("INSERT INTO rus VALUES (?,?,?,?,?,?,?,?)", [(r.SMP, r.TIPO1, r.TIPO2 if isinstance(r.TIPO2, str) else None, r.ESTADO, i(r.PISOS), r.CALLE, r.PUERTA, r[-1]) for r in rus.itertuples()])
con.commit(); print("rus", len(rus))
fr = pd.read_csv(D + "frentes-parcelas.csv", dtype=str, low_memory=False)
cur.executemany("INSERT INTO frentes VALUES (?,?,?,?,?)", [(r.smp, r.frente, r.num_dom, r.parc_esq, r.ochava) for r in fr.itertuples() if isinstance(r.frente, str)])
con.commit(); print("frentes", len(fr))
ob = pd.read_csv(D + "obrasregistradas-acumulado.csv", dtype=str, low_memory=False)
cur.executemany("INSERT INTO obras VALUES (?,?,?,?,?)", [(r.smp, r.fecha, r.expediente, r.ubicacion, r.descripcio) for r in ob.itertuples() if isinstance(r.smp, str)])
con.commit(); print("obras", len(ob))
aph = pd.read_csv(D + "areas-de-proteccion-historica.csv", dtype=str, low_memory=False)
cur.executemany("INSERT INTO aph VALUES (?,?,?,?,?,?)", [(r.SMP, r[7], r.DENOMINACI if isinstance(r.DENOMINACI, str) else None, r.CATALOGACI if isinstance(r.CATALOGACI, str) else None, r.PROTECCION, r.ESTADO) for r in aph.itertuples() if isinstance(r.SMP, str)])
con.commit(); print("aph", len(aph))
k = 0
for ch in pd.read_csv(D + "superficie_edificable.csv", dtype=str, chunksize=200000):
    ch = ch.drop_duplicates(["smp", "tipo", "altura_ini"])
    cur.executemany("INSERT INTO cur3d VALUES (?,?,?,?,?)", [(r.smp, r.tipo, f(r.altura_ini), f(r.altura_fin), r.edificabil) for r in ch.itertuples()]); k += len(ch)
con.commit(); print("cur3d", k)
cur.executescript("CREATE INDEX ix_p_sm ON parcelas(sm); CREATE INDEX ix_rus ON rus(smp); CREATE INDEX ix_fr ON frentes(smp); CREATE INDEX ix_fr_calle ON frentes(calle); CREATE INDEX ix_ob ON obras(smp); CREATE INDEX ix_aph ON aph(smp); CREATE INDEX ix_c3 ON cur3d(smp);")
cur.executemany("INSERT INTO meta VALUES (?,?)", [("fuente", "data.buenosaires.gob.ar: parcelas jul-2026, codigo urbanistico (norma 31/12/2024) jun-2026, RUS 2022-2024, obras registradas jul-2026, APH jun-2026, CUR3D nov-2024"), ("crs", "EPSG:5347 (POSGAR 2007 faja 5), coordenadas en metros"), ("generado", "2026-10-03")])
con.commit(); con.execute("VACUUM"); con.close()
print("size MB", round(os.path.getsize(OUT) / 1e6, 1), "t", round(time.time() - t0))
