import os, csv
from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
out_dir = "out_reports"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, f"ej{ej}_postprocess_final_summary.csv")

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# fase_source stats
cur.execute("""
SELECT
  COALESCE(t.fase_source,'NULL') AS fase_source,
  COUNT(*) AS n,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_source
ORDER BY n DESC
""", (ej,))
rows = cur.fetchall()

# noise / null audit
cur.execute("""
SELECT
  SUM(CASE WHEN t.fase_source='NOISE' THEN 1 ELSE 0 END) AS noise_total,
  SUM(CASE WHEN t.fase_source='NOISE' AND (t.fase IS NULL OR TRIM(t.fase)='') THEN 1 ELSE 0 END) AS noise_fase_null,
  SUM(CASE WHEN (t.fase IS NULL OR TRIM(t.fase)='') THEN 1 ELSE 0 END) AS fase_null_total,
  SUM(CASE WHEN (t.fase_8 IS NULL OR TRIM(t.fase_8)='') THEN 1 ELSE 0 END) AS fase8_null_total
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
noise_total, noise_fase_null, fase_null_total, fase8_null_total = cur.fetchone()

# violaciones finales (con excepciones permitidas)
cur.execute("""
WITH fase_orden AS (
  SELECT 'APERTURA' fase, 1 ord UNION ALL
  SELECT 'IDENTIFICACIÓN', 2 UNION ALL
  SELECT 'IDENTIFICACION', 2 UNION ALL
  SELECT 'INFORMACIÓN_DEUDA', 3 UNION ALL
  SELECT 'INFORMACION_DEUDA', 3 UNION ALL
  SELECT 'NEGOCIACIÓN', 4 UNION ALL
  SELECT 'NEGOCIACION', 4 UNION ALL
  SELECT 'CONSULTA_ACEPTACIÓN', 5 UNION ALL
  SELECT 'CONSULTA_ACEPTACION', 5 UNION ALL
  SELECT 'FORMALIZACIÓN_PAGO', 6 UNION ALL
  SELECT 'FORMALIZACION_PAGO', 6 UNION ALL
  SELECT 'ADVERTENCIAS', 7 UNION ALL
  SELECT 'CIERRE', 8
),
t AS (
  SELECT
    t.conversacion_pk,
    t.turno_idx,
    t.fase,
    LAG(t.fase) OVER (PARTITION BY t.conversacion_pk ORDER BY t.turno_idx) AS prev_fase
  FROM sa_turnos t
  JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
  WHERE c.ejecucion_id=%s
    AND t.fase IS NOT NULL AND TRIM(t.fase) <> ''
)
SELECT COUNT(*)
FROM t
JOIN fase_orden fo_cur ON fo_cur.fase = t.fase
JOIN fase_orden fo_prev ON fo_prev.fase = t.prev_fase
WHERE fo_cur.ord < fo_prev.ord
  AND NOT (
    (t.prev_fase IN ('FORMALIZACION_PAGO','FORMALIZACIÓN_PAGO') AND t.fase IN ('CONSULTA_ACEPTACION','CONSULTA_ACEPTACIÓN'))
    OR
    (t.prev_fase='ADVERTENCIAS' AND t.fase IN ('CONSULTA_ACEPTACION','CONSULTA_ACEPTACIÓN'))
    OR
    (t.prev_fase='ADVERTENCIAS' AND t.fase IN ('FORMALIZACION_PAGO','FORMALIZACIÓN_PAGO'))
  )
""", (ej,))
viol = cur.fetchone()[0]

cur.close()
conn.close()

with open(out_path, "w", newline="", encoding="utf-8") as f:
  w = csv.writer(f)
  w.writerow(["ejecucion_id", ej])
  w.writerow(["noise_total", noise_total])
  w.writerow(["noise_fase_null", noise_fase_null])
  w.writerow(["fase_null_total", fase_null_total])
  w.writerow(["fase8_null_total", fase8_null_total])
  w.writerow(["violaciones_finales", viol])
  w.writerow([])
  w.writerow(["fase_source", "n", "fase_null"])
  for fs, n, fn in rows:
    w.writerow([fs, n, fn])

print("[OK] wrote:", out_path)
