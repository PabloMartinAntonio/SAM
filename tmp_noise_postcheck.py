from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  COUNT(*) AS noise_total,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS noise_fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='NOISE'
""", (ej,))
noise_total, noise_null = cur.fetchone()

cur.execute("""
SELECT COUNT(DISTINCT t.conversacion_pk)
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='NOISE'
""", (ej,))
convs_noise = cur.fetchone()[0]

cur.execute("""
SELECT
  COUNT(*) AS noise_impute_total,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS noise_impute_fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='NOISE_IMPUTE'
""", (ej,))
impute_total, impute_null = cur.fetchone()

print(f"ejecucion_id={ej}")
print(f"NOISE: total={noise_total}  fase_null={noise_null}  convs_con_noise={convs_noise}")
print(f"NOISE_IMPUTE: total={impute_total}  fase_null={impute_null}")

cur.close()
conn.close()
