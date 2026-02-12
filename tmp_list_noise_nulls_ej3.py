from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
SELECT
  t.turno_pk, t.conversacion_pk, t.turno_idx,
  LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n', ' '), '\\r', ' '), 200) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND (t.fase IS NULL OR LENGTH(TRIM(t.fase))=0)
  AND t.fase_source=%s
ORDER BY t.conversacion_pk, t.turno_idx
"""

cur.execute(sql, (ej, "NOISE"))
rows = cur.fetchall()
print("ejecucion_id=", ej)
print("rows=", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
