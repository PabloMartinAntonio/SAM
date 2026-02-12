from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  t.fase_source,
  COUNT(*) as n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY t.fase_source
ORDER BY n DESC
""", (ej,))
print("ejecucion_id=", ej)
for r in cur.fetchall():
    print(r)

cur.execute("""
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN t.fase_source='DEEPSEEK' THEN 1 ELSE 0 END) as deepseek,
  SUM(CASE WHEN t.fase_source='RULES' THEN 1 ELSE 0 END) as rules,
  SUM(CASE WHEN t.fase_source='NOISE' THEN 1 ELSE 0 END) as noise,
  SUM(CASE WHEN t.fase IS NULL OR LENGTH(TRIM(t.fase))=0 THEN 1 ELSE 0 END) as fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
print("totals=", cur.fetchone())

cur.close()
conn.close()
