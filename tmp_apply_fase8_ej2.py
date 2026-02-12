from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
version = "v12a8_ej2_2026-02-09"

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
UPDATE sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
LEFT JOIN fase_mapeo_oficial m
  ON m.version=%s
 AND m.activo=1
 AND m.fase_vieja_id=t.fase
SET t.fase_8 = m.fase_nueva_id
WHERE c.ejecucion_id=%s
"""
cur.execute(sql, (version, ej))
updated = cur.rowcount
conn.commit()

print(f"[OK] ejecucion_id={ej} version={version} updated_rows={updated}")

cur.close()
conn.close()
