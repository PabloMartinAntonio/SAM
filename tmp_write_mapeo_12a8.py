import os, csv

out_dir = "out_reports"
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "mapeo_fases_12a8_propuesto.csv")

rows = [
  ("PRESENTACION_AGENTE", "APERTURA"),
  ("APERTURA", "APERTURA"),
  ("VALIDACION_IDENTIDAD", "IDENTIFICACIÓN"),
  ("EXPOSICION_DEUDA", "INFORMACIÓN_DEUDA"),
  ("OBJECIONES_CLIENTE", "NEGOCIACIÓN"),
  ("OFERTA_PAGO", "NEGOCIACIÓN"),
  ("NEGOCIACION_ACUERDO", "NEGOCIACIÓN"),
  ("CONSULTA_ACEPTACION", "CONSULTA_ACEPTACIÓN"),
  ("FORMALIZACION_PAGO", "FORMALIZACIÓN_PAGO"),
  ("ADVERTENCIAS", "ADVERTENCIAS"),
  ("CIERRE", "CIERRE"),
  ("NOISE", "NOISE"),
]

with open(out_path, "w", newline="", encoding="utf-8") as f:
  w = csv.writer(f)
  w.writerow(["fase_origen", "fase_destino_8"])
  w.writerows(rows)

print("[OK] wrote:", out_path)
