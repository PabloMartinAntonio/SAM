from sa_core.config import load_config
from sa_core.db import get_conn
from sa_core.fases_rules import detect_fase_rules_based, normalize_text
import re
import sa_core.fases_rules as fr

EJ = 2
CONV_PK = 4
TURNO_IDX = 31

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor(dictionary=True)

cur.execute("SELECT conversacion_id FROM sa_conversaciones WHERE conversacion_pk=%s", (CONV_PK,))
row = cur.fetchone()
conv_id = row["conversacion_id"] if row else None

cur.execute("""
SELECT turno_pk, turno_idx, text, fase, fase_conf
FROM sa_turnos
WHERE conversacion_pk=%s AND turno_idx=%s
""", (CONV_PK, TURNO_IDX))
turn = cur.fetchone()

cur.execute("""
SELECT turno_idx, fase
FROM sa_turnos
WHERE conversacion_pk=%s AND fase IS NOT NULL AND turno_idx < %s
ORDER BY turno_idx DESC
LIMIT 1
""", (CONV_PK, TURNO_IDX))
prev = cur.fetchone()
prev_phase = prev["fase"] if prev else None
prev_idx = prev["turno_idx"] if prev else None

cur.execute("SELECT COUNT(*) AS n FROM sa_turnos WHERE conversacion_pk=%s", (CONV_PK,))
total = cur.fetchone()["n"]

t_raw = (turn["text"] or "") if turn else ""
t_norm = normalize_text(t_raw)

is_last = (total - int(TURNO_IDX)) < 3

print("EJ=", EJ)
print("conv_pk=", CONV_PK)
print("conv_id=", conv_id)
print("turno_idx=", TURNO_IDX, "total_turns=", total, "is_last=", is_last)
print("prev_idx=", prev_idx, "prev_phase=", prev_phase)
print("db_fase_actual=", (turn["fase"] if turn else None), "db_conf_actual=", (turn["fase_conf"] if turn else None))
print("--- RAW (repr) ---")
print(repr(t_raw))
print("--- NORM ---")
print(t_norm)

contact_match = re.search(r"\b(me podria llamar|podria llamar|me puede llamar|lo llamo|le llamo)\b", t_norm)
timing_match  = re.search(r"\b(manana|horario|coordino|coordinar)\b", t_norm)
gusto_match   = re.search(r"con quien tengo el gusto", t_norm)

print("--- MATCHES ---")
print("contact_match=", bool(contact_match))
print("timing_match =", bool(timing_match))
print("gusto_match  =", bool(gusto_match))
print("WHEN_BRINDO  =", bool(fr.WHEN_BRINDO_RE.search(t_norm)))

fase, conf, score = detect_fase_rules_based(
    t_raw, int(TURNO_IDX), int(total),
    last_phase=prev_phase,
    is_last_turns=is_last
)

print("--- DETECT ---")
print(f"fase={fase} conf={conf:.4f} score={score}")

cur.close()
conn.close()
