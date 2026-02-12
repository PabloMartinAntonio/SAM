from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

for pk in [3918, 5398]:
    cur.execute("""
        SELECT turno_pk, conversacion_pk, turno_idx, fase, fase_conf, fase_source
        FROM sa_turnos
        WHERE turno_pk=%s
    """, (pk,))
    print(cur.fetchone())

cur.close()
conn.close()
