from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Cuenta transiciones donde el orden de fase baja (ej: NEGOCIACIÓN -> INFORMACIÓN_DEUDA)
# Ajustá los nombres si tu taxonomía difiere.
sql = """
WITH fase_orden AS (
  SELECT 'APERTURA' fase, 1 ord UNION ALL
  SELECT 'IDENTIFICACIÓN', 2 UNION ALL
  SELECT 'INFORMACIÓN_DEUDA', 3 UNION ALL
  SELECT 'NEGOCIACIÓN', 4 UNION ALL
  SELECT 'CONSULTA_ACEPTACIÓN', 5 UNION ALL
  SELECT 'FORMALIZACIÓN_PAGO', 6 UNION ALL
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
SELECT
  COUNT(*) AS violaciones,
  SUM(CASE WHEN prev_fase IS NULL OR TRIM(prev_fase)='' THEN 0 ELSE 1 END) AS transiciones_con_prev
FROM t
JOIN fase_orden fo_cur ON fo_cur.fase = t.fase
JOIN fase_orden fo_prev ON fo_prev.fase = t.prev_fase
WHERE fo_cur.ord < fo_prev.ord
"""

cur.execute(sql, (ej,))
violaciones, trans_con_prev = cur.fetchone()

print(f"ejecucion_id={ej}")
print(f"violaciones_baja_orden={violaciones}")
print(f"transiciones_evaluadas={trans_con_prev}")

cur.close()
conn.close()
