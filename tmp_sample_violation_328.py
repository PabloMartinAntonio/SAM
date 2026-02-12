from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor(dictionary=True)

# Detectar nombre de columna texto en sa_turnos
cur.execute("SHOW COLUMNS FROM sa_turnos")
cols = [r["Field"] for r in cur.fetchall()]
text_col = None
for cand in ("texto", "utterance", "transcript", "contenido", "turno_texto", "text"):
    if cand in cols:
        text_col = cand
        break

sel_text = f", t.{text_col} AS texto" if text_col else ", NULL AS texto"

sql = f"""
WITH t2 AS (
  SELECT
    t.conversacion_pk,
    t.turno_idx,
    t.fase,
    LAG(t.fase) OVER (PARTITION BY t.conversacion_pk ORDER BY t.turno_idx) AS prev_fase
    {sel_text}
  FROM sa_turnos t
  JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
  WHERE c.ejecucion_id=%s
)
SELECT
  c.conversacion_id,
  t2.turno_idx,
  t2.prev_fase,
  t2.fase AS curr_fase,
  t2.texto
FROM t2
JOIN sa_conversaciones c ON c.conversacion_pk=t2.conversacion_pk
WHERE t2.prev_fase='FORMALIZACION_PAGO'
  AND t2.fase='CONSULTA_ACEPTACION'
ORDER BY RAND()
LIMIT 10
"""

cur.execute(sql, (ej,))
rows = cur.fetchall()

print(f"ejecucion_id={ej}")
print(f"text_col={text_col or 'NONE'}")
print(f"rows={len(rows)}")
print("-"*80)
for r in rows:
    texto = (r.get("texto") or "")
    texto = " ".join(texto.split())
    if len(texto) > 240:
        texto = texto[:240] + "..."
    print(f"conv_id={r['conversacion_id']}")
    print(f"turno_idx={r['turno_idx']}  prev={r['prev_fase']}  curr={r['curr_fase']}")
    print(f"texto={texto}")
    print("-"*80)

cur.close()
conn.close()
