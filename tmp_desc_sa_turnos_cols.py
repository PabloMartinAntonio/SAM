from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("SHOW COLUMNS FROM sa_turnos")
cols = cur.fetchall()

print("sa_turnos columns:")
for c in cols:
    print(" -", c[0], "|", c[1])

cur.close()
conn.close()
