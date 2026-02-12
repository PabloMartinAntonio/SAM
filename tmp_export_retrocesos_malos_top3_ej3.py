import csv
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
SELECT c.conversacion_pk,
       COALESCE(c.conversacion_id, CAST(c.conversacion_pk AS CHAR)) AS conversation_id,
       t.turno_idx, t.speaker, t.fase,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 200) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
  AND t.fase <> 'NOISE'
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

# 1) contar pares malos y quedarnos con top3
last = {}
pairs_bad = Counter()
events = []  # (pair, conv_id, prev_idx, prev_fase, curr_idx, curr_fase, speaker, txt)

for conv_pk, conv_id, idx, speaker, fase, txt in rows:
    r = rank.get(fase)
    if r is None:
        continue
    prev = last.get(conv_pk)
    if prev is None:
        last[conv_pk] = (r, idx, fase)
        continue
    prev_r, prev_idx, prev_fase = prev
    if r < prev_r:
        key = (prev_fase, fase)
        if key not in TOLERABLE:
            pairs_bad[key] += 1
            events.append((key, conv_id, prev_idx, prev_fase, idx, fase, speaker, txt))
    else:
        last[conv_pk] = (r, idx, fase)

top3 = [k for k,_ in pairs_bad.most_common(3)]
print("top3_pairs=", top3)

# 2) exportar hasta N ejemplos por par
N = 20
out = r"out_reports\ej3_retrocesos_malos_top3.csv"
picked = {k:0 for k in top3}

with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["conversation_id","prev_turno_idx","prev_fase","curr_turno_idx","curr_fase","speaker","txt"])
    for key, conv_id, prev_idx, prev_fase, idx, fase, speaker, txt in events:
        if key in picked and picked[key] < N:
            w.writerow([conv_id, prev_idx, prev_fase, idx, fase, speaker, txt])
            picked[key] += 1

print("[OK] wrote:", out)
print("examples_written=", picked)

cur.close()
conn.close()
