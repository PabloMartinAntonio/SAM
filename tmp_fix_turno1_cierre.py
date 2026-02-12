from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
UPDATE sa_turnos t1
JOIN sa_conversaciones c ON c.conversacion_pk=t1.conversacion_pk
JOIN sa_turnos t2 ON t2.conversacion_pk=t1.conversacion_pk AND t2.turno_idx=2
SET
  t1.fase = t2.fase,
  t1.fase_source = 'CI_FIX1'
WHERE c.ejecucion_id=%s
  AND t1.turno_idx=1
  AND t1.fase='CIERRE'
  AND t2.fase IS NOT NULL AND TRIM(t2.fase)<>'' 
"""
cur.execute(sql, (ej,))
updated = cur.rowcount
conn.commit()

print(f"ejecucion_id={ej}")
print(f"updated_turno1_cierre_to_turno2_fase={updated}")

cur.close()
conn.close()
