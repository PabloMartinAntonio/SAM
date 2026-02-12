from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT ejecucion_id, COUNT(*) convs
FROM sa_conversaciones
GROUP BY ejecucion_id
ORDER BY ejecucion_id
""")
print("ejecucion_id, conversaciones")
for ej, convs in cur.fetchall():
    print(ej, convs)

cur.close(); conn.close()
