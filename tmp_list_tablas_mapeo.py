from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Buscar tablas candidatas
cur.execute("SHOW TABLES")
tables = [r[0] for r in cur.fetchall()]
cands = [t for t in tables if any(k in t.lower() for k in ["mape", "map", "fase", "fases", "tax", "intent"])]

print("tablas_candidatas=", len(cands))
for t in sorted(cands):
    print(" -", t)

print("\nexists_intents_fases=", "intents_fases" in tables)

cur.close()
conn.close()
