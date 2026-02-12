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
  SUM(CASE WHEN t.fase_source='DEEPSEEK_LOW' THEN 1 ELSE 0 END) deepseek_low
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
total, fn, dl = cur.fetchone()
print(f"ejecucion_id={ej} total_turnos={total} fase_null={fn} deepseek_low={dl}")

cur.close(); conn.close()
