from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# 1) Desde fase anterior (prioridad)
cur.execute("""
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
JOIN sa_turnos p ON p.conversacion_pk=t.conversacion_pk AND p.turno_idx=t.turno_idx-1
SET
  t.fase = p.fase,
  t.fase_source = 'NOISE_IMPUTE'
WHERE c.ejecucion_id=%s
  AND t.fase_source='NOISE'
  AND (t.fase IS NULL OR TRIM(t.fase)='')
  AND p.fase IS NOT NULL AND TRIM(p.fase)<>''
""", (ej,))
upd_prev = cur.rowcount

# 2) Si sigue vacío, desde fase siguiente
cur.execute("""
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
JOIN sa_turnos n ON n.conversacion_pk=t.conversacion_pk AND n.turno_idx=t.turno_idx+1
SET
  t.fase = n.fase,
  t.fase_source = 'NOISE_IMPUTE'
WHERE c.ejecucion_id=%s
  AND t.fase_source='NOISE'
  AND (t.fase IS NULL OR TRIM(t.fase)='')
  AND n.fase IS NOT NULL AND TRIM(n.fase)<>''
""", (ej,))
upd_next = cur.rowcount

conn.commit()

print(f"ejecucion_id={ej}")
print(f"updated_from_prev={upd_prev}")
print(f"updated_from_next={upd_next}")
print(f"updated_total={upd_prev + upd_next}")

cur.close()
conn.close()
