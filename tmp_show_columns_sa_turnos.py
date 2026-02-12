from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("SHOW COLUMNS FROM sa_turnos")
rows = cur.fetchall()
print("sa_turnos columns:")
for r in rows:
    # Field, Type, Null, Key, Default, Extra
    print(r)

cur.close()
conn.close()
