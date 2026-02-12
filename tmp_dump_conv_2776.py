from sa_core.config import load_config
from sa_core.db import get_conn

conv_pk = 2776

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT t.turno_idx, t.speaker, t.fase, t.fase_source, t.fase_conf,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 220) AS txt
FROM sa_turnos t
WHERE t.conversacion_pk=%s
ORDER BY t.turno_idx
""", (conv_pk,))

rows = cur.fetchall()
print("conv_pk=", conv_pk, "turnos=", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
