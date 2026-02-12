from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("SHOW COLUMNS FROM fases_conversacion")
rows = cur.fetchall()

print("fases_conversacion columns:")
for r in rows:
    print(" -", r[0], "|", r[1], "| null=", r[2], "| key=", r[3], "| default=", r[4])

cur.close()
conn.close()
