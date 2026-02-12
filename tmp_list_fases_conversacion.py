from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT fase_id, orden_fase, es_fase_terminal, permite_agente_autonomo
FROM fases_conversacion
ORDER BY orden_fase ASC
""")
rows = cur.fetchall()

print("orden".ljust(6), "fase_id".ljust(28), "terminal".ljust(10), "autonomo".ljust(10))
print("-"*60)
for fase_id, orden, terminal, auto in rows:
    print(str(orden).ljust(6), str(fase_id).ljust(28), str(terminal).ljust(10), str(auto).ljust(10))

cur.close()
conn.close()
