from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  SUM(CASE WHEN (t.fase IS NULL OR LENGTH(TRIM(t.fase))=0) THEN 1 ELSE 0 END) AS null_total,
  SUM(CASE WHEN (t.fase IS NULL OR LENGTH(TRIM(t.fase))=0) AND t.fase_source='NOISE' THEN 1 ELSE 0 END) AS null_noise,
  SUM(CASE WHEN (t.fase IS NULL OR LENGTH(TRIM(t.fase))=0) AND (t.fase_source IS NULL OR t.fase_source<>'NOISE') THEN 1 ELSE 0 END) AS null_no_noise
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
print("ejecucion_id=", ej)
print("null_total, null_noise, null_no_noise =", cur.fetchone())

cur.close()
conn.close()
