import os, csv, argparse
from collections import Counter, defaultdict
from sa_core.config import load_config
from sa_core.db import get_conn

def is_null_fase(f):
    return f is None or (isinstance(f, str) and f.strip() == "")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecucion_id", type=int, required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--config", default="config.ini")
    ap.add_argument("--max_rows", type=int, default=0, help="0 = sin limite")
    args = ap.parse_args()

    out_path = args.out or os.path.join("out_reports", f"run_{args.ejecucion_id}_pendientes_llm.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    cfg = load_config(args.config)
    conn = get_conn(cfg)
    cur = conn.cursor()

    # Traemos TODOS los turnos del run, ordenados por conversacion y turno_idx
    cur.execute("""
        SELECT
            t.turno_pk,
            t.conversacion_pk,
            c.conversacion_id,
            t.turno_idx,
            t.text,
            t.fase,
            t.fase_conf,
            t.fase_source
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
        WHERE c.ejecucion_id = %s
        ORDER BY t.conversacion_pk ASC, t.turno_idx ASC
    """, (args.ejecucion_id,))

    rows = cur.fetchall()

    # Agrupar por conversacion_pk
    by_conv = defaultdict(list)
    for r in rows:
        turno_pk, conv_pk, conv_id, turno_idx, text, fase, fase_conf, fase_source = r
        by_conv[conv_pk].append({
            "turno_pk": turno_pk,
            "conv_pk": conv_pk,
            "conv_id": conv_id,
            "turno_idx": int(turno_idx),
            "text": text or "",
            "fase": fase,
            "fase_conf": float(fase_conf) if fase_conf is not None else None,
            "fase_source": fase_source,
        })

    # Calcular prev_fase y next_fase por conversación (sin subqueries)
    pendientes = []
    prev_counts = Counter()
    next_counts = Counter()

    for conv_pk, turns in by_conv.items():
        total = len(turns)

        prev_phase = None
        prev_phases = [None]*total
        for i, t in enumerate(turns):
            prev_phases[i] = prev_phase
            if not is_null_fase(t["fase"]):
                prev_phase = t["fase"]

        next_phase = None
        next_phases = [None]*total
        for i in range(total-1, -1, -1):
            next_phases[i] = next_phase
            if not is_null_fase(turns[i]["fase"]):
                next_phase = turns[i]["fase"]

        for i, t in enumerate(turns):
            if is_null_fase(t["fase"]):
                pf = prev_phases[i]
                nf = next_phases[i]
                prev_counts[pf or "NONE"] += 1
                next_counts[nf or "NONE"] += 1

                is_last = (total - t["turno_idx"]) < 3
                pendientes.append({
                    **t,
                    "total_turnos_conv": total,
                    "prev_fase": pf,
                    "next_fase": nf,
                    "is_last_turns": int(bool(is_last)),
                })

    # Ordenar (útil para batch LLM por conversación)
    pendientes.sort(key=lambda x: (x["conv_pk"], x["turno_idx"]))

    # Escribir CSV
    cols = [
        "turno_pk","conv_pk","conv_id","turno_idx","total_turnos_conv",
        "prev_fase","next_fase","is_last_turns",
        "fase","fase_conf","fase_source","text"
    ]

    written = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for p in pendientes:
            w.writerow({k: p.get(k) for k in cols})
            written += 1
            if args.max_rows and written >= args.max_rows:
                break

    cur.close()
    conn.close()

    print(f"[OK] run={args.ejecucion_id} turnos_total={len(rows)} pendientes_NULL={len(pendientes)} wrote={written} -> {out_path}")
    print("\nTop prev_fase (pendientes):")
    for k,v in prev_counts.most_common(12):
        print(f"  {k}: {v}")
    print("\nTop next_fase (pendientes):")
    for k,v in next_counts.most_common(12):
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
