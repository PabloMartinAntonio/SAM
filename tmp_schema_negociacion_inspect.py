from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
cands = [t for t in tables if any(k in t.lower() for k in ["promes","negoc","acuer","extrac","entidad","pago"])]
print("candidate_tables=", cands)

for t in sorted(cands):
    print("\n--", t, "--")
    cur.execute(f"DESCRIBE {t}")
    for row in cur.fetchall():
        print(row)

cur.close(); conn.close()
