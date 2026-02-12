import csv
from pathlib import Path
from sa_core.config import load_config
from sa_core.db import get_conn

out = Path("out_reports")
out.mkdir(parents=True, exist_ok=True)
csv_path = out / "GLOBAL_promesas_performance_por_ejecucion.csv"

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Totales globales
cur.execute("""
SELECT
  COUNT(*) AS total_promesas,
  SUM(CASE WHEN p.monto IS NOT NULL THEN 1 ELSE 0 END) AS con_monto,
  SUM(CASE WHEN p.monto IS NULL THEN 1 ELSE 0 END) AS sin_monto,
  SUM(CASE WHEN p.monto IS NOT NULL AND (p.moneda IS NULL OR p.moneda='') THEN 1 ELSE 0 END) AS con_monto_sin_moneda,
  SUM(CASE WHEN p.monto IS NOT NULL AND (p.moneda IS NOT NULL AND p.moneda<>'') THEN 1 ELSE 0 END) AS con_monto_con_moneda
FROM sa_promesas_pago p
""")
global_totals = cur.fetchone()

# Por ejecución
cur.execute("""
SELECT
  c.ejecucion_id,
  COUNT(*) AS total_promesas,
  SUM(CASE WHEN p.monto IS NOT NULL THEN 1 ELSE 0 END) AS con_monto,
  SUM(CASE WHEN p.monto IS NULL THEN 1 ELSE 0 END) AS sin_monto,
  SUM(CASE WHEN p.monto IS NOT NULL AND (p.moneda IS NULL OR p.moneda='') THEN 1 ELSE 0 END) AS con_monto_sin_moneda,
  SUM(CASE WHEN p.monto IS NOT NULL AND (p.moneda IS NOT NULL AND p.moneda<>'') THEN 1 ELSE 0 END) AS con_monto_con_moneda
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
GROUP BY c.ejecucion_id
ORDER BY c.ejecucion_id
""")
rows = cur.fetchall()

cur.close()
conn.close()

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)

    w.writerow(["GLOBAL_TOTALES"])
    w.writerow(["total_promesas","con_monto","sin_monto","con_monto_sin_moneda","con_monto_con_moneda"])
    w.writerow(list(global_totals))
    w.writerow([])

    w.writerow(["POR_EJECUCION"])
    w.writerow(["ejecucion_id","total_promesas","con_monto","sin_monto","pct_con_monto","con_monto_sin_moneda","con_monto_con_moneda","pct_moneda_en_con_monto"])
    for ej, total, con_monto, sin_monto, cmsm, cmcm in rows:
        pct_con_monto = (con_monto / total * 100) if total else 0.0
        pct_moneda = (cmcm / con_monto * 100) if con_monto else 0.0
        w.writerow([ej, total, con_monto, sin_monto, round(pct_con_monto,2), cmsm, cmcm, round(pct_moneda,2)])

print("[OK] wrote:", csv_path)
print("GLOBAL:", dict(zip(["total_promesas","con_monto","sin_monto","con_monto_sin_moneda","con_monto_con_moneda"], global_totals)))
