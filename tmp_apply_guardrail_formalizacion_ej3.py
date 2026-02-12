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
clamp_from = "FORMALIZACION_PAGO"
clamp_rank = rank[clamp_from]

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT c.conversacion_pk, t.turno_pk, t.turno_idx, t.fase, t.fase_source
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
  AND t.fase <> 'NOISE'
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

seen_formal = set()
to_update = []  # turno_pk

for conv_pk, turno_pk, idx, fase, src in rows:
    r = rank.get(fase)
    if r is None:
        continue

    if conv_pk not in seen_formal:
        if fase == clamp_from:
            seen_formal.add(conv_pk)
        continue

    # después de formalización: permitir cierre
    if fase == "CIERRE":
        continue

    # solo modificar lo que viene de DEEPSEEK
    if src != "DEEPSEEK":
        continue

    if r < clamp_rank:
        to_update.append(turno_pk)

print("ejecucion_id=", ej)
print("candidatos_update=", len(to_update))

if to_update:
    # UPDATE en batch (IN ...)
    # chunk para no exceder max packet
    chunk_size = 500
    total = 0
    for i in range(0, len(to_update), chunk_size):
        chunk = to_update[i:i+chunk_size]
        placeholders = ",".join(["%s"]*len(chunk))
        sql = f"""
UPDATE sa_turnos
SET fase=%s, fase_source=%s
WHERE turno_pk IN ({placeholders})
"""
        params = [clamp_from, "GUARDRAIL"] + chunk
        cur.execute(sql, params)
        total += cur.rowcount
    conn.commit()
    print("[OK] rows_affected=", total)
else:
    print("[OK] nothing to do")

cur.close()
conn.close()
