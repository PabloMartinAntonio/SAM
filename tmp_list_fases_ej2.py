from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT t.fase, COUNT(*) AS n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND TRIM(t.fase) <> ''
GROUP BY t.fase
ORDER BY n DESC
""", (ej,))

rows = cur.fetchall()
print(f"ejecucion_id={ej} fases_distintas={len(rows)}")
print("fase".ljust(28), "n".rjust(10))
print("-"*40)
for fase, n in rows:
    print(str(fase).ljust(28), str(n).rjust(10))

cur.close()
conn.close()
