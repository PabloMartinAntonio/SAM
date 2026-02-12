from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor(dictionary=True)

# detectar columna texto
cur.execute("SHOW COLUMNS FROM sa_turnos")
cols = [r["Field"] for r in cur.fetchall()]
text_col = None
for cand in ("text","texto","utterance","transcript","contenido","turno_texto"):
    if cand in cols:
        text_col = cand
        break
sel_text = f", t.{text_col} AS texto" if text_col else ", NULL AS texto"

sql = f"""
WITH fase_orden AS (
  SELECT 'APERTURA' fase, 1 ord UNION ALL
  SELECT 'IDENTIFICACIÓN', 2 UNION ALL
  SELECT 'INFORMACIÓN_DEUDA', 3 UNION ALL
  SELECT 'NEGOCIACIÓN', 4 UNION ALL
  SELECT 'CONSULTA_ACEPTACIÓN', 5 ord UNION ALL
  SELECT 'CONSULTA_ACEPTACION', 5 ord UNION ALL
  SELECT 'FORMALIZACIÓN_PAGO', 6 ord UNION ALL
  SELECT 'FORMALIZACION_PAGO', 6 ord UNION ALL
  SELECT 'ADVERTENCIAS', 7 ord UNION ALL
  SELECT 'CIERRE', 8 ord
),
t2 AS (
  SELECT
    t.conversacion_pk,
    t.turno_idx,
    t.fase,
    LAG(t.fase) OVER (PARTITION BY t.conversacion_pk ORDER BY t.turno_idx) AS prev_fase
    {sel_text}
  FROM sa_turnos t
  JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
  WHERE c.ejecucion_id=%s
    AND t.fase IS NOT NULL AND TRIM(t.fase) <> ''
)
SELECT
  c.conversacion_id,
  t2.turno_idx,
  t2.prev_fase,
  t2.fase AS curr_fase,
  t2.texto
FROM t2
JOIN fase_orden fo_cur ON fo_cur.fase=t2.fase
JOIN fase_orden fo_prev ON fo_prev.fase=t2.prev_fase
JOIN sa_conversaciones c ON c.conversacion_pk=t2.conversacion_pk
WHERE fo_cur.ord < fo_prev.ord
  AND NOT (
    (t2.prev_fase IN ('FORMALIZACION_PAGO','FORMALIZACIÓN_PAGO') AND t2.fase IN ('CONSULTA_ACEPTACION','CONSULTA_ACEPTACIÓN'))
    OR
    (t2.prev_fase='ADVERTENCIAS' AND t2.fase IN ('CONSULTA_ACEPTACION','CONSULTA_ACEPTACIÓN'))
    OR
    (t2.prev_fase='ADVERTENCIAS' AND t2.fase IN ('FORMALIZACION_PAGO','FORMALIZACIÓN_PAGO'))
  )
LIMIT 5
"""

cur.execute(sql, (ej,))
rows = cur.fetchall()

print(f"ejecucion_id={ej} rows={len(rows)} text_col={text_col or 'NONE'}")
print("-"*90)
for r in rows:
    texto = (r.get("texto") or "")
    texto = " ".join(texto.split())
    if len(texto) > 320:
        texto = texto[:320] + "..."
    print(f"conv_id={r['conversacion_id']}")
    print(f"turno_idx={r['turno_idx']}  prev={r['prev_fase']}  curr={r['curr_fase']}")
    print(f"texto={texto}")
    print("-"*90)

cur.close()
conn.close()
