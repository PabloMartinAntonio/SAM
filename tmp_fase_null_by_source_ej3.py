from sa_core.config import load_config
from sa_core.db import get_conn

ej=3
cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

cur.execute("""
SELECT
  COALESCE(t.fase_source,'NULL') as fase_source,
  COUNT(*) as n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND (t.fase IS NULL OR TRIM(t.fase)='')
GROUP BY COALESCE(t.fase_source,'NULL')
ORDER BY n DESC
""",(ej,))
rows=cur.fetchall()

print(f"ejecucion_id={ej} fase_null_by_source:")
for fs,n in rows:
    print(f" - {fs}: {n}")

cur.close(); conn.close()
