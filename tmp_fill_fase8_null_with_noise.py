from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
SET t.fase_8='NOISE'
WHERE c.ejecucion_id=%s
  AND (t.fase_8 IS NULL OR TRIM(t.fase_8)='')
"""
cur.execute(sql, (ej,))
updated = cur.rowcount
conn.commit()

print(f"[OK] ejecucion_id={ej} set_fase8_noise_rows={updated}")

cur.close()
conn.close()
