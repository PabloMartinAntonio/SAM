import csv
from sa_core.config import load_config
from sa_core.db import get_conn

version = "v12a8_ej2_2026-02-09"
csv_path = r"out_reports\mapeo_fases_12a8_propuesto.csv"

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# seguridad: borrar solo esa version si ya existiera (idempotente)
cur.execute("DELETE FROM fase_mapeo_oficial WHERE version=%s", (version,))
deleted = cur.rowcount

ins = """
INSERT INTO fase_mapeo_oficial
(version, fase_vieja_id, fase_nueva_id, criterio, patron, prioridad, activo)
VALUES (%s,%s,%s,%s,%s,%s,%s)
"""

rows = []
with open(csv_path, newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        rows.append((
            version,
            row["fase_origen"].strip(),
            row["fase_destino_8"].strip(),
            "DEFAULT",
            None,
            10,
            1
        ))

cur.executemany(ins, rows)
inserted = cur.rowcount
conn.commit()

print(f"[OK] version={version} deleted_prev={deleted} inserted={inserted}")

cur.close()
conn.close()
