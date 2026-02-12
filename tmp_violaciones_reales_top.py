from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
WITH fase_orden AS (
  SELECT 'APERTURA' fase, 1 ord UNION ALL
  SELECT 'IDENTIFICACIÓN', 2 UNION ALL
  SELECT 'INFORMACIÓN_DEUDA', 3 UNION ALL
  SELECT 'NEGOCIACIÓN', 4 UNION ALL
  SELECT 'CONSULTA_ACEPTACIÓN', 5 ord UNION ALL
  SELECT 'CONSULTA_ACEPTACION', 5 ord UNION ALL
  SELECT 'FORMALIZACIÓN_PAGO', 6 ord UNION ALL
  SELECT 'FORMALIZACION_PAGO', 6 ord UNION ALL
  SELECT 'ADVERTENCIAS', 7 ord UNION ALL
  SELECT 'CIERRE', 8 ord
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
SELECT
  t.prev_fase,
  t.fase AS curr_fase,
  COUNT(*) AS n
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
GROUP BY t.prev_fase, t.fase
ORDER BY n DESC
LIMIT 50
"""

cur.execute(sql, (ej,))
rows = cur.fetchall()

print(f"ejecucion_id={ej}  top_violaciones_reales=50 (excepciones aplicadas)")
print("prev_fase".ljust(24), "curr_fase".ljust(24), "n".rjust(8))
print("-"*60)
for prev_f, cur_f, n in rows:
    print(str(prev_f).ljust(24), str(cur_f).ljust(24), str(n).rjust(8))

cur.close()
conn.close()
