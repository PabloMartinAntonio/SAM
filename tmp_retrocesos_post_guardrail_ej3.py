from collections import Counter
from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3

ORDER = [
  "PRESENTACION_AGENTE",
  "VALIDACION_IDENTIDAD",
  "EXPOSICION_DEUDA",
  "OFERTA_PAGO",
  "OBJECIONES_CLIENTE",
  "CONSULTA_ACEPTACION",
  "FORMALIZACION_PAGO",
  "CIERRE",
]
rank = {p:i for i,p in enumerate(ORDER)}

TOLERABLE = set([
  ("OBJECIONES_CLIENTE","OFERTA_PAGO"),
  ("VALIDACION_IDENTIDAD","PRESENTACION_AGENTE"),
])

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT c.conversacion_pk, t.turno_idx, t.fase
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
  AND t.fase <> 'NOISE'
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

last = {}
pairs_bad = Counter()
pairs_tol = Counter()
bad = tol = total = 0

for conv_pk, idx, fase in rows:
    r = rank.get(fase)
    if r is None:
        continue
    prev = last.get(conv_pk)
    if prev is None:
        last[conv_pk] = (r, fase)
        continue
    prev_r, prev_fase = prev
    if r < prev_r:
        total += 1
        key = (prev_fase, fase)
        if key in TOLERABLE:
            tol += 1
            pairs_tol[key] += 1
        else:
            bad += 1
            pairs_bad[key] += 1
    else:
        last[conv_pk] = (r, fase)

print("ejecucion_id=", ej)
print("retrocesos_total=", total)
print("retrocesos_tolerables=", tol)
print("retrocesos_malos=", bad)

print("\nTOP 15 malos (prev->curr):")
for (a,b), n in pairs_bad.most_common(15):
    print(f"{n:>5}  {a}  ->  {b}")

cur.close()
conn.close()
