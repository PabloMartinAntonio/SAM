import csv
from collections import Counter

p = r"out_reports\run_3_pendientes_llm.csv"
rows = list(csv.DictReader(open(p, encoding="utf-8")))
print("file=", p)
print("rows=", len(rows))
print("cols=", rows[0].keys() if rows else [])

def top_count(col, n=20):
    c = Counter((r.get(col) or "").strip() for r in rows)
    print(f"\nTOP {n} {col}:")
    for k,v in c.most_common(n):
        print(v, k)

# Intentar columnas típicas (solo imprime si existen)
candidates = ["reason","motivo","causa","tipo","status","estado","fase_source","fase","fase_conf","llm_conf","confidence","conf"]
for col in candidates:
    if rows and col in rows[0]:
        top_count(col, 20)

# Si hay numeric conf, mostrar min/avg/max de lo que exista
import math
for col in ["fase_conf","llm_conf","confidence","conf"]:
    if rows and col in rows[0]:
        vals=[]
        for r in rows:
            try:
                vals.append(float((r.get(col) or "").strip()))
            except:
                pass
        if vals:
            print(f"\n{col}: n={len(vals)} min={min(vals):.4f} avg={sum(vals)/len(vals):.4f} max={max(vals):.4f}")

