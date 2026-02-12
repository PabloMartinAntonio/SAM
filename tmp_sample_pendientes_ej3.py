import csv, random

p = r"out_reports\run_3_pendientes_llm.csv"
rows = list(csv.DictReader(open(p, encoding="utf-8")))
print("rows=", len(rows))

random.seed(3)
sample = rows[:5] + random.sample(rows, min(10, len(rows)))

for r in sample:
    print("-"*80)
    print("turno_pk=", r["turno_pk"], "conv_pk=", r["conv_pk"], "idx=", r["turno_idx"], "fase=", r["fase"], "source=", r["fase_source"])
    txt = (r.get("text") or "").strip().replace("\n"," ").replace("\r"," ")
    print("text=", txt[:220])
