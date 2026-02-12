from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor(dictionary=True)

ej = 2

# 1) Verificar columnas y valores en sa_conversaciones (muestra 5 conversaciones)
cur.execute("""
SELECT
  c.conversacion_pk,
  c.conversacion_id,
  c.total_turnos,
  SUM(CASE WHEN t.fase IS NOT NULL AND TRIM(t.fase)<>'' THEN 1 ELSE 0 END) AS turnos_con_fase,
  c.fase_final,
  c.fase_final_turn_idx,
  c.tipo_finalizacion,
  c.llm_usado
FROM sa_conversaciones c
JOIN sa_turnos t ON t.conversacion_pk = c.conversacion_pk
WHERE c.ejecucion_id = %s
GROUP BY c.conversacion_pk, c.conversacion_id, c.total_turnos, c.fase_final, c.fase_final_turn_idx, c.tipo_finalizacion, c.llm_usado
ORDER BY c.conversacion_pk
LIMIT 5
""", (ej,))
rows = cur.fetchall()
print("\n=== SAMPLE sa_conversaciones (5) ===")
for r in rows:
    print(r)

# 2) Mostrar los últimos 15 turnos de la primera conversación (para ver fase y el “cierre” real)
if rows:
    conv_pk = rows[0]["conversacion_pk"]
    cur.execute("""
    SELECT turno_idx, fase, fase_conf, LEFT(text, 140) AS text
    FROM sa_turnos
    WHERE conversacion_pk = %s
    ORDER BY turno_idx DESC
    LIMIT 15
    """, (conv_pk,))
    last = list(reversed(cur.fetchall()))
    print(f"\n=== LAST 15 TURNS conv_pk={conv_pk} ===")
    for r in last:
        print(r)

cur.close()
conn.close()
print("\nOK")
