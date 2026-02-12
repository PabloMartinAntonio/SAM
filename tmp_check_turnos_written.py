from sa_core.config import load_config
from sa_core.db import get_conn

turno_pks = (3603,3609,3618)  # agrega acá los que te devolvió como [OK] en write
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

fmt = ",".join(["%s"]*len(turno_pks))
cur.execute(f"""
SELECT turno_pk, fase, fase_conf, fase_source
FROM sa_turnos
WHERE turno_pk IN ({fmt})
ORDER BY turno_pk
""", turno_pks)

for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
