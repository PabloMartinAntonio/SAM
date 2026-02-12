import csv
from sa_core.config import load_config
from sa_core.db import get_conn

p = r"out_reports\run_3_pendientes_llm.csv"
ids = [int(r["turno_pk"]) for r in csv.DictReader(open(p, encoding="utf-8"))]
print("csv_rows=", len(ids))

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# traer estado actual en DB
placeholders = ",".join(["%s"]*len(ids))
sql = f"""
SELECT t.turno_pk, t.conversacion_pk, t.turno_idx,
       t.fase, t.fase_source, t.fase_conf,
       CHAR_LENGTH(t.text) AS text_len,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 120) AS txt
FROM sa_turnos t
WHERE t.turno_pk IN ({placeholders})
ORDER BY t.conversacion_pk, t.turno_idx
"""
cur.execute(sql, ids)
rows = cur.fetchall()
print("db_rows=", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
