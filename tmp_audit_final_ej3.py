from sa_core.config import load_config
from sa_core.db import get_conn

ej=3
cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

cur.execute("""
SELECT
  COUNT(*) total,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) fase_null,
  SUM(CASE WHEN t.fase_source='NOISE' THEN 1 ELSE 0 END) noise_rows,
  SUM(CASE WHEN t.fase_8 IS NULL OR TRIM(t.fase_8)='' THEN 1 ELSE 0 END) fase8_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
total, fn, noise, f8n = cur.fetchone()
print(f"ejecucion_id={ej} total={total} fase_null={fn} noise_rows={noise} fase8_null={f8n}")

cur.close(); conn.close()
