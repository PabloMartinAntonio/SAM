from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

print("=== ejecucion_id =", ej, "===")

print("\n-- fases (count) --")
cur.execute("""
SELECT t.fase, COUNT(*) n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase
ORDER BY n DESC
""", (ej,))
for r in cur.fetchall():
    print(r)

print("\n-- fase_source (count) --")
cur.execute("""
SELECT t.fase_source, COUNT(*) n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_source
ORDER BY n DESC
""", (ej,))
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
