"""Divide fmv_parcelas.sqlite en 15 bases por comuna (comuna_01.sqlite ... comuna_15.sqlite) + gzip."""
import sqlite3, os, gzip, shutil
SRC = "/home/claude/gcba/fmv_parcelas.sqlite"; OUTD = "/home/claude/gcba/datos"; os.makedirs(OUTD, exist_ok=True)
src = sqlite3.connect(SRC)
schema = [r[0] for r in src.execute("select sql from sqlite_master where type='table' and name!='meta'")]
for c in range(1, 16):
    out = f"{OUTD}/comuna_{c:02d}.sqlite"
    if os.path.exists(out): os.remove(out)
    con = sqlite3.connect(out); cur = con.cursor()
    for s in schema: cur.execute(s)
    cur.execute("CREATE TABLE meta(k TEXT, v TEXT)")
    cur.execute(f"ATTACH '{SRC}' AS s")
    cur.execute("CREATE TEMP TABLE sel AS SELECT smp FROM s.parcelas WHERE comuna=? UNION SELECT smp FROM s.cu WHERE comuna=?", (f"Comuna {c}", f"Comuna {c}"))
    for t in ["parcelas", "cu", "rus", "frentes", "obras", "aph", "cur3d"]:
        cur.execute(f"INSERT INTO {t} SELECT * FROM s.{t} WHERE smp IN (SELECT smp FROM sel)")
    cur.execute("INSERT INTO meta SELECT * FROM s.meta"); cur.execute("INSERT INTO meta VALUES ('comuna', ?)", (str(c),))
    con.commit(); cur.execute("DETACH s")
    cur.executescript("CREATE INDEX ix_p_sm ON parcelas(sm); CREATE INDEX ix_rus ON rus(smp); CREATE INDEX ix_fr ON frentes(smp); CREATE INDEX ix_fr_calle ON frentes(calle); CREATE INDEX ix_ob ON obras(smp); CREATE INDEX ix_aph ON aph(smp); CREATE INDEX ix_c3 ON cur3d(smp);")
    con.commit(); con.execute("VACUUM"); n = con.execute("select count(*) from parcelas").fetchone()[0]; con.close()
    with open(out, "rb") as f, gzip.open(out + ".gz", "wb", compresslevel=9) as g: shutil.copyfileobj(f, g)
    print(c, n, round(os.path.getsize(out) / 1e6, 1), "MB  gz", round(os.path.getsize(out + ".gz") / 1e6, 1))
