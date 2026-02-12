from sa_core.config import load_config
from sa_core.db import get_conn

ej=3
cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

cur.execute("""
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
SET t.fase='NOISE'
WHERE c.ejecucion_id=%s
  AND t.fase_source='NOISE'
  AND (t.fase IS NULL OR TRIM(t.fase)='')
""", (ej,))
conn.commit()
print("rows_affected=", cur.rowcount)

cur.close()
conn.close()
