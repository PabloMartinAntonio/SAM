from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Turnos detectados como NOISE pero con texto real
updates = [
    # (turno_pk, fase)
    (57408, "CIERRE"),      # despedida / cierre
    (57517, "APERTURA"),    # saludo
    (57518, "APERTURA"),    # respuesta al saludo (sigue apertura)
]

sql = """
UPDATE sa_turnos
SET fase=%s, fase_source=%s
WHERE turno_pk=%s
  AND (fase IS NULL OR LENGTH(TRIM(fase))=0)
  AND fase_source=%s
"""

total = 0
for turno_pk, fase in updates:
    cur.execute(sql, (fase, "RULES", turno_pk, "NOISE"))
    total += cur.rowcount

conn.commit()
print("[OK] rows_affected=", total)

# Verificación rápida
cur.execute("""
SELECT turno_pk, conversacion_pk, turno_idx, fase, fase_source,
       LEFT(REPLACE(REPLACE(COALESCE(text,''), '\\n',' '), '\\r',' '), 120) AS txt
FROM sa_turnos
WHERE turno_pk IN (57408,57517,57518)
ORDER BY turno_pk
""")
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
