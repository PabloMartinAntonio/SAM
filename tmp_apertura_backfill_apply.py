from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
JOIN sa_turnos n
  ON n.conversacion_pk=t.conversacion_pk AND n.turno_idx=t.turno_idx+1
JOIN (
  SELECT
    a.conversacion_pk,
    a.turno_idx,
    (
      SELECT t2.fase
      FROM sa_turnos t2
      WHERE t2.conversacion_pk=a.conversacion_pk
        AND t2.turno_idx < a.turno_idx
        AND t2.fase IS NOT NULL AND TRIM(t2.fase)<>'' AND t2.fase <> 'APERTURA'
      ORDER BY t2.turno_idx DESC
      LIMIT 1
    ) AS back_fase
  FROM sa_turnos a
  JOIN sa_conversaciones c2 ON c2.conversacion_pk=a.conversacion_pk
  WHERE c2.ejecucion_id=%s
    AND a.fase='APERTURA'
) x ON x.conversacion_pk=t.conversacion_pk AND x.turno_idx=t.turno_idx
SET
  t.fase = x.back_fase,
  t.fase_source = 'AP_BK'
WHERE c.ejecucion_id=%s
  AND t.fase='APERTURA'
  AND x.back_fase IS NOT NULL AND TRIM(x.back_fase)<>'' AND x.back_fase <> 'APERTURA'
"""
cur.execute(sql, (ej, ej))
updated = cur.rowcount
conn.commit()

print(f"ejecucion_id={ej}")
print(f"updated_apertura_backfill_when_has_next={updated}")

cur.close()
conn.close()
