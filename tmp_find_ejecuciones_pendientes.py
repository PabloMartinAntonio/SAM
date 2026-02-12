from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  c.ejecucion_id,
  COUNT(*) AS total_turnos,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS fase_null,
  SUM(CASE WHEN t.fase_source='DEEPSEEK_LOW' THEN 1 ELSE 0 END) AS deepseek_low
FROM sa_conversaciones c
JOIN sa_turnos t ON t.conversacion_pk=c.conversacion_pk
GROUP BY c.ejecucion_id
HAVING fase_null > 0 OR deepseek_low > 0
ORDER BY (fase_null + deepseek_low) DESC
LIMIT 15
""")

rows = cur.fetchall()
print("ejecucion_id".ljust(12), "total".rjust(10), "fase_null".rjust(10), "deepseek_low".rjust(14), "pendientes".rjust(12))
print("-"*62)
for ej, total, fn, dl in rows:
    pend = int(fn or 0) + int(dl or 0)
    print(str(ej).ljust(12), str(total).rjust(10), str(fn).rjust(10), str(dl).rjust(14), str(pend).rjust(12))

cur.close()
conn.close()
