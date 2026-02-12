import os, csv
from sa_core.config import load_config
from sa_core.db import get_conn

ej=3
out_path = os.path.join("out_reports", f"ej{ej}_postprocess_final_summary.csv")
os.makedirs("out_reports", exist_ok=True)

cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

# 1) distribución fase (11)
cur.execute("""
SELECT t.fase, COUNT(*) n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase
ORDER BY n DESC
""",(ej,))
fase_rows = cur.fetchall()

# 2) distribución fase_8 (8)
cur.execute("""
SELECT t.fase_8, COUNT(*) n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_8
ORDER BY n DESC
""",(ej,))
fase8_rows = cur.fetchall()

# 3) fase_source
cur.execute("""
SELECT t.fase_source, COUNT(*) n,
       SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_source
ORDER BY n DESC
""",(ej,))
src_rows = cur.fetchall()

# 4) métricas globales
cur.execute("""
SELECT
  COUNT(*) total_turnos,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) fase_null,
  SUM(CASE WHEN t.fase_source='NOISE' THEN 1 ELSE 0 END) noise_rows,
  SUM(CASE WHEN t.fase_8 IS NULL OR TRIM(t.fase_8)='' THEN 1 ELSE 0 END) fase8_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
total_turnos, fase_null, noise_rows, fase8_null = cur.fetchone()

cur.close(); conn.close()

# Escribir CSV tipo "secciones"
with open(out_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ejecucion_id", ej])
    w.writerow([])
    w.writerow(["METRICAS", "valor"])
    w.writerow(["total_turnos", total_turnos])
    w.writerow(["fase_null", fase_null])
    w.writerow(["noise_rows", noise_rows])
    w.writerow(["fase8_null", fase8_null])
    w.writerow([])
    w.writerow(["DISTRIBUCION_FASE_11", "n"])
    for fase, n in fase_rows:
        w.writerow([fase if fase is not None else "NULL", n])
    w.writerow([])
    w.writerow(["DISTRIBUCION_FASE_8", "n"])
    for fase8, n in fase8_rows:
        w.writerow([fase8 if fase8 is not None else "NULL", n])
    w.writerow([])
    w.writerow(["DISTRIBUCION_FASE_SOURCE", "n", "fase_null"])
    for fs, n, fn in src_rows:
        w.writerow([fs if fs is not None else "NULL", n, fn])

print(f"[OK] wrote: {out_path}")
