from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  COUNT(*) AS total,
  SUM(CASE WHEN fase_8 IS NULL OR TRIM(fase_8)='' THEN 1 ELSE 0 END) AS fase8_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
total, nulls = cur.fetchone()

print(f"ejecucion_id={ej} total_turnos={total} fase8_null={nulls}")

cur.execute("""
SELECT fase_8, COUNT(*) AS n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY fase_8
ORDER BY n DESC
""", (ej,))
rows = cur.fetchall()

print("fase_8".ljust(24), "n".rjust(10))
print("-"*36)
for f8, n in rows:
    print(str(f8).ljust(24), str(n).rjust(10))

cur.close()
conn.close()
