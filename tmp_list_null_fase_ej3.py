from sa_core.config import load_config
from sa_core.db import get_conn

ej=3
cfg=load_config("config.ini")
conn=get_conn(cfg)
cur=conn.cursor()

cur.execute("""
SELECT c.conversacion_pk,
       COALESCE(c.conversacion_id, CAST(c.conversacion_pk AS CHAR)) AS conversation_id,
       t.turno_pk, t.turno_idx, t.speaker, t.fase_source,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 220) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NULL
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))

rows=cur.fetchall()
print("null_fase_rows=", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
