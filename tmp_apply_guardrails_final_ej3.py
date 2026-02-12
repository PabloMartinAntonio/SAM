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

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT c.conversacion_pk, t.turno_pk, t.turno_idx, t.fase, t.fase_source
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND LENGTH(TRIM(t.fase))>0
ORDER BY c.conversacion_pk, t.turno_idx
""", (ej,))
rows = cur.fetchall()

to_update = []  # (turno_pk, new_fase, new_source)

seen_formal = set()
seen_cierre = set()
formal_rank = rank["FORMALIZACION_PAGO"]

for conv_pk, turno_pk, idx, fase, src in rows:
    # ignorar ruido
    if fase == "NOISE" or src == "NOISE":
        continue

    # 1) Si ya cerró, todo lo posterior debe ser CIERRE
    if conv_pk in seen_cierre:
        if fase != "CIERRE":
            to_update.append((turno_pk, "CIERRE", "GUARDRAIL2"))
        continue

    # marcar cierre
    if fase == "CIERRE":
        seen_cierre.add(conv_pk)
        continue

    # 2) Si ya entró a formalización, no permitir bajar a fases previas
    if conv_pk in seen_formal:
        # no tocar RULES (lo tuyo manual) ni NOISE
        if src == "RULES":
            continue
        r = rank.get(fase)
        if r is not None and r < formal_rank:
            to_update.append((turno_pk, "FORMALIZACION_PAGO", "GUARDRAIL2"))
        continue

    # marcar formalización
    if fase == "FORMALIZACION_PAGO":
        seen_formal.add(conv_pk)

print("ejecucion_id=", ej)
print("candidatos_update=", len(to_update))

# aplicar updates
total = 0
if to_update:
    chunk_size = 500
    for i in range(0, len(to_update), chunk_size):
        chunk = to_update[i:i+chunk_size]
        ids = [x[0] for x in chunk]

        # Agrupar por new_fase (aquí solo puede ser CIERRE o FORMALIZACION_PAGO)
        # Ejecutamos 2 updates por chunk para mantenerlo simple y seguro.
        for new_fase in ("CIERRE", "FORMALIZACION_PAGO"):
            sub = [x[0] for x in chunk if x[1] == new_fase]
            if not sub:
                continue
            placeholders = ",".join(["%s"] * len(sub))
            sql = f"""
UPDATE sa_turnos
SET fase=%s, fase_source=%s
WHERE turno_pk IN ({placeholders})
"""
            params = [new_fase, "GUARDRAIL2"] + sub
            cur.execute(sql, params)
            total += cur.rowcount

    conn.commit()

print("[OK] rows_affected=", total)

cur.close()
conn.close()
