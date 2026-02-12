from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Distribución de NOISE por turno_idx (primeros/medios/últimos)
cur.execute("""
SELECT
  SUM(CASE WHEN t.turno_idx <= 2 THEN 1 ELSE 0 END) AS noise_idx_1_2,
  SUM(CASE WHEN t.turno_idx BETWEEN 3 AND 6 THEN 1 ELSE 0 END) AS noise_idx_3_6,
  SUM(CASE WHEN t.turno_idx >= 7 THEN 1 ELSE 0 END) AS noise_idx_7_plus,
  COUNT(*) AS noise_total
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='NOISE'
""", (ej,))
a,b,c_,tot = cur.fetchone()

print(f"ejecucion_id={ej}")
print(f"noise_total={tot}")
print(f"turno_idx<=2: {a}")
print(f"turno_idx 3-6: {b}")
print(f"turno_idx>=7: {c_}")

cur.close()
conn.close()
