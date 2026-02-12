from sa_core.config import load_config
from sa_core.db import get_conn

EJ = 2

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Turnos (filtrados por ejecucion_id via join)
cur.execute("""
SELECT
  COUNT(*) AS total_turnos,
  SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase)='' THEN 1 ELSE 0 END) AS null_turnos,
  SUM(CASE WHEN t.fase_source='RULES' THEN 1 ELSE 0 END) AS rules_turnos,
  SUM(CASE WHEN t.fase_source IS NULL THEN 1 ELSE 0 END) AS source_null
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
WHERE c.ejecucion_id = %s
""", (EJ,))
print("TURNOS:", cur.fetchone())

# Conversaciones (fase_final)
cur.execute("""
SELECT
  COUNT(*) AS total_convs,
  SUM(CASE WHEN c.fase_final IS NULL OR TRIM(c.fase_final)='' THEN 1 ELSE 0 END) AS convs_fase_final_null,
  SUM(CASE WHEN c.tipo_finalizacion='CIERRE' THEN 1 ELSE 0 END) AS convs_cierre,
  SUM(CASE WHEN c.tipo_finalizacion='CORTE' THEN 1 ELSE 0 END) AS convs_corte
FROM sa_conversaciones c
WHERE c.ejecucion_id = %s
""", (EJ,))
print("CONVS :", cur.fetchone())

cur.close()
conn.close()
