import csv
from pathlib import Path
from sa_core.config import load_config
from sa_core.db import get_conn

out = Path("out_reports")
out.mkdir(parents=True, exist_ok=True)

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# 50 sin monto
cur.execute("""
SELECT
  c.ejecucion_id, p.conversacion_pk, p.turno_idx, p.estado_promesa, p.numero_cuotas, p.fecha_pago,
  LEFT(p.evidence_text, 260) ev
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE p.monto IS NULL
ORDER BY c.ejecucion_id, p.promesa_pk DESC
LIMIT 50
""")
sin_monto = cur.fetchall()

# 50 con monto sin moneda
cur.execute("""
SELECT
  c.ejecucion_id, p.conversacion_pk, p.turno_idx, p.monto, p.moneda, p.estado_promesa, p.numero_cuotas, p.fecha_pago,
  LEFT(p.evidence_text, 260) ev
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE p.monto IS NOT NULL AND (p.moneda IS NULL OR p.moneda='')
ORDER BY c.ejecucion_id, p.promesa_pk DESC
LIMIT 50
""")
sin_moneda = cur.fetchall()

cur.close(); conn.close()

p1 = out / "GLOBAL_muestra_sin_monto.csv"
p2 = out / "GLOBAL_muestra_con_monto_sin_moneda.csv"

with open(p1,"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["ejecucion_id","conversacion_pk","turno_idx","estado_promesa","numero_cuotas","fecha_pago","evidence_text_260"])
    for r in sin_monto: w.writerow(list(r))

with open(p2,"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f)
    w.writerow(["ejecucion_id","conversacion_pk","turno_idx","monto","moneda","estado_promesa","numero_cuotas","fecha_pago","evidence_text_260"])
    for r in sin_moneda: w.writerow(list(r))

print("[OK] wrote:", p1)
print("[OK] wrote:", p2)
