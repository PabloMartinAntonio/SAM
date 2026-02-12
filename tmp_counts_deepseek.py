from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT COUNT(*)
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
WHERE c.ejecucion_id = %s AND t.fase_source = 'DEEPSEEK'
""", (ej,))
print("deepseek_turnos=", cur.fetchone()[0])

cur.execute("""
SELECT COUNT(*)
FROM sa_conversaciones
WHERE ejecucion_id=%s AND llm_usado=1
""", (ej,))
print("llm_usado_convs=", cur.fetchone()[0])

cur.close()
conn.close()
