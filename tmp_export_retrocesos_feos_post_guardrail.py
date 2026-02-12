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

TARGET_BAD = set([
  ("CIERRE", "FORMALIZACION_PAGO"),
  ("FORMALIZACION_PAGO", "VALIDACION_IDENTIDAD"),
  ("FORMALIZACION_PAGO", "OFERTA_PAGO"),
  ("FORMALIZACION_PAGO", "OBJECIONES_CLIENTE"),
])

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT c.conversacion_pk,
       COALESCE(c.conversacion_id, CAST(c.conversacion_pk AS CHAR)) AS conversation_id,
       t.turno_pk, t.turno_idx, t.speaker, t.fase, t.fase_source,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 220) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
  AND t.fase <> 'NOISE'
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

last = {}
events = []
cnt = Counter()

for conv_pk, conv_id, turno_pk, idx, speaker, fase, src, txt in rows:
    r = rank.get(fase)
    if r is None:
        continue
    prev = last.get(conv_pk)
    if prev is None:
        last[conv_pk] = (r, idx, fase)
        continue
    prev_r, prev_idx, prev_fase = prev
    if r < prev_r:
        pair = (prev_fase, fase)
        if pair in TARGET_BAD:
            cnt[pair] += 1
            events.append((conv_id, prev_idx, prev_fase, idx, fase, speaker, src, txt, turno_pk))
    else:
        last[conv_pk] = (r, idx, fase)

out = r"out_reports\ej3_retrocesos_feos_post_guardrail.csv"
with open(out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["conversation_id","prev_turno_idx","prev_fase","curr_turno_idx","curr_fase","speaker","fase_source","txt","turno_pk"])
    for e in events:
        w.writerow(e)

print("ejecucion_id=", ej)
print("[OK] wrote:", out)
print("counts_by_pair:")
for k,n in cnt.most_common():
    print(f"{n:>5}  {k[0]} -> {k[1]}")

cur.close()
conn.close()
