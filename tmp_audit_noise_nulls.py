from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  SUM(CASE WHEN t.fase_source='NOISE' THEN 1 ELSE 0 END) AS noise_total,
  SUM(CASE WHEN t.fase_source='NOISE' AND (t.fase IS NULL OR TRIM(t.fase)='') THEN 1 ELSE 0 END) AS noise_fase_null,
  SUM(CASE WHEN t.fase_source='NOISE' AND (t.fase IS NOT NULL AND TRIM(t.fase)<>'') THEN 1 ELSE 0 END) AS noise_fase_nonnull,
  SUM(CASE WHEN (t.fase IS NULL OR TRIM(t.fase)='') THEN 1 ELSE 0 END) AS fase_null_total
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
noise_total, noise_null, noise_nonnull, fase_null_total = cur.fetchone()

print(f"ejecucion_id={ej}")
print(f"noise_total={noise_total}")
print(f"noise_fase_null={noise_null}")
print(f"noise_fase_nonnull={noise_nonnull}")
print(f"fase_null_total={fase_null_total}")

cur.close()
conn.close()
