from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  SUM(CASE WHEN t.fase_8 IS NOT NULL AND t.fase IS NOT NULL AND t.fase <> t.fase_8 THEN 1 ELSE 0 END) AS distintos,
  COUNT(*) AS total
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
distintos, total = cur.fetchone()
print(f"ejecucion_id={ej} distintos_fase_vs_fase8={distintos} total={total}")

cur.execute("""
SELECT t.fase, t.fase_8, COUNT(*) AS n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase, t.fase_8
ORDER BY n DESC
LIMIT 50
""", (ej,))
rows = cur.fetchall()

print("fase".ljust(24), "fase_8".ljust(24), "n".rjust(10))
print("-"*62)
for f, f8, n in rows:
    print(str(f).ljust(24), str(f8).ljust(24), str(n).rjust(10))

cur.close()
conn.close()
