from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
SELECT
  COUNT(*) AS cierre_midcall
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase='CIERRE'
  AND t.turno_idx > 2
  AND t.turno_idx < (
    SELECT MAX(t2.turno_idx)
    FROM sa_turnos t2
    WHERE t2.conversacion_pk=t.conversacion_pk
  )
"""
cur.execute(sql, (ej,))
n = cur.fetchone()[0]

print(f"ejecucion_id={ej}")
print(f"cierre_midcall={n}")

cur.close()
conn.close()
