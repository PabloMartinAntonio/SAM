import re
from sa_core.config import load_config
from sa_core.db import get_conn

ej = 3
MIN_LEN = 12

def clean(s: str) -> str:
    s = (s or "").strip()
    s = s.replace("\n"," ").replace("\r"," ")
    s = re.sub(r"\s+", " ", s)
    return s

def is_noise_short(s: str) -> bool:
    s = clean(s)
    if len(s) < MIN_LEN:
        return True
    # solo numeros / puntuacion
    if re.fullmatch(r"[\d\s\.\,\-\?!¿:;]+", s):
        return True
    return False

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Traer NO_IMP con contexto prev/next ya disponible vía ventana (subqueries)
cur.execute("""
SELECT t.turno_pk, t.conversacion_pk, t.turno_idx, t.text,
       (
         SELECT t2.fase FROM sa_turnos t2
         WHERE t2.conversacion_pk=t.conversacion_pk AND t2.turno_idx=t.turno_idx-1
         LIMIT 1
       ) AS prev_fase,
       (
         SELECT t3.fase FROM sa_turnos t3
         WHERE t3.conversacion_pk=t.conversacion_pk AND t3.turno_idx=t.turno_idx+1
         LIMIT 1
       ) AS next_fase
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase_source='NO_IMP'
""", (ej,))
rows = cur.fetchall()

to_update = []
skip = 0
for turno_pk, conv_pk, idx, text, prev_fase, next_fase in rows:
    if not is_noise_short(text):
        skip += 1
        continue
    target = (prev_fase or "").strip() or (next_fase or "").strip()
    if not target or target == "NOISE":
        continue
    to_update.append((turno_pk, target))

print("ejecucion_id=", ej)
print("no_imp_total=", len(rows))
print("short_skipped_long=", skip)
print("candidatos_update=", len(to_update))

total = 0
if to_update:
    # update por chunks
    chunk_size = 500
    for i in range(0, len(to_update), chunk_size):
        chunk = to_update[i:i+chunk_size]
        # hacemos updates individuales para no armar CASE gigante (53 no es nada)
        for turno_pk, fase in chunk:
            cur.execute("""
UPDATE sa_turnos
SET fase=%s, fase_source=%s
WHERE turno_pk=%s AND fase_source='NO_IMP'
""", (fase, "IMPUTE_SHORT", turno_pk))
            total += cur.rowcount
    conn.commit()

print("[OK] rows_affected=", total)

cur.close()
conn.close()
