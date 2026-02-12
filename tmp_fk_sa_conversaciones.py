from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  k.CONSTRAINT_NAME,
  k.COLUMN_NAME,
  k.REFERENCED_TABLE_NAME,
  k.REFERENCED_COLUMN_NAME
FROM information_schema.KEY_COLUMN_USAGE k
WHERE k.TABLE_SCHEMA = DATABASE()
  AND k.TABLE_NAME = 'sa_conversaciones'
  AND k.REFERENCED_TABLE_NAME IS NOT NULL
ORDER BY k.CONSTRAINT_NAME, k.ORDINAL_POSITION
""")
rows = cur.fetchall()

print("FKs sa_conversaciones:")
for r in rows:
    print(" -", r)

cur.close()
conn.close()
