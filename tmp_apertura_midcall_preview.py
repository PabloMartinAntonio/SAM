from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
WITH t AS (
  SELECT
    t.conversacion_pk,
    t.turno_idx,
    t.fase,
    LAG(t.fase) OVER (PARTITION BY t.conversacion_pk ORDER BY t.turno_idx) AS prev_fase
  FROM sa_turnos t
  JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
  WHERE c.ejecucion_id=%s
    AND t.fase IS NOT NULL AND TRIM(t.fase) <> ''
)
SELECT
  prev_fase,
  COUNT(*) AS n
FROM t
WHERE fase='APERTURA'
  AND turno_idx > 2
  AND prev_fase IS NOT NULL
  AND prev_fase <> 'APERTURA'
GROUP BY prev_fase
ORDER BY n DESC
"""
cur.execute(sql, (ej,))
rows = cur.fetchall()

total = sum(r[1] for r in rows)
print(f"ejecucion_id={ej}")
print(f"apertura_midcall_total={total}")
print("prev_fase".ljust(24), "n".rjust(8))
print("-"*36)
for prev_f, n in rows:
    print(str(prev_f).ljust(24), str(n).rjust(8))

cur.close()
conn.close()
