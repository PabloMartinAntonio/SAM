from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
JOIN sa_turnos p
  ON p.conversacion_pk=t.conversacion_pk AND p.turno_idx=t.turno_idx-1
JOIN sa_turnos n
  ON n.conversacion_pk=t.conversacion_pk AND n.turno_idx=t.turno_idx+1
SET
  t.fase = p.fase,
  t.fase_source = 'CI_IMP'
WHERE c.ejecucion_id=%s
  AND t.fase='CIERRE'
  AND t.turno_idx > 1
  AND p.fase IS NOT NULL AND TRIM(p.fase)<>'' AND p.fase <> 'CIERRE'
"""
cur.execute(sql, (ej,))
updated = cur.rowcount
conn.commit()

print(f"ejecucion_id={ej}")
print(f"updated_cierre_with_next_turn={updated}")

cur.close()
conn.close()
