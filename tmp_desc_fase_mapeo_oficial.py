from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("SHOW COLUMNS FROM fase_mapeo_oficial")
rows = cur.fetchall()

print("fase_mapeo_oficial columns:")
for r in rows:
    # Field, Type, Null, Key, Default, Extra
    print(" -", r[0], "|", r[1], "| null=", r[2], "| key=", r[3], "| default=", r[4])

cur.close()
conn.close()
