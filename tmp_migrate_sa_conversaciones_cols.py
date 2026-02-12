from sa_core.config import load_config
from sa_core.db import get_conn

def ensure_cols(conn):
    cur = conn.cursor()
    cur.execute("SELECT DATABASE()")
    db = cur.fetchone()[0]
    print("DB=", db)

    cur.execute("""
    SELECT COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sa_conversaciones'
    """, (db,))
    existing = {r[0] for r in cur.fetchall()}

    alters = []
    if "fase_final" not in existing:
        alters.append("ADD COLUMN fase_final VARCHAR(32) NULL")
    if "fase_final_turn_idx" not in existing:
        alters.append("ADD COLUMN fase_final_turn_idx INT NULL")
    if "tipo_finalizacion" not in existing:
        alters.append("ADD COLUMN tipo_finalizacion VARCHAR(32) NULL")
    if "llm_usado" not in existing:
        alters.append("ADD COLUMN llm_usado TINYINT NOT NULL DEFAULT 0")

    if not alters:
        print("OK: sa_conversaciones ya tiene las columnas de fases.")
        return

    sql = "ALTER TABLE sa_conversaciones " + ", ".join(alters)
    print("RUN:", sql)
    cur.execute(sql)
    conn.commit()
    print("OK: columnas agregadas/actualizadas en sa_conversaciones.")

    cur.close()

cfg = load_config("config.ini")
conn = get_conn(cfg)
ensure_cols(conn)
conn.close()
