from sa_core.config import load_config
from sa_core.db import get_conn

ej=5
cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

cur.execute("SELECT COUNT(*) FROM sa_conversaciones WHERE ejecucion_id=%s", (ej,))
print("sa_conversaciones_count=", cur.fetchone()[0])

cur.execute("""
SELECT COUNT(*)
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
print("sa_turnos_count=", cur.fetchone()[0])

cur.close(); conn.close()
