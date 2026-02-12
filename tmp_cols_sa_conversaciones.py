from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("SELECT DATABASE()")
db = cur.fetchone()[0]
print("DB=", db)

cur.execute("""
SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sa_conversaciones'
ORDER BY ORDINAL_POSITION
""", (db,))

rows = cur.fetchall()
print("cols=", len(rows))
for r in rows:
    print(r)

cur.close()
conn.close()
