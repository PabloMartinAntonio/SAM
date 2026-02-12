from sa_core.config import load_config
from sa_core.db import get_conn
from sa_core.turnos import parse_turns_for_run

ej = 5
cfg = load_config("config.ini")
conn = get_conn(cfg)

parse_turns_for_run(conn, ejecucion_id=ej, limit=0, verbose=True)

cur = conn.cursor()
cur.execute("""
SELECT COUNT(*)
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
""", (ej,))
print("sa_turnos_count=", cur.fetchone()[0])

cur.close()
conn.close()
