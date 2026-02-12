import csv
from pathlib import Path
from sa_core.config import load_config
from sa_core.db import get_conn

out = Path("out_reports")
out.mkdir(parents=True, exist_ok=True)
ej = 5
csv_path = out / f"ej_{ej}_promesas_resumen.csv"

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

cur.execute("""
SELECT
  COUNT(*) total,
  SUM(CASE WHEN p.monto IS NOT NULL THEN 1 ELSE 0 END) con_monto,
  SUM(CASE WHEN p.monto IS NULL THEN 1 ELSE 0 END) sin_monto
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
total, con_monto, sin_monto = cur.fetchone()

cur.execute("""
SELECT estado_promesa, COUNT(*) cnt
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY estado_promesa
ORDER BY cnt DESC
""",(ej,))
by_estado = cur.fetchall()

cur.execute("""
SELECT p.conversacion_pk, p.turno_idx, p.monto, p.moneda, p.numero_cuotas, p.fecha_pago, p.estado_promesa, p.evidence_text
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s AND p.monto IS NULL
ORDER BY p.promesa_pk DESC
LIMIT 20
""",(ej,))
sin_monto_rows = cur.fetchall()

cur.close(); conn.close()

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ejecucion_id", ej])
    w.writerow(["total", total])
    w.writerow(["con_monto", con_monto])
    w.writerow(["sin_monto", sin_monto])
    w.writerow([])
    w.writerow(["by_estado"])
    w.writerow(["estado_promesa", "cantidad"])
    for estado, cnt in by_estado:
        w.writerow([estado, cnt])
    w.writerow([])
    w.writerow(["muestra_sin_monto"])
    w.writerow(["conversacion_pk","turno_idx","monto","moneda","numero_cuotas","fecha_pago","estado_promesa","evidence_text"])
    for r in sin_monto_rows:
        w.writerow(list(r))

print("[OK] wrote:", csv_path)

