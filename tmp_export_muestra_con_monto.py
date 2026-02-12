import csv
from pathlib import Path
from sa_core.config import load_config
from sa_core.db import get_conn

out = Path("out_reports")
out.mkdir(parents=True, exist_ok=True)
ej = 5
csv_path = out / f"ej_{ej}_promesas_muestra_con_monto.csv"

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  p.conversacion_pk, p.turno_idx, p.monto, p.moneda, p.numero_cuotas, p.fecha_pago, p.estado_promesa,
  LEFT(p.evidence_text, 250)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s AND p.monto IS NOT NULL
ORDER BY p.promesa_pk DESC
LIMIT 50
""",(ej,))
rows = cur.fetchall()

cur.close(); conn.close()

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["conversacion_pk","turno_idx","monto","moneda","numero_cuotas","fecha_pago","estado_promesa","evidence_text_250"])
    for r in rows:
        w.writerow(list(r))

print("[OK] wrote:", csv_path)
