from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

ej = 3

sql1 = """
SELECT COALESCE(NULLIF(TRIM(fase_source),''),'(NULL)') AS src, COUNT(*) AS n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND (t.fase IS NULL OR TRIM(t.fase)='')
GROUP BY COALESCE(NULLIF(TRIM(fase_source),''),'(NULL)')
ORDER BY n DESC
"""
cur.execute(sql1, (ej,))
print("ejecucion_id=", ej)
for r in cur.fetchall():
    print(r)

sql2 = """
SELECT COUNT(*)
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND (t.fase IS NULL OR TRIM(t.fase)='')
  AND (t.fase_source IS NULL OR TRIM(t.fase_source)='')
"""
cur.execute(sql2, (ej,))
print("candidatos_SQL_reclasificar_from_db=", cur.fetchone()[0])

cur.close()
conn.close()
