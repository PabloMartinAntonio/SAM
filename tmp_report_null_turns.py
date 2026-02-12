import argparse
from sa_core.config import load_config
from sa_core.db import get_conn

def trunc(s, n=160):
    s = (s or "").replace("\r"," ").replace("\n"," ").strip()
    return s if len(s) <= n else s[:n-3] + "..."

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecucion_id", type=int, required=True)
    ap.add_argument("--limit_convs", type=int, default=5)
    ap.add_argument("--max_null_per_conv", type=int, default=12)
    args = ap.parse_args()

    cfg = load_config("config.ini")
    conn = get_conn(cfg)
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT
            c.conversacion_pk, c.conversacion_id, c.total_turnos,
            t.turno_pk, t.turno_idx, t.text, t.fase, t.fase_conf
        FROM sa_conversaciones c
        JOIN sa_turnos t ON t.conversacion_pk = c.conversacion_pk
        WHERE c.ejecucion_id = %s
        ORDER BY c.conversacion_pk, t.turno_idx
    """, (args.ejecucion_id,))
    rows = cur.fetchall()

    # limitar por conv_pk manteniendo orden
    conv_order = []
    seen = set()
    for r in rows:
        pk = r["conversacion_pk"]
        if pk not in seen:
            seen.add(pk)
            conv_order.append(pk)
    if args.limit_convs > 0:
        allowed = set(conv_order[:args.limit_convs])
        rows = [r for r in rows if r["conversacion_pk"] in allowed]

    total_turnos = 0
    total_null = 0

    by_conv = {}
    for r in rows:
        by_conv.setdefault(r["conversacion_pk"], []).append(r)

    for conv_pk in sorted(by_conv.keys()):
        turns = by_conv[conv_pk]
        conv_id = turns[0]["conversacion_id"]
        total = turns[0]["total_turnos"]
        total_turnos += len(turns)

        last_phase = None
        last_idx = None
        nulls = []

        for t in turns:
            fase = (t["fase"] or "").strip() if t["fase"] is not None else ""
            if fase:
                last_phase = fase
                last_idx = t["turno_idx"]
            else:
                total_null += 1
                if len(nulls) < args.max_null_per_conv:
                    nulls.append({
                        "turno_idx": t["turno_idx"],
                        "text": trunc(t["text"]),
                        "prev_phase": last_phase,
                        "prev_idx": last_idx
                    })

        null_count = sum(1 for t in turns if not ((t["fase"] or "").strip() if t["fase"] is not None else ""))
        print(f"\n=== CONV pk={conv_pk} turnos={len(turns)} total_turnos_db={total} NULL={null_count} ===")
        print(f"ID: {conv_id}")
        for x in nulls:
            print(f"- idx={x['turno_idx']:>3} prev={x['prev_phase']}@{x['prev_idx']}  text='{x['text']}'")

    print("\n=== RESUMEN ===")
    print(f"ejecucion_id={args.ejecucion_id}")
    print(f"turnos_leidos={total_turnos}")
    print(f"null_turnos={total_null}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
