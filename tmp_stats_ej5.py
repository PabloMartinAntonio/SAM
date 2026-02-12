from sa_core.config import load_config
from sa_core.db import get_conn

ej=5
cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

cur.execute("""
SELECT COUNT(*) total,
       SUM(CASE WHEN t.fase_source IS NULL OR TRIM(t.fase_source)='' THEN 1 ELSE 0 END) src_null,
       SUM(CASE WHEN t.fase_source='NO_IMP' THEN 1 ELSE 0 END) no_imp,
       SUM(CASE WHEN t.fase_source='DEEPSEEK' THEN 1 ELSE 0 END) deepseek,
       SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
print("ejecucion_id=",ej,"stats=",cur.fetchone())

cur.execute("""
SELECT t.fase_source, COUNT(*) n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_source
ORDER BY n DESC
""",(ej,))
print("\nby_source:")
for r in cur.fetchall(): print(r)

cur.close(); conn.close()
