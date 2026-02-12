from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Cuántos NOISE con fase vacía tienen fase en prev o next (potencialmente imputables)
cur.execute("""
SELECT
  SUM(CASE WHEN prev_fase IS NOT NULL AND TRIM(prev_fase)<>'' THEN 1 ELSE 0 END) AS can_from_prev,
  SUM(CASE WHEN (prev_fase IS NULL OR TRIM(prev_fase)='') AND next_fase IS NOT NULL AND TRIM(next_fase)<>'' THEN 1 ELSE 0 END) AS can_from_next,
  COUNT(*) AS noise_null_total
FROM (
  SELECT
    t.conversacion_pk,
    t.turno_idx,
    t.fase AS cur_fase,
    (SELECT t2.fase
     FROM sa_turnos t2
     WHERE t2.conversacion_pk=t.conversacion_pk AND t2.turno_idx=t.turno_idx-1
     LIMIT 1) AS prev_fase,
    (SELECT t3.fase
     FROM sa_turnos t3
     WHERE t3.conversacion_pk=t.conversacion_pk AND t3.turno_idx=t.turno_idx+1
     LIMIT 1) AS next_fase
  FROM sa_turnos t
  JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
  WHERE c.ejecucion_id=%s
    AND t.fase_source='NOISE'
    AND (t.fase IS NULL OR TRIM(t.fase)='')
) x
""", (ej,))

can_prev, can_next, total = cur.fetchone()
print(f"ejecucion_id={ej}")
print(f"noise_null_total={total}")
print(f"imputable_from_prev={can_prev}")
print(f"imputable_from_next_only={can_next}")
print(f"imputable_total={can_prev + can_next}")

cur.close()
conn.close()
