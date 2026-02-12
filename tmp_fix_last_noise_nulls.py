from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# 1) backfill hacia atrás (fase válida más cercana)
sql_back = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
JOIN (
  SELECT
    a.turno_pk,
    (
      SELECT t2.fase
      FROM sa_turnos t2
      WHERE t2.conversacion_pk=a.conversacion_pk
        AND t2.turno_idx < a.turno_idx
        AND t2.fase IS NOT NULL AND TRIM(t2.fase)<>'' 
      ORDER BY t2.turno_idx DESC
      LIMIT 1
    ) AS bf
  FROM sa_turnos a
  JOIN sa_conversaciones c2 ON c2.conversacion_pk=a.conversacion_pk
  WHERE c2.ejecucion_id=%s
    AND a.fase_source='NOISE'
    AND (a.fase IS NULL OR TRIM(a.fase)='')
) x ON x.turno_pk=t.turno_pk
SET t.fase = x.bf,
    t.fase_source = 'NO_IMP'
WHERE c.ejecucion_id=%s
  AND t.fase_source='NOISE'
  AND (t.fase IS NULL OR TRIM(t.fase)='')
  AND x.bf IS NOT NULL AND TRIM(x.bf)<>'' 
"""
cur.execute(sql_back, (ej, ej))
upd_back = cur.rowcount or 0

# 2) si siguen vacíos, buscar hacia adelante (fase válida más cercana)
sql_fwd = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
JOIN (
  SELECT
    a.turno_pk,
    (
      SELECT t2.fase
      FROM sa_turnos t2
      WHERE t2.conversacion_pk=a.conversacion_pk
        AND t2.turno_idx > a.turno_idx
        AND t2.fase IS NOT NULL AND TRIM(t2.fase)<>'' 
      ORDER BY t2.turno_idx ASC
      LIMIT 1
    ) AS ff
  FROM sa_turnos a
  JOIN sa_conversaciones c2 ON c2.conversacion_pk=a.conversacion_pk
  WHERE c2.ejecucion_id=%s
    AND a.fase_source='NOISE'
    AND (a.fase IS NULL OR TRIM(a.fase)='')
) x ON x.turno_pk=t.turno_pk
SET t.fase = x.ff,
    t.fase_source = 'NO_IMP'
WHERE c.ejecucion_id=%s
  AND t.fase_source='NOISE'
  AND (t.fase IS NULL OR TRIM(t.fase)='')
  AND x.ff IS NOT NULL AND TRIM(x.ff)<>'' 
"""
cur.execute(sql_fwd, (ej, ej))
upd_fwd = cur.rowcount or 0

# 3) fallback: set fase='NOISE' para que no queden NULL
sql_fallback = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
SET t.fase = 'NOISE'
WHERE c.ejecucion_id=%s
  AND t.fase_source='NOISE'
  AND (t.fase IS NULL OR TRIM(t.fase)='')
"""
cur.execute(sql_fallback, (ej,))
upd_fb = cur.rowcount or 0

conn.commit()

print(f"ejecucion_id={ej}")
print(f"updated_backfill_prev={upd_back}")
print(f"updated_backfill_next={upd_fwd}")
print(f"updated_fallback_set_fase_NOISE={upd_fb}")

cur.close()
conn.close()
