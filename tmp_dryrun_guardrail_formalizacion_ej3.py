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

CLAMP_FROM = "FORMALIZACION_PAGO"
clamp_rank = rank[CLAMP_FROM]

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT c.conversacion_pk,
       COALESCE(c.conversacion_id, CAST(c.conversacion_pk AS CHAR)) AS conversation_id,
       t.turno_pk, t.turno_idx, t.speaker, t.fase, t.fase_source, t.fase_conf,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 180) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
  AND t.fase <> 'NOISE'
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

seen_formal = {}
changes = []
by_pair = Counter()

for conv_pk, conv_id, turno_pk, idx, speaker, fase, src, conf, txt in rows:
    r = rank.get(fase)
    if r is None:
        continue

    if conv_pk not in seen_formal:
        if fase == CLAMP_FROM:
            seen_formal[conv_pk] = True
        else:
            continue
    else:
        # ya vimos formalización, mantener CIERE
        if fase == "CIERRE":
            continue
        # solo clamplear DEEPSEEK, no tocar RULES/NOISE/CI_*
        if src != "DEEPSEEK":
            continue
        if r < clamp_rank:
            by_pair[(fase, CLAMP_FROM)] += 1
            changes.append((conv_id, turno_pk, idx, speaker, src, conf, fase, CLAMP_FROM, txt))

print("ejecucion_id=", ej)
print("would_change=", len(changes))

print("\nTOP 15 cambios (from -> FORMALIZACION_PAGO):")
for (a,b), n in by_pair.most_common(15):
    print(f"{n:>5}  {a} -> {b}")

print("\nMUESTRA 20 cambios:")
for x in changes[:20]:
    print(x)

cur.close()
conn.close()
