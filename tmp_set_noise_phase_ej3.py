from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Actualiza SOLO fase NULL con fase_source=NOISE dentro de la ejecución
sql = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
SET t.fase=%s
WHERE c.ejecucion_id=%s
  AND (t.fase IS NULL OR LENGTH(TRIM(t.fase))=0)
  AND t.fase_source=%s
"""
cur.execute(sql, ("NOISE", ej, "NOISE"))
conn.commit()
print("[OK] rows_affected=", cur.rowcount)

# Verificación: ya no debe quedar fase NULL
cur.execute("""
SELECT
  SUM(CASE WHEN (t.fase IS NULL OR LENGTH(TRIM(t.fase))=0) THEN 1 ELSE 0 END) AS null_total
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
print("[CHECK] null_total=", cur.fetchone()[0])

# Listar los 4 turnos
cur.execute("""
SELECT t.turno_pk, t.conversacion_pk, t.turno_idx, t.fase, t.fase_source,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 80) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase='NOISE' AND t.fase_source='NOISE'
ORDER BY t.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()
print("[NOISE rows] =", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
