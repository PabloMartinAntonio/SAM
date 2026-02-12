import inspect
from sa_core.config import load_config
from sa_core.db import get_conn
from sa_core.fases_rules import apply_fase_rules_for_run

EJ = 2
LIMIT = 5
TH = 0.55
CONV_PK = 4
TURNO_IDX = 31

print("apply_fase_rules_for_run file:", inspect.getsourcefile(apply_fase_rules_for_run))

cfg = load_config("config.ini")
conn = get_conn(cfg)

apply_fase_rules_for_run(conn, EJ, limit=LIMIT, conf_threshold=TH, verbose=True)

cur = conn.cursor(dictionary=True)
cur.execute("""
SELECT turno_idx, fase, fase_conf, fase_source, text
FROM sa_turnos
WHERE conversacion_pk=%s AND turno_idx=%s
""", (CONV_PK, TURNO_IDX))
row = cur.fetchone()
print("\n=== AFTER APPLY ===")
print(row)

cur.close()
conn.close()
