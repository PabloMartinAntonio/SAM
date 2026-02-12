from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
SELECT
  COALESCE(t.fase_source,'NULL') AS fase_source,
  COUNT(*) AS n,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_source
ORDER BY n DESC
"""

cur.execute(sql, (ej,))
rows = cur.fetchall()

print("fase_source".ljust(20), "n".rjust(10), "fase_null".rjust(10))
print("-"*44)
for fs, n, fn in rows:
    print(str(fs).ljust(20), str(n).rjust(10), str(fn).rjust(10))

cur.close()
conn.close()
