from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3

# Orden esperado (ajustable). NOISE fuera.
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

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT c.conversacion_pk,
       COALESCE(c.conversacion_id, CAST(c.conversacion_pk AS CHAR)) AS conversation_id,
       t.turno_idx, t.speaker, t.fase, t.fase_source,
       LEFT(REPLACE(REPLACE(COALESCE(t.text,''), '\\n',' '), '\\r',' '), 140) AS txt
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
  AND t.fase <> 'NOISE'
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

bad = []
last_by_conv = {}

for conv_pk, conv_id, idx, speaker, fase, src, txt in rows:
    r = rank.get(fase)
    if r is None:
        continue  # fases fuera del orden -> las ignoramos en este chequeo
    prev = last_by_conv.get(conv_pk)
    if prev is None:
        last_by_conv[conv_pk] = (r, idx, fase)
        continue
    prev_r, prev_idx, prev_fase = prev
    if r < prev_r:
        bad.append((conv_pk, conv_id, prev_idx, prev_fase, idx, fase, speaker, src, txt))
    else:
        last_by_conv[conv_pk] = (r, idx, fase)

print("ejecucion_id=", ej)
print("retrocesos_detectados=", len(bad))
print("muestra_hasta_30:")
for x in bad[:30]:
    print(x)

cur.close()
conn.close()
