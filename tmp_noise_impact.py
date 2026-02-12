from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# NOISE: total y fase vacía
cur.execute("""
SELECT
  COUNT(*) AS noise_total,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS noise_fase_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='NOISE'
""", (ej,))
noise_total, noise_fase_null = cur.fetchone()

# Conversaciones afectadas por NOISE
cur.execute("""
SELECT COUNT(DISTINCT t.conversacion_pk) AS convs_con_noise
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='NOISE'
""", (ej,))
convs_con_noise = cur.fetchone()[0]

print(f"ejecucion_id={ej}")
print(f"noise_total={noise_total}  noise_fase_null={noise_fase_null}")
print(f"convs_con_noise={convs_con_noise}")

cur.close()
conn.close()
