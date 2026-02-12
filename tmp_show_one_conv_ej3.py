from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# 1) Elegir una conversacion con muchos turnos DEEPSEEK
cur.execute("""
SELECT c.conversacion_pk, COALESCE(c.conversacion_id, CAST(c.conversacion_pk AS CHAR)) AS conversation_id,
       SUM(CASE WHEN t.fase_source='DEEPSEEK' THEN 1 ELSE 0 END) AS deepseek_turnos,
       COUNT(*) AS total_turnos
FROM sa_conversaciones c
JOIN sa_turnos t ON t.conversacion_pk=c.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY c.conversacion_pk, conversation_id
ORDER BY deepseek_turnos DESC, total_turnos DESC
LIMIT 1
""", (ej,))
row = cur.fetchone()
print("picked_conv=", row)

conv_pk = row[0]

# 2) Listar todos los turnos
cur.execute("""
SELECT t.turno_idx, t.hablante, t.fase, t.fase_source, t.intent,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 200) AS txt
FROM sa_turnos t
WHERE t.conversacion_pk=%s
ORDER BY t.turno_idx
""", (conv_pk,))
rows = cur.fetchall()
print("turnos=", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
