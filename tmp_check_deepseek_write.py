from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor(dictionary=True)

ej = 2

print("=== ULTIMOS TURNOS CON DEEPSEEK (run=2) ===")
cur.execute("""
SELECT
  t.turno_pk, t.conversacion_pk, c.conversacion_id,
  t.turno_idx, t.fase, t.fase_conf, t.fase_source,
  LEFT(t.text, 90) AS text90
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
WHERE c.ejecucion_id=%s AND t.fase_source='DEEPSEEK'
ORDER BY t.turno_pk DESC
LIMIT 20
""", (ej,))
rows = cur.fetchall()
print("rows=", len(rows))
for r in rows:
    print(r)

print("\n=== CONVERSACIONES MARCADAS llm_usado=1 (run=2) ===")
cur.execute("""
SELECT conversacion_pk, conversacion_id, llm_usado, fase_final, fase_final_turn_idx, tipo_finalizacion
FROM sa_conversaciones
WHERE ejecucion_id=%s AND llm_usado=1
ORDER BY conversacion_pk DESC
LIMIT 20
""", (ej,))
rows2 = cur.fetchall()
print("rows=", len(rows2))
for r in rows2:
    print(r)

cur.close()
conn.close()
print("\nOK")
