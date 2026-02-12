from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Agregar columna solo si no existe
cur.execute("SHOW COLUMNS FROM sa_turnos LIKE 'fase_8'")
exists = cur.fetchone() is not None

if not exists:
    cur.execute("ALTER TABLE sa_turnos ADD COLUMN fase_8 varchar(64) NULL AFTER fase")
    conn.commit()
    print("[OK] added column sa_turnos.fase_8")
else:
    print("[OK] column sa_turnos.fase_8 already exists")

cur.close()
conn.close()
